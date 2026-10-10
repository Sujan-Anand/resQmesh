"""Crew-to-incident matching and the decent-work safeguards for crews."""

from collections import Counter
from math import asin, cos, radians, sin, sqrt

from scipy.optimize import linear_sum_assignment

# Shift-hour limits from the brief
SHIFT_LIMIT_HOURS = 12      # at or above this, a crew is blocked from new work
FATIGUE_WARNING_HOURS = 10  # at or above this, a fatigue warning is shown

# Which crew skill each kind of asset needs
SKILL_FOR = {
    "power": "electrical", "telecom": "telecom", "water": "plumbing",
    "road": "civil", "bridge": "civil",
    "hospital": "electrical", "industry": "electrical",
}

# Hazardous jobs need the safety checklist ticked before the assignment is saved
HAZARDOUS = ("power", "bridge", "hospital")
SAFETY_CHECKLIST = ["Power isolated", "Area secured", "Protective gear worn"]

# Added to the cost of a pairing that must not happen (wrong skill, or blocked crew)
PENALTY = 1000


def crew_warning(crew):
    """Return the warning text for a crew, or "" when there is none."""
    if crew["hours_worked"] >= SHIFT_LIMIT_HOURS:
        return "Blocked – shift limit"
    if crew["hours_worked"] >= FATIGUE_WARNING_HOURS:
        return "Fatigue warning"
    return ""


def skill_for(asset_type):
    """The crew skill needed to repair this kind of asset."""
    return SKILL_FOR.get(asset_type)


def is_blocked(crew):
    """Safeguard: a crew at the 12 h shift limit, or off duty, gets no new assignments."""
    return crew["hours_worked"] >= SHIFT_LIMIT_HOURS or crew["status"] == "Off-duty"


def fatigue_warning(crew):
    """Safeguard: a crew at 10 h or more is shown with a fatigue warning."""
    return crew["hours_worked"] >= FATIGUE_WARNING_HOURS


def distance_km(lat1, lng1, lat2, lng2):
    """Straight-line distance between two points on the Earth, in km (haversine formula)."""
    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def assignment_cost(report, crew):
    """Cost of sending this crew to this incident (lower is better)."""
    # cost = distance (km) + 1000 if skill mismatch + 1000 if the crew is blocked by safeguards
    cost = distance_km(report["lat"], report["lng"], crew["lat"], crew["lng"])
    if crew["skill"] != skill_for(report["asset_type"]):
        cost += PENALTY
    if is_blocked(crew):
        cost += PENALTY
    return cost


def suggest_assignments(reports, crews):
    """Suggest the best crew for unassigned incidents.

    `reports` must be sorted highest priority first.
    Returns {report_id: {"crew": crew, "distance_km": km}}.
    """
    waiting = [r for r in reports if r["status"] == "Reported"]
    # Crews already on a job cannot take another one
    crews = [c for c in crews if c["status"] not in ("Assigned", "On-site")]

    # There are usually more incidents than crews. So for each skill, keep only as many
    # incidents as there are usable crews with that skill - the highest-priority ones.
    usable = Counter(c["skill"] for c in crews if not is_blocked(c))
    chosen = []
    for report in waiting:
        skill = skill_for(report["asset_type"])
        if usable[skill] > 0:
            usable[skill] -= 1
            chosen.append(report)
    if not chosen:
        return {}

    # One row per incident, one column per crew; the solver picks the pairing with the lowest total cost
    cost = [[assignment_cost(report, crew) for crew in crews] for report in chosen]
    rows, columns = linear_sum_assignment(cost)

    suggestions = {}
    for row, column in zip(rows, columns):
        # A cost of 1000 or more means wrong skill or blocked crew: never suggest those
        if cost[row][column] < PENALTY:
            suggestions[chosen[row]["id"]] = {
                "crew": crews[column],
                "distance_km": round(cost[row][column], 1),
            }
    return suggestions


def eligible_crews(report, crews):
    """Every crew a supervisor may choose for this incident, nearest first.

    Only free crews with the right skill that are not blocked by the safeguards.
    Returns a list of {"crew": crew, "distance_km": km}.
    """
    options = []
    for crew in crews:
        if (crew["status"] == "Available" and not is_blocked(crew)
                and crew["skill"] == skill_for(report["asset_type"])):
            km = distance_km(report["lat"], report["lng"], crew["lat"], crew["lng"])
            options.append({"crew": crew, "distance_km": round(km, 1)})
    return sorted(options, key=lambda option: option["distance_km"])
