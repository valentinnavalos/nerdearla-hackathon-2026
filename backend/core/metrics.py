"""Audio level, local VAD, latencies and quota — the full set lands in T2.4."""

import math
import sys
from array import array

SILENCE_DBFS = -120.0


def rms_dbfs(pcm: bytes) -> float:
    """RMS level of a PCM16 LE frame in dBFS (0 = full scale)."""
    samples = array("h", pcm[: len(pcm) - len(pcm) % 2])
    if sys.byteorder == "big":
        samples.byteswap()
    if not samples:
        return SILENCE_DBFS
    mean_sq = sum(s * s for s in samples) / len(samples)
    if mean_sq == 0:
        return SILENCE_DBFS
    return 10 * math.log10(mean_sq / 32768**2)
