from bisect import bisect_left

LIMITS = [500, 2000, 10000]  # grams
TIERS = ["letter", "small", "parcel"]


def tier(weight):
    """Shipping tier for an int weight in grams."""
    if weight <= 0:
        raise ValueError(f"weight must be positive: {weight}")
    i = bisect_left(LIMITS, weight)
    if i == len(LIMITS):
        raise ValueError(f"too heavy to ship: {weight} g")
    return TIERS[i]
