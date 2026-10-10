"""Priority scoring: an explainable 0-100 score for every damage report."""

from datetime import datetime

from database import TIME_FORMAT

# How critical each kind of asset is (1-5)
CRITICALITY = {
    "hospital": 5, "power": 5, "water": 4, "telecom": 4,
    "bridge": 3, "industry": 3, "road": 2,
}

# The most points each part of the score can give (adds up to 100)
MAX_POINTS = {
    "Severity": 40,
    "Asset criticality": 25,
    "People affected": 20,
    "Time waiting": 15,
}


def priority(report, hours_waiting):
    """Return (score 0-100, breakdown dict) for one report."""
    # Keep bad input inside its allowed range, so the score always stays 0-100
    severity = min(max(report["severity"], 1), 5)
    people = max(report["people_affected"], 0)
    hours_waiting = max(hours_waiting, 0)

    breakdown = {
        # Severity 1-5, 8 points each (max 40)
        "Severity": severity * 8,
        # Asset criticality 1-5, 5 points each (max 25)
        "Asset criticality": CRITICALITY.get(report["asset_type"], 0) * 5,
        # 1 point per 200 people affected (max 20)
        "People affected": min(people / 200, 20),
        # 2 points per hour the incident has been waiting (max 15)
        "Time waiting": min(hours_waiting * 2, 15),
    }
    breakdown = {part: round(points, 1) for part, points in breakdown.items()}
    score = round(sum(breakdown.values()), 1)
    return score, breakdown


def level(score):
    """Turn a score into a priority level."""
    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def hours_waiting(report):
    """Hours since the report was created (the clock stops once it is restored)."""
    start = datetime.strptime(report["created_at"], TIME_FORMAT)
    if report.get("restored_at"):
        end = datetime.strptime(report["restored_at"], TIME_FORMAT)
    else:
        end = datetime.now()
    return max((end - start).total_seconds() / 3600, 0)


def score_report(report):
    """Return a copy of the report with score, level and breakdown added."""
    score, breakdown = priority(report, hours_waiting(report))
    return {**report, "score": score, "level": level(score), "breakdown": breakdown}
