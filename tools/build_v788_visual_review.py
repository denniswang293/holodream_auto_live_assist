"""Build the offline V7.8.8 visual identity review package.

This tool consumes the existing V7.8.7 trace package and source recording.  It
does not replay or modify the live tracker, planner, scheduler, actuator, or
configuration.  The generated page is static and can be opened from disk.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REVIEW_FIELDS = [
    "case_id", "source_frame", "old_uid", "candidate_id", "appearance",
    "old_lane", "new_lane", "prior_observation_frames",
    "subsequent_real_observations", "competing_track_ids",
    "same_physical_note_verdict", "visual_confidence", "reviewer_status",
    "reviewer_notes", "game_judgment", "software_verdict", "evidence_paths",
]
IDENTITY_VALUES = {"SAME_PHYSICAL_NOTE", "DIFFERENT_PHYSICAL_NOTE", "NOT_A_REAL_NOTE", "AMBIGUOUS", "UNREVIEWED", "UNKNOWN"}
CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
STATUS_VALUES = {"REVIEWED", "UNREVIEWED"}
GAME_VALUES = {"PERFECT", "GOOD", "MISS", "UNKNOWN"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else REVIEW_FIELDS)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in fields} for row in rows)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def number(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def parse_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    try:
        parsed = json.loads(str(value).replace("'", '"'))
    except (TypeError, ValueError, json.JSONDecodeError):
        nums = re.findall(r"-?\d+(?:\.\d+)?", str(value))
        if len(nums) < 4:
            return None
        parsed = [float(x) for x in nums[:4]]
    if isinstance(parsed, (list, tuple)) and len(parsed) >= 4:
        vals = [number(x) for x in parsed[:4]]
        if all(v is not None for v in vals):
            return tuple(float(v) for v in vals)  # type: ignore[arg-type]
    return None


def valid_review_row(row: dict[str, Any]) -> tuple[bool, str]:
    if not row.get("case_id"):
        return False, "missing case_id"
    identity = str(row.get("same_physical_note_verdict", "UNKNOWN") or "UNKNOWN")
    confidence = str(row.get("visual_confidence", "UNKNOWN") or "UNKNOWN")
    status = str(row.get("reviewer_status", "UNREVIEWED") or "UNREVIEWED")
    game = str(row.get("game_judgment", "UNKNOWN") or "UNKNOWN")
    if identity not in IDENTITY_VALUES:
        return False, f"invalid identity verdict: {identity}"
    if confidence not in CONFIDENCE_VALUES:
        return False, f"invalid confidence: {confidence}"
    if status not in STATUS_VALUES:
        return False, f"invalid reviewer status: {status}"
    if game not in GAME_VALUES:
        return False, f"invalid game judgment: {game}"
    return True, ""


def normalize_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    result = []
    for row in rows:
        normalized = {field: str(row.get(field, "") if row.get(field, "") is not None else "") for field in REVIEW_FIELDS}
        normalized["same_physical_note_verdict"] = normalized["same_physical_note_verdict"] or "UNKNOWN"
        normalized["visual_confidence"] = normalized["visual_confidence"] or "UNKNOWN"
        normalized["reviewer_status"] = normalized["reviewer_status"] or "UNREVIEWED"
        normalized["game_judgment"] = normalized["game_judgment"] or "UNKNOWN"
        valid, reason = valid_review_row(normalized)
        if not valid:
            raise ValueError(f"invalid review row {normalized.get('case_id')}: {reason}")
        result.append(normalized)
    return result


def choose_review_rows(source_results: Path) -> list[dict[str, str]]:
    completed = source_results / "physical_identity_review_completed.csv"
    template = source_results / "physical_identity_review.csv"
    return normalize_review_rows(read_csv(completed if completed.exists() else template))


def add_parity_review_rows(rows: list[dict[str, str]], divergence: list[dict[str, str]], candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    """Add the two required parity cases without changing the V7.8.7 CSV."""
    existing = {r.get("case_id") for r in rows}
    result = list(rows)
    for case_id, frame, track in (("parity_385", "385", "1000003"), ("parity_546", "546", "1000014")):
        if case_id in existing:
            continue
        div = next((r for r in divergence if r.get("source_frame") == frame), {})
        cand = next((r for r in candidates if r.get("source_frame") == frame and r.get("stage") == "candidate_final" and r.get("candidate_id") == div.get("target_candidate_id")), {})
        result.append({
            "case_id": case_id, "source_frame": frame, "old_uid": f"simple:{track}",
            "candidate_id": div.get("target_candidate_id", ""), "appearance": cand.get("appearance", "UNKNOWN"),
            "old_lane": "UNKNOWN", "new_lane": cand.get("candidate_keys", "UNKNOWN"),
            "prior_observation_frames": "UNKNOWN", "subsequent_real_observations": "UNKNOWN",
            "competing_track_ids": "UNKNOWN", "same_physical_note_verdict": "UNKNOWN",
            "visual_confidence": "UNKNOWN", "reviewer_status": "UNREVIEWED",
            "reviewer_notes": "Compare ±5 source frames; replay-extra is a trace-semantic difference, not an identity verdict.",
            "game_judgment": "UNKNOWN", "software_verdict": "TRACE_SEMANTICS_EXTRA", "evidence_paths": "",
        })
    return normalize_review_rows(result)


def sample_index(index: list[dict[str, str]], center_ts: float | None, window_ms: float, limit: int = 15) -> list[dict[str, str]]:
    if center_ts is None:
        return []
    available = [r for r in index if number(r.get("capture_timestamp")) is not None and abs(number(r.get("capture_timestamp"), 0) - center_ts) <= window_ms / 1000.0]
    available.sort(key=lambda r: number(r.get("capture_timestamp"), 0) or 0)
    if len(available) <= limit:
        return available
    picks = []
    for i in range(limit):
        pos = round(i * (len(available) - 1) / max(1, limit - 1))
        picks.append(available[pos])
    unique = []
    seen = set()
    for row in picks:
        key = row.get("source_frame", "")
        if key not in seen:
            unique.append(row); seen.add(key)
    return unique


def row_subset(rows: list[dict[str, str]], source_frame: str) -> list[dict[str, str]]:
    return [r for r in rows if str(r.get("source_frame", "")) == str(source_frame)]


def case_data(review: dict[str, str], index: list[dict[str, str]], candidates: list[dict[str, str]], attempts: list[dict[str, str]], tracks: list[dict[str, str]], proposals: list[dict[str, str]], divergence: list[dict[str, str]], rescue: list[dict[str, str]], window_ms: float) -> dict[str, Any]:
    source_frame = review.get("source_frame", "")
    idx = next((r for r in index if r.get("source_frame") == source_frame), None)
    center_ts = number((idx or {}).get("capture_timestamp"))
    samples = sample_index(index, center_ts, window_ms)
    candidate_at_center = row_subset(candidates, source_frame)
    candidate_at_center = [r for r in candidate_at_center if r.get("stage") == "candidate_final" and str(r.get("passed", "")).lower() in {"true", "1", "yes"}]
    attempts_center = row_subset(attempts, source_frame)
    tracks_center = row_subset(tracks, source_frame)
    proposals_center = row_subset(proposals, source_frame)
    div_center = [r for r in divergence if r.get("source_frame") == source_frame]
    rescue_row = next((r for r in rescue if r.get("case_id") == review.get("case_id")), {})
    timeline = []
    for sample in samples:
        sf = sample.get("source_frame", "")
        cs = [r for r in row_subset(candidates, sf) if r.get("stage") == "candidate_final" and str(r.get("passed", "")).lower() in {"true", "1", "yes"}]
        ats = row_subset(attempts, sf)
        trs = row_subset(tracks, sf)
        pfs = row_subset(proposals, sf)
        timeline.append({
            "source_frame": sf,
            "capture_timestamp": sample.get("capture_timestamp", ""),
            "video_frame": sample.get("source_video_frame", sample.get("video_frame", "")),
            "gameplay_state": sample.get("gameplay_state", ""),
            "candidate_count": len(cs),
            "track_count": len(trs),
            "pf_count": len(pfs),
        })
    return {
        "case_id": review.get("case_id", ""),
        "evidence_status": "READY" if idx and samples else "NO_VIDEO_EVIDENCE",
        "source_record": {
            "source_frame": source_frame,
            "capture_timestamp": (idx or {}).get("capture_timestamp", ""),
            "source_video_frame": (idx or {}).get("source_video_frame", ""),
            "video_frame": (idx or {}).get("video_frame", ""),
            "gameplay_state": (idx or {}).get("gameplay_state", ""),
            "candidate_ids": [r.get("candidate_id", "") for r in candidate_at_center],
        },
        "inference": {
            "review": review,
            "center_candidates": [{k: r.get(k, "") for k in ("candidate_id", "appearance", "core_bbox", "raw_bbox", "candidate_keys", "lane_span", "score")} for r in candidate_at_center],
            "legacy_assignments": [{k: r.get(k, "") for k in ("track_id", "track_uid", "candidate_id", "assigned", "reject_reason", "total_cost", "competition_track_ids")} for r in attempts_center if r.get("candidate_id")],
            "track_state": [{k: r.get(k, "") for k in ("track_id", "track_uid", "note_uid", "candidate_id", "track_status", "matched_this_frame", "coasting_this_frame", "last_real_observation_timestamp", "state_transition")} for r in tracks_center],
            "pf_proposals": [{k: r.get(k, "") for k in ("old_uid", "track_id", "candidate_id", "decision", "reason", "pf_association_score", "score_margin", "coast_ms", "pf_predicted_y", "pf_sigma_y", "competitor_track_ids", "input_sent")} for r in proposals_center],
            "parity_context": [{k: r.get(k, "") for k in ("edge_case", "source_frame", "target_candidate_id", "replay_track", "root_cause", "confidence")} for r in div_center],
            "parity_detail": div_center,
            "rescue": rescue_row,
            "truth_policy": "Software traces are not game judgment; physical identity and game judgment remain UNKNOWN until human review.",
        },
        "timeline": timeline,
        "media": {"frames": [], "window_ms": window_ms},
    }


def annotate_frame(frame: Any, case: dict[str, Any], sf: str, candidates: list[dict[str, str]], attempts: list[dict[str, str]], tracks: list[dict[str, str]], proposals: list[dict[str, str]]) -> Any:
    import cv2
    image = frame.copy()
    review = case["inference"]["review"]
    target_id = review.get("candidate_id", "")
    for row in [r for r in row_subset(candidates, sf) if r.get("stage") == "candidate_final" and str(r.get("passed", "")).lower() in {"true", "1", "yes"}]:
        bbox = parse_bbox(row.get("core_bbox") or row.get("raw_bbox"))
        if not bbox:
            continue
        x, y, w, h = [int(round(v)) for v in bbox]
        is_target = row.get("candidate_id") == target_id
        color = (0, 0, 255) if is_target else (0, 190, 255)
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 2 if is_target else 1)
        label = f"{row.get('candidate_id','')} {row.get('appearance','')}"
        cv2.putText(image, label[:80], (x, max(12, y - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA)
    # Track/UID annotations are deliberately separate from candidate boxes so
    # the reviewer can see an apparent re-attachment without confusing it with
    # a physical-note judgment.
    for row in row_subset(tracks, sf):
        bbox = parse_bbox(row.get("bbox"))
        if bbox:
            x, y, w, h = [int(round(v)) for v in bbox]
            cv2.rectangle(image, (x, y), (x + w, y + h), (190, 90, 255), 1)
            label = f"T{row.get('track_id','')} {row.get('track_status','')} {row.get('state_transition','')}"
            cv2.putText(image, label[:80], (x, min(image.shape[0] - 5, y + h + 12)), cv2.FONT_HERSHEY_SIMPLEX, .30, (190, 90, 255), 1, cv2.LINE_AA)
    pf_y = []
    for row in row_subset(proposals, sf):
        y = number(row.get("pf_predicted_y"))
        if y is None:
            continue
        sigma = row.get("pf_sigma_y", "")
        pf_y.append(f"{row.get('old_uid','')} y={y:.1f} σ={sigma or 'UNKNOWN'}")
        yi = max(0, min(image.shape[0] - 1, int(round(y))))
        cv2.line(image, (0, yi), (image.shape[1] - 1, yi), (80, 230, 80), 1)
    for i, label in enumerate(pf_y[:3]):
        cv2.putText(image, "PF " + label[:75], (6, 62 + i * 14), cv2.FONT_HERSHEY_SIMPLEX, .30, (80, 230, 80), 1, cv2.LINE_AA)
    y0 = 18
    cv2.rectangle(image, (0, 0), (image.shape[1], 42), (0, 0, 0), -1)
    cv2.putText(image, f"{case['case_id']} frame={sf} target={target_id or 'none'}", (6, y0), cv2.FONT_HERSHEY_SIMPLEX, .42, (255, 255, 255), 1, cv2.LINE_AA)
    center_tracks = row_subset(tracks, sf)
    center_pf = row_subset(proposals, sf)
    cv2.putText(image, f"tracks={len(center_tracks)} PF={len(center_pf)} input_sent=FALSE", (6, y0 + 18), cv2.FONT_HERSHEY_SIMPLEX, .38, (0, 255, 255), 1, cv2.LINE_AA)
    return image


def create_media(case: dict[str, Any], source: Path, index: list[dict[str, str]], candidates: list[dict[str, str]], attempts: list[dict[str, str]], tracks: list[dict[str, str]], proposals: list[dict[str, str]], out: Path) -> None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        case["evidence_status"] = "NO_VIDEO_EVIDENCE:cv2_unavailable"
        return
    samples = [r for r in index if any(t.get("source_frame") == r.get("source_frame") for t in case.get("timeline", []))]
    if not samples or not source.exists():
        return
    cap = cv2.VideoCapture(str(source))
    folder = out / "cases" / case["case_id"] / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    media = []
    for ordinal, sample in enumerate(samples):
        video_frame = number(sample.get("source_video_frame"))
        if video_frame is None:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(video_frame))
        ok, frame = cap.read()
        if not ok:
            continue
        annotated = annotate_frame(frame, case, sample.get("source_frame", ""), candidates, attempts, tracks, proposals)
        left = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
        right = cv2.resize(annotated, (640, 360), interpolation=cv2.INTER_AREA)
        pair = np.concatenate([left, right], axis=1)
        path = folder / f"{ordinal:02d}.jpg"
        cv2.imwrite(str(path), pair, [int(cv2.IMWRITE_JPEG_QUALITY), 68])
        media.append({"source_frame": sample.get("source_frame", ""), "capture_timestamp": sample.get("capture_timestamp", ""), "video_frame": sample.get("source_video_frame", ""), "path": str(path.relative_to(out)).replace("\\", "/")})
    cap.release()
    case["media"]["frames"] = media
    case["media"]["legend"] = "Left: original source frame. Right: candidate/track annotation. Red target, orange other candidates. PF values are shown only when present in trace."
    if not media:
        case["evidence_status"] = "NO_VIDEO_EVIDENCE"


def safe_json(value: Any) -> str:
    # Prevent a trace note or case id from closing the inline script element.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def html_page(cases: list[dict[str, Any]], fields: list[str]) -> str:
    data = safe_json(cases)
    field_json = safe_json(fields)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HoloDream V7.8.8 Visual Identity Review</title>
<style>
body{{font-family:system-ui,sans-serif;background:#10131a;color:#e8edf5;margin:0}} header{{padding:14px 20px;background:#182131;position:sticky;top:0;z-index:2}} h1{{font-size:20px;margin:0 0 4px}} .warn{{color:#ffd166;font-size:13px}} main{{display:grid;grid-template-columns:270px 1fr;gap:16px;padding:16px}} aside,section{{background:#171d29;border:1px solid #2d3a50;border-radius:8px;padding:12px}} select,button,input,textarea{{font:inherit;background:#0e141e;color:#e8edf5;border:1px solid #3a4c68;border-radius:4px;padding:6px}} button{{cursor:pointer}} .toolbar{{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}} .meta{{display:grid;grid-template-columns:repeat(2,minmax(150px,1fr));gap:6px;font-size:13px}} .meta div{{background:#101722;padding:6px;border-radius:4px}} .media{{background:#090d13;text-align:center;padding:8px}} #frame{{max-width:100%;width:1280px}} .caption{{font-size:12px;color:#aebbd0}} label{{display:block;margin:8px 0 3px;font-size:12px;color:#aebbd0}} textarea{{width:100%;box-sizing:border-box;min-height:64px}} .source-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}} pre{{white-space:pre-wrap;word-break:break-word;font-size:11px;max-height:220px;overflow:auto;background:#0c1119;padding:8px}} .status{{font-weight:600}} .ok{{color:#7ee787}} .unknown{{color:#ffd166}} .case-btn{{display:block;width:100%;text-align:left;margin:3px 0}} .active{{border-color:#ffd166;background:#26344b}} .small{{font-size:11px;color:#9baac1}}
</style></head><body><header><h1>HoloDream V7.8.8 — Visual Identity Review</h1><div class="warn">Offline evidence only. Software replay is not physical identity; game judgment remains UNKNOWN unless a human has direct evidence. PF Active is OFF.</div></header>
<main><aside><label for="caseSelect">Case</label><select id="caseSelect"></select><div id="caseList"></div><div class="toolbar"><button id="importBtn">Import completed CSV</button><input id="importFile" type="file" accept=".csv" hidden><button id="exportBtn">Export completed CSV</button></div><div class="small">Import validates case IDs and preserves unknown/ambiguous values. Nothing is written automatically.</div></aside>
<section><div class="toolbar"><button id="prevBtn">◀ previous</button><button id="playBtn">▶ play</button><button id="nextBtn">next ▶</button><label style="display:inline">speed <select id="speed"><option>0.5</option><option selected>1</option><option>2</option><option>4</option></select>x</label></div><div id="title"></div><div class="media"><img id="frame" alt="source and annotated frame"><div id="caption" class="caption"></div></div><div id="meta" class="meta"></div><h3>Manual identity review</h3><div class="source-grid"><div><label>same physical note?</label><select id="identity"><option>UNREVIEWED</option><option>UNKNOWN</option><option>SAME_PHYSICAL_NOTE</option><option>DIFFERENT_PHYSICAL_NOTE</option><option>NOT_A_REAL_NOTE</option><option>AMBIGUOUS</option></select></div><div><label>reviewer confidence</label><select id="confidence"><option>UNKNOWN</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></select></div><div><label>reviewer status</label><select id="reviewerStatus"><option>UNREVIEWED</option><option>REVIEWED</option></select></div><div><label>game judgment (independent)</label><select id="gameJudgment"><option>UNKNOWN</option><option>PERFECT</option><option>GOOD</option><option>MISS</option></select></div></div><label>notes / evidence frames</label><textarea id="notes"></textarea><div class="toolbar"><button id="saveBtn">Save this review in browser</button><span id="saveState" class="small"></span></div><h3>Source record</h3><pre id="sourceRecord"></pre><h3>Inference (read-only)</h3><pre id="inference"></pre></section></main>
<script>
const CASES={data}; const FIELDS={field_json}; let state=structuredClone(CASES); let current=0; let frame=0; let timer=null;
const $=id=>document.getElementById(id); const currentCase=()=>state[current];
function refreshSelect(){{ $('caseSelect').innerHTML=''; state.forEach((c,i)=>{{let o=document.createElement('option');o.value=i;o.textContent=c.case_id+' · '+c.source_record.source_frame; $('caseSelect').appendChild(o)}}); $('caseSelect').value=current; }}
function refreshList(){{ $('caseList').innerHTML=''; state.forEach((c,i)=>{{let b=document.createElement('button');b.className='case-btn'+(i===current?' active':'');b.textContent=c.case_id;b.onclick=()=>{{current=i;frame=0;render()}};$('caseList').appendChild(b)}})}}
function review(c){{return c.inference.review}}
function render(){{let c=currentCase(); let r=review(c); refreshSelect();refreshList(); $('title').textContent=c.case_id+' — '+c.evidence_status; $('identity').value=r.same_physical_note_verdict||'UNKNOWN'; $('confidence').value=r.visual_confidence||'UNKNOWN'; $('reviewerStatus').value=r.reviewer_status||'UNREVIEWED'; $('gameJudgment').value=r.game_judgment||'UNKNOWN'; $('notes').value=r.reviewer_notes||''; $('sourceRecord').textContent=JSON.stringify(c.source_record,null,2); $('inference').textContent=JSON.stringify(c.inference,null,2); let media=c.media.frames||[]; if(media.length){{frame=Math.max(0,Math.min(frame,media.length-1));let m=media[frame];$('frame').src=m.path;$('caption').textContent='source_frame '+m.source_frame+' · capture_timestamp '+m.capture_timestamp+' · video frame '+m.video_frame+' · '+(frame+1)+'/'+media.length}}else{{$('frame').removeAttribute('src');$('caption').textContent='NO_VIDEO_EVIDENCE'}} $('meta').innerHTML='<div><b>frame</b><br>'+esc(c.source_record.source_frame)+'</div><div><b>capture timestamp</b><br>'+esc(c.source_record.capture_timestamp)+'</div><div><b>candidate</b><br>'+esc(r.candidate_id)+'</div><div><b>track / UID</b><br>'+esc(r.old_uid)+'</div><div><b>software</b><br>'+esc(r.software_verdict||'UNKNOWN')+'</div><div><b>game judgment</b><br><span class="unknown">'+esc(r.game_judgment||'UNKNOWN')+'</span></div>'; }}
function esc(v){{let d=document.createElement('div');d.textContent=v??'';return d.innerHTML}}
function save(){{let r=review(currentCase());r.same_physical_note_verdict=$('identity').value;r.visual_confidence=$('confidence').value;r.reviewer_status=$('reviewerStatus').value;r.game_judgment=$('gameJudgment').value;r.reviewer_notes=$('notes').value;$('saveState').textContent='saved in this browser only';render()}}
function csvEscape(v){{v=String(v??'');let needs=v.includes(',')||v.includes('"')||v.includes(String.fromCharCode(10))||v.includes(String.fromCharCode(13));return needs?'"'+v.replaceAll('"','""')+'"':v}}
function exportCsv(){{let lines=[FIELDS.join(',')];state.forEach(c=>{{let r=review(c);lines.push(FIELDS.map(f=>csvEscape(r[f]??'')).join(','))}});let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join(String.fromCharCode(10))],{{type:'text/csv;charset=utf-8'}}));a.download='physical_identity_review_completed.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}}
function parseCsv(text){{let rows=[],row=[],cell='',quoted=false,lf=String.fromCharCode(10),cr=String.fromCharCode(13);for(let i=0;i<text.length;i++){{let ch=text[i],next=text[i+1];if(quoted&&ch==='"'&&next==='"'){{cell+='"';i++;continue}}if(ch==='"'){{quoted=!quoted;continue}}if(ch===','&&!quoted){{row.push(cell);cell='';continue}}if((ch===lf||ch===cr)&&!quoted){{if(ch===cr&&next===lf)i++;row.push(cell);cell='';if(row.some(x=>x!==''))rows.push(row);row=[];continue}}cell+=ch}}row.push(cell);if(row.some(x=>x!==''))rows.push(row);let head=rows.shift()||[];return rows.map(vals=>Object.fromEntries(head.map((h,i)=>[h,vals[i]??''])))}}
function importCsv(text){{let rows=parseCsv(text),byId=new Map(state.map(c=>[c.case_id,c])),seen=new Set(),rejected=0;let ids=new Set(['SAME_PHYSICAL_NOTE','DIFFERENT_PHYSICAL_NOTE','NOT_A_REAL_NOTE','AMBIGUOUS','UNREVIEWED','UNKNOWN']),conf=new Set(['HIGH','MEDIUM','LOW','UNKNOWN']),status=new Set(['REVIEWED','UNREVIEWED']),game=new Set(['PERFECT','GOOD','MISS','UNKNOWN']);rows.forEach(r=>{{let ok=byId.has(r.case_id)&&!seen.has(r.case_id)&&ids.has(r.same_physical_note_verdict)&&conf.has(r.visual_confidence)&&status.has(r.reviewer_status)&&game.has(r.game_judgment);if(!ok){{rejected++;return}}seen.add(r.case_id);Object.assign(review(byId.get(r.case_id)),r)}});render();$('saveState').textContent='imported '+seen.size+' rows; rejected '+rejected+' invalid/unknown IDs or schema rows'}}
function nextFrame(delta){{let n=(currentCase().media.frames||[]).length;if(!n)return;frame=(frame+delta+n)%n;render()}}
$('caseSelect').onchange=e=>{{current=Number(e.target.value);frame=0;render()}};$('prevBtn').onclick=()=>nextFrame(-1);$('nextBtn').onclick=()=>nextFrame(1);$('playBtn').onclick=()=>{{if(timer){{clearInterval(timer);timer=null;$('playBtn').textContent='▶ play'}}else{{timer=setInterval(()=>nextFrame(1),700/Number($('speed').value));$('playBtn').textContent='⏸ pause'}}}};$('saveBtn').onclick=save;$('exportBtn').onclick=exportCsv;$('importBtn').onclick=()=>$('importFile').click();$('importFile').onchange=e=>{{let f=e.target.files[0];if(f)f.text().then(importCsv)}};let requested=new URLSearchParams(location.search).get('case');let requestedIndex=state.findIndex(c=>c.case_id===requested);if(requestedIndex>=0)current=requestedIndex;render();
</script></body></html>'''


def parity_report(divergence: list[dict[str, str]], out: Path) -> None:
    lines = ["# V7.8.8 parity 385/546 visual analysis", "", "The two V7.8.7 replay-extra edges remain visible; no edge is deleted or relabeled as PASS.", "", "| edge | source frame | candidate | replay track | root cause | confidence |", "|---|---:|---|---|---|---|"]
    for center in ("385", "546"):
        row = next((r for r in divergence if r.get("source_frame") == center), {})
        lines.append(f"| {row.get('edge_case','')} | {center} | `{row.get('target_candidate_id','')}` | `{row.get('replay_track','')}` | `{row.get('root_cause','UNKNOWN')}` | `{row.get('confidence','UNKNOWN')}` |")
    lines += ["", "## Evidence interpretation", "", "At each center frame the target candidate is present in the candidate trace, but the retained Live assignment-attempt trace has no matching assignment row for that candidate. The trace contains duplicate pair/assignment rows for other edges. This supports `TRACE_SEMANTICS` as the highest-confidence software explanation, but the original run lacks serialized Tracker/PF snapshots, so a full replay PASS cannot be claimed.", "", "The paired images in `cases/parity_385/` and `cases/parity_546/` show original and annotated source frames. Physical identity and game judgment remain UNKNOWN until human review."]
    (out / "parity_385_546_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def cases_index(cases: list[dict[str, Any]], out: Path) -> None:
    rows = []
    for case in cases:
        cid = html.escape(str(case.get("case_id", "")), quote=True)
        status = html.escape(str(case.get("evidence_status", "")), quote=True)
        frame = html.escape(str(case.get("source_record", {}).get("source_frame", "")), quote=True)
        rows.append(f'<tr><td><a href="../index.html?case={cid}">{cid}</a></td><td>{frame}</td><td>{status}</td><td><a href="{cid}/case.json">case.json</a></td></tr>')
    page = """<!doctype html><meta charset="utf-8"><title>V7.8.8 cases</title><style>body{font-family:system-ui;background:#10131a;color:#e8edf5;padding:20px}a{color:#7dcfff}table{border-collapse:collapse}td,th{border:1px solid #39465c;padding:7px}</style><h1>V7.8.8 visual review cases</h1><p>Open a case in the parent offline review page. Each case folder contains <code>case.json</code> and paired source/annotation frames.</p><table><thead><tr><th>case</th><th>source frame</th><th>evidence</th><th>data</th></tr></thead><tbody>""" + "\n".join(rows) + "</tbody></table>"
    (out / "cases" / "index.html").write_text(page, encoding="utf-8")


def build(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else ROOT / "output" / "run_20261101T034646_232725Z"
    source_results = Path(args.source_results).expanduser().resolve() if args.source_results else ROOT / "output" / "v787_parity_identity"
    out = Path(args.output_dir).expanduser().resolve() if args.output_dir else ROOT / "output" / "v788_visual_identity_review"
    out.mkdir(parents=True, exist_ok=True)
    required = ["live_source.mp4", "live_video_index.csv", "live_candidate_trace.csv", "live_association_attempts.csv", "live_track_identity.csv", "pf_reassociation_proposals.csv", "tap_intents.csv", "live_key_actions.csv"]
    missing = [name for name in required if not (run_dir / name).exists()]
    # If a user has already exported/imported a completed review, use it to
    # populate the page. Otherwise seed from the V7.8.7 review package.
    review_root = out if (out / "physical_identity_review_completed.csv").exists() else source_results
    review_rows = choose_review_rows(review_root)
    index = read_csv(run_dir / "live_video_index.csv")
    candidates = read_csv(run_dir / "live_candidate_trace.csv")
    attempts = read_csv(run_dir / "live_association_attempts.csv")
    tracks = read_csv(run_dir / "live_track_identity.csv")
    proposals = read_csv(run_dir / "pf_reassociation_proposals.csv")
    divergence = read_csv(source_results / "assignment_divergence_385_546.csv")
    rescue = read_csv(source_results / "rescue_identity_case_audit.csv")
    review_rows = add_parity_review_rows(review_rows, divergence, candidates)
    cases = []
    for review in review_rows:
        case = case_data(review, index, candidates, attempts, tracks, proposals, divergence, rescue, float(args.window_before_ms + args.window_after_ms))
        create_media(case, run_dir / "live_source.mp4", index, candidates, attempts, tracks, proposals, out)
        case_dir = out / "cases" / case["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        cases.append(case)
    cases_index(cases, out)
    template_path = out / "physical_identity_review_template.csv"
    if not template_path.exists():
        write_csv(template_path, review_rows, REVIEW_FIELDS)
    # Never replace a manually exported file.  It is accepted as input on a
    # later build and remains a separate artifact from the template.
    completed = out / "physical_identity_review_completed.csv"
    if not completed.exists():
        pass
    (out / "index.html").write_text(html_page(cases, REVIEW_FIELDS), encoding="utf-8")
    parity_report(divergence, out)
    inputs = {name: {"exists": (run_dir / name).exists(), "sha256": digest(run_dir / name) if (run_dir / name).exists() else None, "bytes": (run_dir / name).stat().st_size if (run_dir / name).exists() else None} for name in required}
    result_names = ["physical_identity_review.csv", "rescue_identity_case_audit.csv", "assignment_divergence_385_546.csv", "baseline_parity_semantic.json", "decision_gate.json"]
    result_files = {name: {"exists": (source_results / name).exists(), "sha256": digest(source_results / name) if (source_results / name).exists() else None, "bytes": (source_results / name).stat().st_size if (source_results / name).exists() else None} for name in result_names}
    manifest = {"status": "READY" if not missing else "DATA_UNAVAILABLE", "run_dir": str(run_dir), "source_results": str(source_results), "missing": missing, "input_files": inputs, "source_result_files": result_files, "case_count": len(cases), "case_ids": [c["case_id"] for c in cases], "review_status": "UNREVIEWED/UNKNOWN preserved; completed CSV is user-exported only", "timestamp_policy": "source_frame + capture_timestamp + live_video_index; no frame/60", "active_enabled": False, "game_accuracy": "UNKNOWN"}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "status": manifest["status"], "case_count": len(cases), "missing": missing}, ensure_ascii=False, indent=2))
    return 0 if not missing and len(cases) >= 30 else (0 if not missing else 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    parser.add_argument("--source-results")
    parser.add_argument("--output-dir")
    parser.add_argument("--window-before-ms", type=float, default=500.0)
    parser.add_argument("--window-after-ms", type=float, default=500.0)
    raise SystemExit(build(parser.parse_args()))


if __name__ == "__main__":
    main()
