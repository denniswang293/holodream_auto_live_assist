"""Bounded asynchronous recording used by live Assist only."""
from __future__ import annotations

import threading
import time
import queue
import copy

import cv2


class LatestSlot:
    def __init__(self):
        self.condition = threading.Condition()
        self.item = None
        self.closed = False
        self.dropped = 0

    def put(self, item):
        with self.condition:
            if self.closed:
                return False
            if self.item is not None:
                self.dropped += 1
            self.item = item
            self.condition.notify()
            return True

    def take(self):
        with self.condition:
            self.condition.wait_for(lambda: self.item is not None or self.closed)
            result, self.item = self.item, None
            return result

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()



VIDEO_INDEX_FIELDS = ["video_frame","source_frame","capture_timestamp","processing_timestamp","gameplay_state",
                      "event_ids","encoder_queue_wait_ms","encoded_at_host","source_video_frame"]


class EncoderWorker:
    def __init__(self,directory,profiler,logger,fps=60,record_source=True,writer_factory=None,
                 overlay_filename='live_overlay_v6.mp4',source_filename='live_source_v6.mp4',
                 index_filename='live_video_index_v6.csv'):
        self.directory,self.profiler,self.logger,self.fps = directory,profiler,logger,fps
        self.record_source,self.writer_factory = record_source,writer_factory or cv2.VideoWriter
        self.overlay_filename,self.source_filename,self.index_filename = overlay_filename,source_filename,index_filename
        self.slot = LatestSlot()
        self.error = None
        self.encoded = 0
        self.thread = threading.Thread(target=self._run,name="holodream-encoder",daemon=False)
        self.thread.start()

    def offer(self,job,image):
        return self.slot.put((job,image,time.perf_counter()))

    def offer_overlay(self, job, snapshot, render):
        """Queue copied inputs; rendering and encoding both happen on this worker."""
        return self.slot.put((job, (snapshot, render), time.perf_counter()))

    def _run(self):
        overlay = source = None
        try:
            while True:
                item = self.slot.take()
                if item is None:
                    break
                job,image,queued = item
                state = job.info["gameplay_state"]
                begin = time.perf_counter()
                wait = begin-queued
                self.profiler.record("encoder_backlog",wait,state)
                if isinstance(image, tuple) and len(image) == 2 and callable(image[1]):
                    snapshot, render = image
                    image = render(snapshot)
                    self.profiler.record("overlay_draw",time.perf_counter()-begin,state)
                begin = time.perf_counter()
                if overlay is None:
                    codec = cv2.VideoWriter_fourcc(*"mp4v")
                    overlay = self.writer_factory(str(self.directory/self.overlay_filename),codec,self.fps,(image.shape[1],image.shape[0]))
                    if not overlay.isOpened():
                        raise OSError("Cannot open overlay encoder")
                    if self.record_source:
                        source = self.writer_factory(str(self.directory/self.source_filename),codec,self.fps,(job.work.shape[1],job.work.shape[0]))
                        if not source.isOpened():
                            raise OSError("Cannot open clean source encoder")
                overlay.write(image)
                if source:
                    source.write(job.work)
                end = time.perf_counter()
                self.profiler.record("video_encoding",end-begin,state)
                self.logger.submit(self.index_filename,[{"video_frame":self.encoded,"source_frame":job.info["frame"],
                    "capture_timestamp":job.info["capture_timestamp"],"processing_timestamp":job.info["processing_timestamp"],
                    "gameplay_state":state,"event_ids":job.event_ids,"encoder_queue_wait_ms":wait*1000,
                    "encoded_at_host":end,"source_video_frame":self.encoded if source else ""}],state)
                self.encoded += 1
        except Exception as error:
            self.error = error
        finally:
            for writer in (overlay,source):
                if writer:
                    writer.release()

    def close(self):
        self.slot.close()
        self.thread.join(timeout=10)
        if self.thread.is_alive() or self.error:
            raise RuntimeError(f"Encoder shutdown failed: {self.error}")


class BoundedCsvLog:
    """Bounded nonblocking CSV handoff; critical loss records a fail-closed error."""
    _STOP = object()

    def __init__(self, logger, capacity=512, *, critical=False, close_timeout_s=1.0):
        self.logger = logger
        self.critical = critical
        self.close_timeout_s = max(0.05, float(close_timeout_s))
        self.rows_dropped = 0
        self.error = None
        self._closed = False
        self.queue = queue.Queue(maxsize=max(1, int(capacity)))
        self.thread = threading.Thread(target=self._run, name="holodream-csv", daemon=True)
        self.thread.start()

    def _check(self):
        if self.error:
            raise RuntimeError(f"CSV writer failed: {self.error}") from self.error

    def write(self, row):
        # Copy so callers can safely reuse or mutate their row after submission.
        try:
            item = copy.deepcopy(row)
        except Exception as error:
            self.rows_dropped += 1
            if self.error is None:
                self.error = error
            return False
        if self.error is not None or self._closed:
            self.rows_dropped += 1
            if self.critical and self.error is None:
                self.error = RuntimeError("critical action log submitted after close")
            return False
        try:
            self.queue.put_nowait(item)
            return True
        except queue.Full:
            self.rows_dropped += 1
            if self.critical and self.error is None:
                self.error = BufferError("critical action log queue overflow; Assist must disarm")
            return False

    def _run(self):
        try:
            while True:
                item = self.queue.get()
                try:
                    if item is self._STOP:
                        return
                    self.logger.write(item)
                finally:
                    self.queue.task_done()
        except Exception as error:
            self.error = error
            while True:
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
                else:
                    self.queue.task_done()

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.thread.is_alive():
            deadline = time.monotonic() + self.close_timeout_s
            while self.thread.is_alive() and time.monotonic() < deadline:
                try:
                    self.queue.put(self._STOP, timeout=.02)
                    break
                except queue.Full:
                    continue
            self.thread.join(max(0, deadline - time.monotonic()))
        if self.thread.is_alive():
            self.error = self.error or TimeoutError("CSV writer did not stop before shutdown timeout")
            raise RuntimeError(f"CSV writer shutdown failed: {self.error}") from self.error
        try:
            self.logger.close()
        finally:
            self._check()


