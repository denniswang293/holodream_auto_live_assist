from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import stat
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def reparse(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except AttributeError:
        return path.is_symlink()


def verify_protected(items: dict[str, str], project: Path) -> list[str]:
    failed = []
    for raw, digest in items.items():
        path = Path(raw)
        if not path.is_absolute():
            path = project / path
        if reparse(path) or not path.is_file() or sha256(path) != digest:
            failed.append(str(path))
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash-guarded cleanup confined to one fresh scratch iteration")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--recording-root", type=Path, required=True)
    parser.add_argument("--iteration", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--preview", action="store_true", help="default; no deletion")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    project = root.parents[2]
    if root.name != f"fresh_20261117" or root.parent.name != "geometry_video_v1" or root.parent.parent.name != "output":
        raise SystemExit("cleanup root must be the new fresh_20261117 workspace")
    manifest_path = args.manifest.resolve(strict=True)
    if reparse(manifest_path):
        raise SystemExit("manifest cannot be a symlink/junction")
    manifest_path.relative_to(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if str(manifest.get("iteration_id")) != str(args.iteration):
        raise SystemExit("iteration ID mismatch")
    scratch = (root / "_scratch" / f"iteration_{args.iteration}").resolve(strict=False)
    rows = []
    blocked = []
    seen = set()
    for item in manifest.get("delete_candidates", []):
        if item.get("action") != "DELETE_CANDIDATE" or item.get("rebuildable") is not True or item.get("referenced") is not False:
            blocked.append({"path": item.get("path"), "reason": "candidate is not explicitly rebuildable and unreferenced"})
            continue
        path = root / item.get("path", "")
        try:
            path.resolve(strict=True).relative_to(scratch)
        except (FileNotFoundError, ValueError):
            blocked.append({"path": item.get("path"), "reason": "candidate must be an existing file under this iteration scratch"})
            continue
        cursor = root
        safe = True
        for part in Path(item["path"]).parts:
            cursor /= part
            if reparse(cursor):
                safe = False
                break
        if not safe or not path.is_file():
            blocked.append({"path": item.get("path"), "reason": "candidate traverses reparse point or is not a regular file"})
            continue
        key = str(path.resolve())
        if key in seen:
            blocked.append({"path": item.get("path"), "reason": "duplicate manifest entry"})
            continue
        seen.add(key)
        if path.stat().st_size != int(item.get("bytes", -1)) or sha256(path) != item.get("sha256"):
            blocked.append({"path": item.get("path"), "reason": "candidate size/hash differs from manifest"})
            continue
        rows.append({"path": item["path"], "bytes": path.stat().st_size, "sha256": item["sha256"]})
    for keep in manifest.get("keep_paths", []):
        path = root / keep
        if not path.is_file() or reparse(path) or str(path.resolve()) in seen:
            blocked.append({"path": keep, "reason": "protected keep path missing, reparse, or also a delete candidate"})

    protected = manifest.get("protected_sha256", {})
    protected_failed = verify_protected(protected, project)
    if protected_failed:
        blocked.extend({"path": p, "reason": "protected hash mismatch"} for p in protected_failed)
    report = {"iteration_id": str(args.iteration), "mode": "EXECUTE" if args.execute else "PREVIEW",
              "status": "BLOCKED" if blocked else "PREVIEW_READY", "files_before": len(list(root.rglob("*"))),
              "delete_candidates": rows, "bytes_to_delete": sum(x["bytes"] for x in rows),
              "protected_files_checked": len(protected), "blocked_paths": blocked,
              "cleanup_scope": str(scratch), "outside_scope_deletions": 0}
    if not args.execute:
        preview = root / "iterations" / f"cleanup_preview_{args.iteration}.json"
        preview.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("status", "bytes_to_delete", "protected_files_checked", "blocked_paths")}, indent=2))
        return 1 if blocked else 0

    if not blocked:
        for item in rows:
            path = (root / item["path"]).resolve(strict=True)
            if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
                blocked.append({"path": item["path"], "reason": "changed after preview"})
                break
            path.unlink()
        protected_failed = verify_protected(protected, project)
        blocked.extend({"path": p, "reason": "protected hash mismatch after cleanup"} for p in protected_failed)
    for directory, _dirs, _files in os.walk(scratch, topdown=False):
        path = Path(directory)
        # os.walk's child lists are snapshots; inspect the directory again so
        # an emptied parent can be removed in the same bottom-up pass.
        if path.exists() and not any(path.iterdir()):
            path.rmdir()
    history = root / "iterations" / "cleanup_history.csv"
    history.parent.mkdir(parents=True, exist_ok=True)
    file_exists = history.exists()
    fields = ["iteration_id", "bytes_before", "bytes_deleted", "files_deleted", "files_kept",
              "blocked_paths", "validation_status", "manifest_path"]
    total_files = sum(1 for p in root.rglob("*") if p.is_file())
    deleted_bytes = 0 if blocked else sum(r["bytes"] for r in rows)
    status = "BLOCKED" if blocked else ("NO_SAFE_CLEANUP" if not rows else "CLEANED")
    with history.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        writer.writerow({"iteration_id": args.iteration, "bytes_before": sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) + deleted_bytes,
                         "bytes_deleted": deleted_bytes, "files_deleted": 0 if blocked else len(rows),
                         "files_kept": total_files, "blocked_paths": json.dumps(blocked),
                         "validation_status": status, "manifest_path": str(manifest_path)})
    prior = list(csv.DictReader(history.open("r", encoding="utf-8-sig")))
    summary = {"status": status, "iterations": len(prior),
               "cumulative_bytes_deleted": sum(int(x["bytes_deleted"]) for x in prior),
               "last_iteration": args.iteration, "last_blocked_paths": blocked}
    (root / "iterations" / "cleanup_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
