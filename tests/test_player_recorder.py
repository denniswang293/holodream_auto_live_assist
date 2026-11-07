import csv
import importlib.util
import json
from pathlib import Path
import zipfile

import cv2
import numpy as np
import pytest


spec = importlib.util.spec_from_file_location('standalone_player_recorder',
    Path(__file__).resolve().parents[1]/'HoloDream_Recorder/recorder.py')
recorder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorder)


def read(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig')))


def test_share_recorder_self_test_video_index_keyboard_and_archive_agree(tmp_path):
    archive = recorder.self_test(tmp_path)
    directory = archive.with_suffix('')
    meta = json.loads((directory/'session.json').read_text())
    assert meta['complete'] and meta['automatic_input'] is False
    assert meta['capture_kind'] == 'SYNTHETIC_TEST_NOT_GAME'
    assert meta['encoded_frames'] == meta['verified_video_frames'] == 12
    index = read(directory/'live_video_index.csv')
    assert [int(r['video_frame']) for r in index] == list(range(12))
    assert all(float(r['capture_timestamp']) <= float(r['acquired_timestamp'])
               <= float(r['encoded_at_host']) for r in index)
    assert float(index[-1]['capture_timestamp']) < meta['stopped_timestamp']
    keys = read(directory/'player_key_events.csv')
    assert [(r['action'],r['key']) for r in keys] == [('key_down','S'),('key_up','S')]
    assert float(keys[0]['elapsed_s']) == pytest.approx(.01)
    cap = cv2.VideoCapture(str(directory/'live_source.mp4'))
    count = 0
    while True:
        ok,frame = cap.read()
        if not ok: break
        assert frame.shape[:2] == (720,1280)
        count += 1
    cap.release()
    assert count == len(index)
    # Packing must not scoop up arbitrary neighbouring private files.
    (directory/'unrelated.txt').write_text('not part of game evidence')
    recorder.pack_session(directory)
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == 5
        assert not any('unrelated' in n for n in z.namelist())
        assert z.testzip() is None


def test_recorder_keys_are_allowlisted_deduplicated_and_not_fabricated(tmp_path):
    s = recorder.Session(tmp_path,'test',clock=lambda:10.,synthetic=True,started_at=9.9)
    s.key(9.8,'key_down','S')  # Before F9.
    s.key(10.,'key_down','X')  # Never collect arbitrary text.
    s.key(10.,'key_down','S',31)
    s.key(10.01,'key_down','S',31)
    s.key(10.02,'key_down','F',focused=False)
    s.key(10.03,'key_up','S',31,focused=False)
    s.key(10.04,'key_down','D',32,injected=True)
    s.frame(np.zeros((80,160,3),np.uint8),10.,10.001,(20,30,160,80))
    s.close('test',lost_keyboard_events=2)
    rows = read(s.directory/'player_key_events.csv')
    assert [(r['action'],r['key']) for r in rows] == [
        ('key_down','S'),('key_up','S'),('key_down','D')]
    assert rows[-1]['injected'] == 'True'
    meta = json.loads((s.directory/'session.json').read_text())
    assert meta['held_keys_at_stop'] == ['D']
    assert not meta['keyboard_trace_complete']
    frame = read(s.directory/'live_video_index.csv')[0]
    assert (int(frame['offset_x']),int(frame['offset_y'])) == (0,40)
    assert float(frame['scale']) == 8.


def test_nonmonotonic_capture_is_rejected_without_extra_video_frame(tmp_path):
    s = recorder.Session(tmp_path,'test',clock=lambda:10.,synthetic=True)
    frame = np.zeros((404,720,3),np.uint8)
    s.frame(frame,10.,10.,(0,0,720,404))
    try:
        with pytest.raises(ValueError,match='timestamps'):
            s.frame(frame,10.,10.,(0,0,720,404))
    finally:
        s.close('test')
    assert len(read(s.directory/'live_video_index.csv')) == 1
    assert s.meta['verified_video_frames'] == 1


def test_failed_recording_retains_evidence_but_cannot_be_packaged_as_complete(tmp_path):
    s = recorder.Session(tmp_path,'test',clock=lambda:10.,synthetic=True)
    s.frame(np.zeros((80,160,3),np.uint8),10.,10.,(0,0,160,80))
    s.close('error',error='simulated capture failure')
    assert not s.meta['complete']
    assert (s.directory/'live_video_index.csv').exists()
    with pytest.raises(ValueError,match='not complete'):
        recorder.pack_session(s.directory)
