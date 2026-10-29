"""Bounded asynchronous recording used by live Assist only."""
from __future__ import annotations

import threading
import time

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


