"""Currency helpers — deterministic conversions only (spec §13)."""


def convert_amount(amount: float, rate: float) -> float:
    """Convert between currencies given an explicit rate (from the FX tool)."""
    return round(amount * rate, 2)


def allocate_budget(total: float, weights: dict[str, float]) -> dict[str, float]:
    """Split a total budget across categories proportionally to weights.

    Rounding residue (from 2-decimal rounding) is added to the largest weight so
    the allocation always sums exactly to `total`.
    """
    if total < 0:
        raise ValueError("total must be non-negative")
    positive = {k: w for k, w in weights.items() if w > 0}
    if not positive:
        raise ValueError("at least one positive weight is required")
    weight_sum = sum(positive.values())
    allocation = {k: round(total * w / weight_sum, 2) for k, w in positive.items()}
    residue = round(total - sum(allocation.values()), 2)
    if residue != 0:
        biggest = max(allocation, key=allocation.get)
        allocation[biggest] = round(allocation[biggest] + residue, 2)
    return allocation
