"""HH:MM time helpers. All itinerary times are "HH:MM" 24h strings."""


def parse_hhmm(value: str) -> int | None:
    """Minutes since midnight, or None for empty/invalid."""
    if not value or ":" not in value:
        return None
    try:
        h, m = value.split(":", 1)
        hours, minutes = int(h), int(m)
    except ValueError:
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def minutes_to_hhmm(total_minutes: int) -> str:
    total_minutes = max(0, total_minutes)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def add_minutes(hhmm: str, minutes: int) -> str | None:
    start = parse_hhmm(hhmm)
    if start is None:
        return None
    return minutes_to_hhmm(start + minutes)


def gap_minutes(end_hhmm: str, start_hhmm: str) -> int | None:
    """Positive minutes between an end and the next start; None if either missing."""
    end, start = parse_hhmm(end_hhmm), parse_hhmm(start_hhmm)
    if end is None or start is None:
        return None
    return start - end
