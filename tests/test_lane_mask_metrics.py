import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from evaluate_lane_masks import object_counts, scores


def test_pixel_and_object_metrics_use_explicit_denominators():
    truth = np.zeros((20, 20), bool); truth[4:10, 5:12] = True
    pred = truth.copy(); pred[0, 0] = True
    pixel = scores(truth, pred)
    assert pixel["tp"] == 42 and pixel["fp"] == 1 and pixel["fn"] == 0
    ids = np.zeros((20, 20), np.int32); ids[4:10, 5:12] = 1
    objects = object_counts(ids, [1], pred)
    assert (objects["object_tp"], objects["object_fp"], objects["object_fn"]) == (1, 1, 0)

