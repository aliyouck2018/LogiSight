"""Statistical helpers for deterministic analytics (z-score, IQR, rolling mean)."""
from __future__ import annotations

from typing import Sequence


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def zscore(value: float, values: Sequence[float]) -> float:
    """Z-score of value within the sample."""
    s = std(values)
    if s == 0:
        return 0.0
    return (value - mean(values)) / s


def iqr_bounds(values: Sequence[float], k: float = 1.5) -> tuple[float, float]:
    """Tukey IQR fences: values outside [q1 - k*iqr, q3 + k*iqr] are outliers."""
    if not values:
        return (0.0, 0.0)
    vs = sorted(values)
    n = len(vs)

    def percentile(p: float) -> float:
        idx = (n - 1) * p
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return vs[lo] * (1 - frac) + vs[hi] * frac

    q1, q3 = percentile(0.25), percentile(0.75)
    iqr = q3 - q1
    return (q1 - k * iqr, q3 + k * iqr)


def rolling_average(values: Sequence[float], window: int) -> list[float | None]:
    """Simple trailing moving average; None until the window is filled."""
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
        else:
            out.append(mean(values[i + 1 - window:i + 1]))
    return out


def is_anomalous(value: float, values: Sequence[float], threshold: float = 2.0) -> bool:
    """True when value deviates more than `threshold` standard deviations."""
    return abs(zscore(value, values)) > threshold
