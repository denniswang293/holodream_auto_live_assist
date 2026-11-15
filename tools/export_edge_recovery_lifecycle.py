"""Export the latest fixed-Replay lifecycle for the two frame-373 edge masks."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replay-run-dir", type=Path, required=True)
    ap.add_argument("--segmentation-manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    replay = args.replay_run_dir.resolve()
    seg_manifest_path = args.segmentation_manifest.resolve()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}")
    seg = json.loads(seg_manifest_path.read_text(encoding="utf-8"))
    if seg.get("index_mapping_verified") is not True:
        raise SystemExit("segmentation evidence does not verify frame/index mapping")
    source_hash = seg["source_video_sha256"]
    index_hash = seg["index_sha256"]
    frame = 373
    expected_boxes = {tuple(box) for box in seg["frame_373_current"]["current_edge_cyan_tap_boxes"]}

    trace = read_csv(replay / "candidate_trace.csv")
    component_rows = [r for r in trace if r.get("provider") == "segmented"
                      and r.get("video_frame") == str(frame)
                      and r.get("role") == "tap_face"
                      and r.get("color") == "cyan"
                      and tuple(json.loads(r["bbox"].replace("(", "[").replace(")", "]"))) in expected_boxes]
    pixel_rows = {tuple(json.loads(r["bbox"].replace("(", "[").replace(")", "]"))): r
                  for r in component_rows if r.get("candidate_stage") == "segmentation_to_detector"}
    tracker_rows = {tuple(json.loads(r["bbox"].replace("(", "[").replace(")", "]"))): r
                    for r in component_rows if r.get("candidate_stage") == "tracker_input"}
    if set(pixel_rows) != expected_boxes or set(tracker_rows) != expected_boxes:
        raise SystemExit(f"exact frame/component trace coverage missing: pixel={set(pixel_rows)} tracker={set(tracker_rows)}")

    decisions = read_csv(replay / "physical_note_decisions.csv")
    actions = read_csv(replay / "mock_actions.csv")
    lifecycle = []
    for box in sorted(expected_boxes):
        pixel = pixel_rows[box]
        tracker = tracker_rows[box]
        uid = tracker.get("tracker_uid", "")
        if not uid:
            raise SystemExit(f"no provider-local tracker UID for component {box}")
        decision_matches = [r for r in decisions if r.get("provider") == "segmented"
                            and r.get("video_frame") == str(frame) and r.get("note_uid") == uid]
        if len(decision_matches) != 1:
            raise SystemExit(f"expected one exact decision row for {uid}; got {len(decision_matches)}")
        decision = decision_matches[0]
        events = [r for r in actions if r.get("provider") == "segmented" and r.get("uid") == uid]
        accepted = next((r for r in events if r.get("event") == "accepted"), None)
        pressed = next((r for r in events if r.get("event") == "pressed"), None)
        released = next((r for r in events if r.get("event") == "released"), None)
        rejected = [r for r in events if r.get("event") == "rejected"]
        lifecycle.append({
            "source_video_sha256": source_hash,
            "source_index_sha256": index_hash,
            "video_frame": frame,
            "source_frame": pixel["source_frame"],
            "capture_timestamp": pixel["capture_timestamp"],
            "provider": "segmented",
            "component_id": pixel["component_id"],
            "pixel_role": pixel["role"],
            "color": pixel["color"],
            "component_bbox_rectified": pixel["bbox"],
            "component_area_pixels": pixel["area"],
            "adapter_conversion": pixel["conversion"],
            "adapter_keys": pixel["keys"],
            "tracker_uid_provider_local": uid,
            "tracker_confirmed_at_frame": tracker["tracker_confirmed"],
            "tracker_kind": tracker["tracker_kind"],
            "tracker_state_at_frame": tracker["tracker_state"],
            "tracker_reason_at_frame": tracker["tracker_reason"],
            "timing_reason_at_frame": tracker["timing_reason"],
            "scheduler_pending_at_frame": tracker["scheduler_pending"],
            "physical_decision_state": decision["state"],
            "physical_decision_reason": decision["reason"],
            "decision_bbox": decision["bbox"],
            "decision_key_candidates": decision["keys"],
            "scheduler_accept_at": accepted["at"] if accepted else "",
            "mock_key": pressed["key"] if pressed else "",
            "mock_key_down_at": pressed["at"] if pressed else "",
            "mock_key_up_at": released["at"] if released else "",
            "mock_key_up_reason": released["reason"] if released else "",
            "scheduler_rejection_count_for_uid": len(rejected),
            "action_lifecycle_complete": bool(accepted and pressed and released and not rejected),
            "physical_note_truth": "UNKNOWN",
            "evidence_grade": "PROVISIONAL_SOURCE_FRAME_AND_PROVIDER_TRACE; not human-reviewed physical-note truth",
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(lifecycle[0]))
        writer.writeheader()
        writer.writerows(lifecycle)
    print(out)


if __name__ == "__main__":
    main()
