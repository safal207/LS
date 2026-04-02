def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def clamp11(value: float) -> float:
    return max(-1.0, min(1.0, value))
