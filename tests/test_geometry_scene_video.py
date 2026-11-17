from fractions import Fraction

import av
import numpy as np

from tools.geometry_scene.video import VFRVideoWriter


def test_vfr_writer_preserves_irregular_source_timestamps(tmp_path):
    path = tmp_path / "timestamps.mp4"
    times = [0.0, 0.0171234, 0.057]
    frame = np.full((32, 48, 3), 50, dtype=np.uint8)
    with VFRVideoWriter(path, 48, 32, times[-1] - times[-2]) as writer:
        for t in times:
            writer.write(frame, t)
    with av.open(str(path)) as container:
        decoded = list(container.decode(video=0))
        assert len(decoded) == 3
        actual = [f.pts * f.time_base for f in decoded]
        expected = [Fraction(round(t * 90_000), 90_000) for t in times]
        assert actual == expected
        expected_duration = Fraction(round((times[-1] + times[-1] - times[-2]) * 90_000), 90_000)
        assert abs(Fraction(container.duration, av.time_base) - expected_duration) <= Fraction(1, 90_000)
