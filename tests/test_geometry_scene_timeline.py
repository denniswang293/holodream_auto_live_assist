import csv
from pathlib import Path

import numpy as np
import pytest

av = pytest.importorskip("av")

from tools.geometry_scene.scene import Point, Scene, Segment
from tools.geometry_scene.scene_io import save_scene
from tools.geometry_scene.timeline import render_timeline
from tools.geometry_scene.video import VFRVideoWriter


def _index(path: Path, run_id="r"):
    rows = []
    for i, t in enumerate((0.0, 0.020011, 0.060023)):
        rows.append({"run_id": run_id, "video_frame": i, "source_frame": i,
                     "source_pts_seconds": i/60, "capture_timestamp": t+100,
                     "acquired_timestamp": t+100, "acquired_elapsed_seconds": t})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def test_full_timeline_renderer_uses_scene_and_timestamp_index_without_source_video(tmp_path):
    scene = Scene(64, 48, tuple(Segment(Point(x, 1), Point(x, 40)) for x in (2,10,18,26,34,42,50)),
                  Segment(Point(2,40),Point(50,40)),(),"2.0","r")
    scene_path=tmp_path/"scene.json"; index_path=tmp_path/"index.csv"; out=tmp_path/"geometry.mp4"
    save_scene(scene,scene_path);_index(index_path)
    result=render_timeline(scene_path,index_path,"r",out)
    assert result["frames"]==3 and result["renderer_input_boundary"]=="SCENE_JSON_AND_FRAME_INDEX_ONLY"
    with av.open(str(out)) as c:
        frames=list(c.decode(video=0))
    assert [round(float(f.pts*f.time_base),6) for f in frames]==[0.0,0.020011,0.060022]


def test_vfr_comparison_preserves_source_and_geometry_frame_count(tmp_path):
    from tools.geometry_scene.compare import make_comparison
    source=tmp_path/"source.mp4";geometry=tmp_path/"geometry.mp4";comparison=tmp_path/"comparison.mp4"
    times=(0.0,0.020011,0.060023); frame=np.zeros((720,1280,3),np.uint8)
    for path,color in ((source,(10,20,30)),(geometry,(40,50,60))):
        with VFRVideoWriter(path,1280,720,times[-1]-times[-2],crf=30) as w:
            for i,t in enumerate(times):
                image=np.full_like(frame,color);image[0,0]=i
                w.write(image,t)
    index=tmp_path/"index.csv";_index(index)
    summary=make_comparison(source,geometry,index,"r",comparison)
    assert summary["comparison_frames"]==3 and summary["dropped_or_extra_frames"]==0
    with av.open(str(comparison)) as c:
        assert c.streams.video[0].width==2560
        frames=list(c.decode(video=0))
    assert len(frames)==3
    assert [round(float(f.pts*f.time_base),6) for f in frames]==[0.0,0.020011,0.060022]
