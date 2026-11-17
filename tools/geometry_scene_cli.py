"""Renderer-only CLI. Render commands accept Scene JSON and never open source video."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from tools.geometry_scene.renderer import render_scene_frame
from tools.geometry_scene.scene import Point, Scene, Segment
from tools.geometry_scene.scene_io import load_scene, save_scene


def render(scene_path: Path, output_path: Path, fps: float, frames: int) -> None:
    scene = load_scene(scene_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps,
                             (scene.width, scene.height))
    if not writer.isOpened():
        raise RuntimeError(f"could not create video: {output_path}")
    try:
        for i in range(frames):
            writer.write(render_scene_frame(scene, i / fps))
    finally:
        writer.release()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("render-scene", help="render fresh geometry from Scene JSON only")
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--fps", type=float, default=60.0)
    p.add_argument("--frames", type=int, required=True)
    b = sub.add_parser("blank-preview", help="build and render the independent rail calibration preview")
    b.add_argument("--calibration", type=Path, required=True)
    b.add_argument("--scene-out", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--fps", type=float, default=60.0)
    b.add_argument("--seconds", type=float, default=3.0)
    t = sub.add_parser("render-timeline", help="render a full acquired-time timeline from Scene JSON + index only")
    t.add_argument("--scene", type=Path, required=True)
    t.add_argument("--frame-index", type=Path, required=True)
    t.add_argument("--run-id", required=True)
    t.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "render-scene":
        render(args.scene, args.out, args.fps, args.frames)
        print(json.dumps({"scene": str(args.scene), "output": str(args.out),
                          "frames": args.frames, "fps": args.fps,
                          "renderer_input": "scene_json_only"}, indent=2))
    elif args.command == "blank-preview":
        config = json.loads(args.calibration.read_text(encoding="utf-8"))
        top = config["rail_top_x_estimates"]
        bottom = config["rail_bottom_x_estimates"]
        y0, y1 = config["boundary_rails_top_y"], config["boundary_rails_bottom_y"]
        rails = tuple(Segment(Point(x0, y0), Point(x1, y1)) for x0, x1 in zip(top, bottom))
        j = config["judgment_line_estimate"]
        scene = Scene(config["width"], config["height"], rails,
                      Segment(Point(*j["start"]), Point(*j["end"])), (), "2.0",
                      config["reference_source"], (12, 14, 20))
        save_scene(scene, args.scene_out)
        frames = round(args.fps * args.seconds)
        render(args.scene_out, args.out, args.fps, frames)
        print(json.dumps({"scene": str(args.scene_out), "output": str(args.out),
                          "frames": frames, "fps": args.fps,
                          "calibration_status": config["status"]}, indent=2))
    elif args.command == "render-timeline":
        from tools.geometry_scene.timeline import render_timeline
        print(json.dumps(render_timeline(args.scene, args.frame_index, args.run_id, args.out), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
