"""Preview/execute exact-file cleanup for Geometry Video V1 iterations.

Deletion is limited to manifest-listed regular files in this project output.
The tool never recursively removes directories or follows reparse points.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import stat
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_reparse(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
        return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except AttributeError:
        return path.is_symlink()


def project_files(root: Path) -> list[Path]:
    result = []
    for directory, children, files in os.walk(root, topdown=True, followlinks=False):
        parent = Path(directory)
        children[:] = [name for name in children if not is_reparse(parent / name)]
        result.extend(parent / name for name in files
                      if (parent / name).is_file() and not is_reparse(parent / name))
    return result


def validate_source_hashes(root: Path) -> list[str]:
    project = root.parent.parent
    inventory_path = root / "inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
    problems = []
    for run in inventory:
        for source in run.get("source_files", []):
            path = project / source["path"]
            if not path.is_file() or sha256(path) != source["sha256"]:
                problems.append(str(path))
    return problems


def resolve_candidate(root: Path, project: Path, entry: dict) -> tuple[Path | None, str | None]:
    raw = Path(entry.get("path", ""))
    if raw.is_absolute() or not entry.get("disposable", False):
        return None, "candidate must be a relative disposable file"
    target = project / raw
    try:
        relative = target.relative_to(root)
    except ValueError:
        return None, "candidate is outside geometry_video_v1 output"
    allowed_scratch = (len(relative.parts) >= 3 and relative.parts[0] == "_scratch" and
                       relative.parts[1].startswith("iteration_"))
    allowed_registered = (((relative.parts[0] == "geometry_alignment_review" and len(relative.parts) >= 3) or
                           (relative.parts[0] == "performance" and len(relative.parts) >= 2)) and
                          entry.get("registered_redundant") is True)
    allowed_registered_preview = (len(relative.parts) == 1 and
                                  relative.name.startswith("blank_geometry_preview") and
                                  entry.get("registered_redundant") is True)
    inventory_path = root / "inventory.json"
    run_ids = set()
    if inventory_path.is_file():
        try:
            run_ids = {row.get("run_id") for row in json.loads(inventory_path.read_text(encoding="utf-8-sig"))
                       if row.get("availability") == "AVAILABLE"}
        except Exception:
            pass
    allowed_failed_output = (len(relative.parts) >= 2 and relative.parts[0] in run_ids and
                             entry.get("registered_failed_output") is True)
    if not (allowed_scratch or allowed_registered or allowed_registered_preview or allowed_failed_output):
        return None, "candidate is outside scratch or explicitly registered redundant/failed outputs"
    current = root
    for part in relative.parts:
        current = current / part
        if not current.exists() or is_reparse(current):
            return None, "candidate is missing or traverses a symlink/junction/reparse point"
    resolved = target.resolve(strict=True)
    try:
        resolved.relative_to(root.resolve(strict=True))
    except ValueError:
        return None, "resolved candidate escapes geometry_video_v1 output"
    if not resolved.is_file():
        return None, "only exact regular files may be deleted"
    if target.stat().st_size != int(entry.get("bytes", -1)):
        return None, "candidate size differs from cleanup manifest"
    if sha256(target) != entry.get("sha256"):
        return None, "candidate hash differs from cleanup manifest"
    return target, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("output/geometry_video_v1"))
    parser.add_argument("--iteration", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true", help="default: preview only")
    mode.add_argument("--execute", action="store_true", help="delete only manifest-listed exact files")
    args = parser.parse_args()
    supplied_root = args.root.absolute()
    if is_reparse(supplied_root):
        raise SystemExit("Geometry output root cannot be a symlink/junction/reparse point")
    root = supplied_root.resolve(strict=True)
    if root.name != "geometry_video_v1" or root.parent.name != "output":
        raise SystemExit("Cleanup root must be this workspace's output/geometry_video_v1 directory")
    project = root.parent.parent
    manifest_path = args.manifest.resolve(strict=True)
    if is_reparse(manifest_path):
        raise SystemExit("Cleanup manifest cannot be a symlink/junction/reparse point")
    try:
        manifest_path.relative_to(root.resolve())
    except ValueError:
        raise SystemExit("Cleanup manifest must be inside geometry_video_v1 output")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if str(manifest.get("iteration_id")) != str(args.iteration):
        raise SystemExit("Iteration ID does not match cleanup manifest")
    candidates = manifest.get("delete_files", [])
    keep_paths = manifest.get("keep_paths", [])
    blocked = []
    plan = []
    seen = set()
    for entry in candidates:
        target, error = resolve_candidate(root, project, entry)
        if error:
            blocked.append({"path": entry.get("path", ""), "reason": error})
            continue
        if str(target) in seen:
            blocked.append({"path": entry["path"], "reason": "duplicate manifest candidate"})
            continue
        seen.add(str(target))
        plan.append({"path": entry["path"], "bytes": target.stat().st_size, "sha256": entry["sha256"]})
    for keep in keep_paths:
        path = project / keep
        if not path.is_file() or is_reparse(path):
            blocked.append({"path": keep, "reason": "preserve path is missing or is a reparse point"})
        elif str(path.resolve()) in seen:
            blocked.append({"path": keep, "reason": "preserve path is also listed for deletion"})
    bytes_before = sum(path.stat().st_size for path in project_files(root))
    report = {"iteration_id": str(args.iteration), "mode": "EXECUTE" if args.execute else "PREVIEW",
              "manifest": str(manifest_path), "bytes_before": bytes_before,
              "delete_candidates": plan, "files_kept": len(project_files(root)),
              "blocked_paths": blocked, "status": "BLOCKED" if blocked else "PREVIEW_READY"}
    if not args.execute:
        (root / "iterations").mkdir(parents=True, exist_ok=True)
        (root / "iterations" / f"cleanup_preview_{args.iteration}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1 if blocked else 0

    source_before = validate_source_hashes(root)
    if source_before:
        report["blocked_paths"].extend({"path": path, "reason": "source hash differs from inventory before cleanup"}
                                       for path in source_before)
        report["status"] = "BLOCKED"
    deleted = []
    if not report["blocked_paths"]:
        for entry, planned in zip(candidates, plan):
            target, error = resolve_candidate(root, project, entry)
            if error or target is None:
                report["blocked_paths"].append({"path": entry.get("path", ""), "reason": error or "candidate changed"})
                break
            target.unlink()
            deleted.append(planned)
        source_after = validate_source_hashes(root)
        if source_after:
            report["blocked_paths"].extend({"path": path, "reason": "source hash changed after cleanup"}
                                           for path in source_after)
    report["deleted_files"] = deleted
    report["bytes_deleted"] = sum(row["bytes"] for row in deleted)
    report["files_kept"] = len(project_files(root))
    report["status"] = "BLOCKED" if report["blocked_paths"] else ("NO_SAFE_CLEANUP" if not deleted else "CLEANED")
    iterations = root / "iterations"
    iterations.mkdir(parents=True, exist_ok=True)
    history = iterations / "cleanup_history.csv"
    fields = ["iteration_id", "bytes_before", "bytes_deleted", "files_deleted", "files_kept",
              "blocked_paths", "validation_status", "manifest_path"]
    write_header = not history.exists()
    with history.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        if write_header: writer.writeheader()
        writer.writerow({"iteration_id": args.iteration, "bytes_before": bytes_before,
                         "bytes_deleted": report["bytes_deleted"], "files_deleted": len(deleted),
                         "files_kept": report["files_kept"],
                         "blocked_paths": json.dumps(report["blocked_paths"]),
                         "validation_status": report["status"], "manifest_path": str(manifest_path)})
    total_bytes = sum(int(row["bytes_deleted"]) for row in csv.DictReader(history.open("r", encoding="utf-8")))
    summary = {"status": report["status"], "iterations": sum(1 for _ in csv.DictReader(history.open("r", encoding="utf-8"))),
               "cumulative_bytes_deleted": total_bytes, "last_iteration": args.iteration,
               "last_blocked_paths": report["blocked_paths"]}
    (iterations / "cleanup_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["blocked_paths"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
