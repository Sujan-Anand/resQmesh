"""Decent-work safeguards for crews. (Crew-to-incident matching is added in the next build step.)"""

# Shift-hour limits from the brief
SHIFT_LIMIT_HOURS = 12      # at or above this, a crew is blocked from new work
FATIGUE_WARNING_HOURS = 10  # at or above this, a fatigue warning is shown


def crew_warning(crew):
    """Return the warning text for a crew, or "" when there is none."""
    if crew["hours_worked"] >= SHIFT_LIMIT_HOURS:
        return "Blocked – shift limit"
    if crew["hours_worked"] >= FATIGUE_WARNING_HOURS:
        return "Fatigue warning"
    return ""
