"""Source-first defaults for the HoloDream Assist runtime.

These values mirror the currently validated JSON defaults.  Geometry remains
an external calibration asset because its y coordinates are still pending
manual validation.
"""
from __future__ import annotations

from copy import deepcopy


DEFAULTS_VERSION = "v7148.1"

CORE_DEFAULTS = {
    "reference_resolution": [720, 404],
    "key_map": ["S", "D", "F", "J", "K", "L"],
    "playfield": {"top_y": 28, "top_left_x": 346, "top_right_x": 374,
                  "hit_y": 352, "bottom_left_x": 36, "bottom_right_x": 684},
    "capture": {"fps_target": 120, "crop_game_window": True},
    "timing": {"offset_ms": 0, "tap_duration_ms": 25},
    "control": {"dry_run": True, "flick_mode": "unverified", "hold_mode": "unverified"},
    "diagnostics": {
        "live_identity_trace": {"enabled": True, "max_queue_rows": 4096,
                                 "max_candidate_rows": 2000, "max_pair_rows": 10000,
                                 "sample_every": 1, "case_frames": []},
        "trace_snapshot": {"enabled": True, "max_rows": 512, "schema_version": "v791.1"},
    },
    "pf_assisted_reassociation": {
        "enabled": False, "mode": "shadow", "offline_only": True,
        "require_real_candidate": True, "allow_coasting_to_fire": False,
        "preserve_hard_gates": True, "min_score_margin": 0.5,
    },
    "detector": {
        "edge_threshold": 65, "min_area": 55, "min_aspect": 2.0,
        "min_score": 0.42, "min_lane_width": 0.7, "min_colored_fraction": 0.12,
        "lane_min_overlap_fraction": 0.15,
        "association_diagnostics": {"enabled": False, "max_candidate_rows": 2000,
                                     "max_pair_rows": 10000},
        "pink_tap": {"enabled": True, "min_mask_fraction": 0.20, "max_core_trim_px": 8},
    },
    "gameplay": {
        "confirm_frames": 3, "hsv_lower": [78, 65, 170], "hsv_upper": [104, 255, 255],
        "min_cyan_fraction": 0.15,
        "hud_regions": {"score": [80, 10, 280, 38], "life": [550, 10, 655, 40],
                         "pause": [675, 10, 710, 50]},
    },
    "tracker": {
        "confirm_observations": 5, "max_missed_frames": 8, "max_gap_s": 0.16,
        "max_u_step": 0.09, "backward_jitter_px": 3.5, "stationary_after_s": 0.20,
        "stationary_span_px": 5, "pink_min_displacement_px": 5, "max_hit_drift_s": 0.08,
        "experimental_local_reassociation": {"enabled": False, "offline_only": True},
    },
    "predictor": {
        "mode": "particle", "window": 11, "min_observations": 5,
        "min_duration_s": 0.05, "min_velocity": 20, "max_velocity": 1800,
        "min_displacement_px": 5, "jitter_px": 3.5, "lookahead_s": 1.5,
        "max_uncertainty_s": 0.04,
        "particle": {
            "count": 128, "ess_resample_fraction": 0.5, "min_real_observations": 4,
            "max_coast_ms": 90, "max_posterior_width_ms": 40,
            "min_valid_crossing_mass": 0.95, "max_prediction_horizon_ms": 1500,
            "use_acceleration": False, "deterministic_seed": 20261030,
            "measurement_model": "student_t", "position_process_noise_px_sqrt_s": 1.8,
            "velocity_process_noise_px_s_sqrt_s": 8.0, "lane_process_noise_sqrt_s": 0.0015,
            "position_measurement_noise_px": 3.0, "lane_measurement_noise": 0.012,
            "observation_gate_px": 32.0, "min_velocity": 20, "max_velocity": 1800,
        },
    },
    "events": {"max_eta_s": 0.45, "min_y": 190, "max_hit_drift_s": 0.06},
}

LIVE_DEFAULTS = {
    "capture_fps": 120, "keyboard_input_mode": "scan_code", "max_frame_age_ms": 60,
    "stale_context_pause_ms": 200, "max_input_lateness_ms": 15, "input_advance_px": 30,
    "tap_deadline_amend": {"enabled": True, "freeze_window_ms": 30,
                            "max_amend_step_ms": 40, "max_total_amend_ms": 80,
                            "allow_earlier_amend": False},
    "simplified_tap_planner": {"enabled": False, "mode": "shadow",
                                "reason": "Keep legacy gates until paired replay confirms no false-positive increase"},
    "linear_timing": {"enabled": False, "mode": "shadow", "window": 5,
                       "min_velocity": 20, "max_observation_age_ms": 200},
    "global_tap_timing": {
        "enabled": True, "mode": "active", "allow_active": True, "min_tracks": 2,
        "min_samples": 3, "history_size": 8, "max_tracks": 32,
        "max_observation_age_ms": 180, "min_velocity": 20, "max_velocity": 1800,
        "max_speed_dispersion": 0.25, "max_jump_px": 80, "max_eta_s": 0.45,
        "measurement_noise_px": 3.0, "max_uncertainty_s": 0.04, "profile_segments": 4,
        "profile_ttl_ms": 3000, "profile_min_samples": 1,
        "timing_reference": "physical_calibrated", "input_lead_ms": 60.0,
        "ab_label": "timing-lead-60ms",
    },
    "judgment_calibration_v2": {"enabled": True, "mode": "shadow",
                                 "min_samples": 20, "offset_ms": 0},
    "hold_tracker_v2": {"enabled": True, "min_head_observations": 2, "dropout_grace_ms": 120},
    "hold_visual": {"enabled": True, "path_appearances": ["green_candidate", "yellow_bar"],
                     "control_rule": "hold_start_key_to_visible_tail", "confirmed_by": "user",
                     "confirmation": "按住起點鍵直到尾端，滑動中不換鍵", "min_path_px": 40,
                     "release_gap_ms": 80, "max_hold_s": 6.0},
    "tap_rule": {"rule": "any_covered_key", "commit_horizon_ms": 100,
                  "geometry_sha256": "e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4",
                  "key_order": ["S", "D", "F", "J", "K", "L"], "confirmed_by": "user",
                  "confirmation_date": "2026-10-28", "confirmation": "範圍內任意一鍵；鍵位是 S D F J K L"},
    "speculative_taps": {"enabled": True, "max_uncertainty_s": 0.1,
                          "max_hit_drift_s": 0.15, "tap_min_hit_observations": 2,
                          "tap_hit_drift_window": 3, "tap_last_chance_single_fit": True},
    "diagnostics": {"timing_ab_label": "timing-lead-60ms"},
}


def builtin_defaults() -> dict:
    """Return a fresh complete configuration tree."""
    result = deepcopy(CORE_DEFAULTS)
    result["live"] = deepcopy(LIVE_DEFAULTS)
    return result
