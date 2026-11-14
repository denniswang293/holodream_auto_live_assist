"""Audit exported MockActuator scheduler events for replay safety invariants."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.model import KEYS


def audit(path: Path):
    groups=defaultdict(list)
    with path.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            groups[(row["provider"],float(row["latency_ms"]))].append(row)
    results=[]
    for (provider,latency),events in sorted(groups.items()):
        downs=[e for e in events if e["event"]=="pressed"]
        ups=[e for e in events if e["event"]=="released"]
        duids=[e["uid"] for e in downs]
        release_uids={e["uid"] for e in ups}
        results.append({"provider":provider,"latency_ms":latency,"actuator":"MockActuator",
            "pressed_events":len(downs),"released_events":len(ups),
            "duplicate_press_uid_count":len(duids)-len(set(duids)),
            "unreleased_press_uid_count":len(set(duids)-release_uids),
            "key_up_error_count":sum(e["event"]=="key_up_error" for e in events),
            "illegal_key_count":sum(e.get("key") not in KEYS for e in downs),
            "rejected_events":sum(e["event"]=="rejected" for e in events),
            "late_rejections":sum(e["event"]=="rejected" and e.get("reason")=="late" for e in events),
            "stale_pause_events":sum(e["event"]=="input_paused" for e in events)})
    return results


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--actions",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    result=audit(args.actions)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(args.out)


if __name__=="__main__":main()
