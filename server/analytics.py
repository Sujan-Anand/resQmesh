"""Economic impact and workforce analytics (pandas)."""

from collections import Counter
from datetime import datetime

import pandas as pd

import assignment
import database
from scoring import CRITICALITY

# Assumption, shown on the Analytics page: what one business earns in a day
AVG_DAILY_REVENUE = 15000
ASSUMPTION = "Assumption: average daily revenue ₹15,000 per business"

REPORT_COLUMNS = ["id", "asset_type", "lat", "lng", "severity", "description", "people_affected",
                  "businesses_affected", "workers_affected", "status", "created_at", "restored_at"]
ASSIGNMENT_COLUMNS = ["id", "report_id", "crew_id", "assigned_at", "safety_checked"]


def days_down(report, now=None):
    """Days the asset has been down: from created_at to now, or to restored_at."""
    start = datetime.strptime(report["created_at"], database.TIME_FORMAT)
    if report["restored_at"]:
        end = datetime.strptime(report["restored_at"], database.TIME_FORMAT)
    else:
        end = now or datetime.now()
    return round(max((end - start).total_seconds() / 86400, 0), 2)


def impact(report, now=None):
    """Economic impact of one incident in rupees."""
    # impact (₹) = businesses_affected × 15000 (avg daily revenue, an assumption) × days_down
    return round(report["businesses_affected"] * AVG_DAILY_REVENUE * days_down(report, now))


def reports_with_impact():
    """All reports as a pandas table, with days_down and impact (₹) added."""
    now = datetime.now()  # one moment for every row, so the numbers agree with each other
    rows = [{**report, "days_down": days_down(report, now), "impact": impact(report, now)}
            for report in database.get_reports()]
    return pd.DataFrame(rows, columns=REPORT_COLUMNS + ["days_down", "impact"])


def restore_first():
    """Open incidents sorted by economic impact, highest first (restored ones are left out)."""
    table = reports_with_impact()
    still_open = table[table["status"] != "Restored"]
    ranked = still_open.sort_values(["impact", "businesses_affected"], ascending=False)
    return ranked.to_dict("records")


def totals():
    """Headline numbers: businesses and workers affected, daily loss, restored vs open."""
    table = reports_with_impact()
    still_open = table[table["status"] != "Restored"]
    businesses = int(still_open["businesses_affected"].sum())
    return {
        "businesses_affected": businesses,
        "workers_affected": int(still_open["workers_affected"].sum()),
        # What the local economy loses every day while these incidents stay open
        "daily_loss": businesses * AVG_DAILY_REVENUE,
        "restored": int((table["status"] == "Restored").sum()),
        "open": len(still_open),
    }


def impact_by_asset_type():
    """Total impact (₹) so far for each asset type, as {asset_type: rupees}. Every type gets a bar."""
    table = reports_with_impact()
    by_type = table.groupby("asset_type")["impact"].sum().reindex(list(CRITICALITY), fill_value=0)
    return {asset_type: int(rupees) for asset_type, rupees in by_type.items()}


def workforce_summary():
    """Per crew: hours worked and tasks done. Plus the skills that are in short supply."""
    crews = database.get_crews()
    reports = pd.DataFrame(database.get_reports(), columns=REPORT_COLUMNS)
    tasks = pd.DataFrame(database.get_assignments(), columns=ASSIGNMENT_COLUMNS)

    # Tasks done = assignments whose incident has been restored, counted per crew
    joined = tasks.merge(reports[["id", "status"]], left_on="report_id", right_on="id", suffixes=("", "_report"))
    done = joined[joined["status"] == "Restored"].groupby("crew_id").size()
    crew_rows = [{
        "id": crew["id"],
        "name": crew["name"],
        "skill": crew["skill"],
        "status": crew["status"],
        "hours_worked": crew["hours_worked"],
        "tasks_done": int(done.get(crew["id"], 0)),
        "warning": assignment.crew_warning(crew),
    } for crew in crews]

    # Short supply = unassigned incidents need a skill, but no crew with that skill is free
    waiting = reports[reports["status"] == "Reported"]
    needed = waiting["asset_type"].map(assignment.skill_for).value_counts()
    free = Counter(crew["skill"] for crew in crews
                   if crew["status"] == "Available" and not assignment.is_blocked(crew))
    short_supply = [{"skill": skill, "open_incidents": int(count)}
                    for skill, count in needed.items() if free[skill] == 0]

    return {"crews": crew_rows, "short_supply": short_supply}
