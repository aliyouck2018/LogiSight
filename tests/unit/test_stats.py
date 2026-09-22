"""Unit tests for statistical helpers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.stats import (iqr_bounds, is_anomalous, mean, rolling_average,
                                 std, zscore)


def test_mean():
    assert mean([2, 4, 6]) == 4.0


def test_std():
    assert std([2, 4, 6]) == 2.0


def test_zscore():
    assert zscore(6, [2, 4, 6]) == 1.0


def test_iqr_bounds_outlier_detection():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 5 + [1000]
    lo, hi = iqr_bounds(values[:-1])
    assert values[-1] > hi  # the 1000 lies above the upper fence


def test_rolling_average_window():
    result = rolling_average([1, 2, 3, 4], 2)
    assert result[0] is None
    assert result[1] == 1.5
    assert result[3] == 3.5


def test_is_anomalous():
    assert is_anomalous(100, [1, 2, 3, 4, 5])
    assert not is_anomalous(3, [1, 2, 3, 4, 5])
