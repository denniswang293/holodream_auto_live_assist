import csv

from src.live import ASSOCIATION_FIELDS, CsvLog, IDENTITY_FIELDS


def test_identity_transition_csv_accepts_coast_and_reliable_age(tmp_path):
    path = tmp_path / "pf_identity_transitions.csv"
    row = {"physical_note_uid": "physical:1", "track_id": 1,
           "timestamp": 1.0, "from_state": "CONFIRMED_TAP",
           "to_state": "TAP_COASTING", "reason": "no_accepted_measurement",
           "coast_ms": 16.7, "reliable_age_ms": 33.3, "source_frame": 12}
    assert {"coast_ms", "reliable_age_ms"}.issubset(IDENTITY_FIELDS)
    log = CsvLog(path, IDENTITY_FIELDS)
    try:
        log.write(row)
    finally:
        log.close()
    with path.open(newline="", encoding="utf-8-sig") as f:
        saved = next(csv.DictReader(f))
    assert saved["coast_ms"] == "16.7"
    assert saved["reliable_age_ms"] == "33.3"


def test_unknown_association_csv_accepts_source_verdict_fields(tmp_path):
    path = tmp_path / "pf_unknown_association_audit.csv"
    row = {"source_frame": 7, "track_id": 1, "candidate_index": 0,
           "association_accepted": True, "final_reason": "PF_MATCHED_DEGRADED_UNKNOWN",
           "accepted": True, "reason": "PF_MATCHED_DEGRADED_UNKNOWN",
           "association_score": .2, "predicted_y": 170.0,
           "observed_y": 170.2, "coast_ms": 16.7}
    assert {"accepted", "reason"}.issubset(ASSOCIATION_FIELDS)
    log = CsvLog(path, ASSOCIATION_FIELDS)
    try:
        log.write(row)
    finally:
        log.close()
    with path.open(newline="", encoding="utf-8-sig") as f:
        saved = next(csv.DictReader(f))
    assert saved["accepted"] == "True"
    assert saved["reason"] == "PF_MATCHED_DEGRADED_UNKNOWN"
