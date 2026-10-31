# V7.5.6 五個 Shadow 案例判定

判定只代表 trace 證據；沒有遊戲 Perfect/Great/Miss 真值。

| UID | representative frame | replay track | mapping | verdict | evidence |
|---|---:|---:|---|---|---|
| `cdaf4ddbea12:simple:1000004` | 257 | 5 | HIGH | **MULTIPLE_BLOCKERS** | legacy reasons={'track_not_current_confirmed': 30, 'below_event_min_y': 84, 'eta_outside_horizon': 18, 'particle_posterior_too_wide': 8}; prediction={'prediction_unavailable': 72, 'available': 68}; track statuses={'tentative': 1, 'confirmed': 13, 'lost': 12} |
| `cdaf4ddbea12:simple:1000059` | 615 | 101 | UNKNOWN | **AMBIGUOUS** | legacy reasons={'track_not_current_confirmed': 25, 'below_event_min_y': 76, 'PF_NO_VALID_CROSSING': 2, 'eta_outside_horizon': 9, 'particle_posterior_too_wide': 8}; prediction={'prediction_unavailable': 85, 'available': 35}; track statuses={'tentative': 1, 'confirmed': 9, 'lost': 7} |
| `cdaf4ddbea12:simple:1000139` | 923 | 140 | MEDIUM | **AMBIGUOUS** | legacy reasons={'track_not_current_confirmed': 14, 'below_event_min_y': 86, 'eta_outside_horizon': 17, 'particle_posterior_too_wide': 1}; prediction={'prediction_unavailable': 72, 'available': 46}; track statuses={'tentative': 1, 'confirmed': 6, 'lost': 4} |
| `cdaf4ddbea12:simple:1000140` | 935 | AMBIGUOUS | UNKNOWN | **AMBIGUOUS** | legacy reasons={'track_not_current_confirmed': 51, 'below_event_min_y': 62, 'eta_outside_horizon': 13, 'particle_posterior_too_wide': 4}; prediction={'prediction_unavailable': 81, 'available': 49}; track statuses={'tentative': 1, 'confirmed': 17, 'lost': 16} |
| `cdaf4ddbea12:simple:1000143` | 963 | AMBIGUOUS | UNKNOWN | **AMBIGUOUS** | legacy reasons={'track_not_current_confirmed': 23, 'below_event_min_y': 80, 'eta_outside_horizon': 16, 'particle_posterior_too_wide': 4}; prediction={'prediction_unavailable': 79, 'available': 44}; track statuses={'tentative': 1, 'confirmed': 12, 'lost': 11} |

未使用 `FIRED` 或 `key_down` 當作遊戲命中；沒有足夠身份與單一阻礙證據的案例保持 AMBIGUOUS。
