"""Build the VFR source-left / fresh-geometry-right review video."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.geometry_scene.compare import make_comparison


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-video", type=Path, required=True)
    p.add_argument("--geometry-video", type=Path, required=True)
    p.add_argument("--frame-index", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(make_comparison(a.source_video, a.geometry_video,
                                     a.frame_index, a.run_id, a.out), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
