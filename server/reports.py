"""CSV export and the end-of-day restoration summary."""

import csv
import io
from datetime import datetime

import analytics
import assignment
import database
import scoring

STATUSES = ["Reported", "Assigned", "In Progress", "Restored"]


def to_csv(header, rows):
    """Turn a header and a list of rows into CSV text."""
    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(value) for value in row])
    return text.getvalue()


def safe_cell(value):
    """Stop Excel from running typed-in text (like a description starting with =) as a formula."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def incidents():
    """Every incident with its score, level, days down and impact (₹), highest score first."""
    now = datetime.now()  # one moment for every row, so the numbers agree with each other
    rows = []
    for report in database.get_reports():
        scored = scoring.score_report(report)
        scored["days_down"] = analytics.days_down(report, now)
        scored["impact"] = analytics.impact(report, now)
        rows.append(scored)
    return sorted(rows, key=lambda report: report["score"], reverse=True)


def incidents_csv():
    """All incidents, with score, level and impact."""
    columns = ["id", "asset_type", "severity", "status", "score", "level", "description", "lat", "lng",
               "people_affected", "businesses_affected", "workers_affected", "days_down", "impact",
               "created_at", "restored_at"]
    header = [column if column != "impact" else "impact_rupees" for column in columns]
    return to_csv(header, [[report[column] for column in columns] for report in incidents()])


def crews_csv():
    """All crews, with their hours and decent-work warning."""
    header = ["id", "name", "skill", "status", "hours_worked", "warning", "lat", "lng"]
    rows = [[crew["id"], crew["name"], crew["skill"], crew["status"], crew["hours_worked"],
             assignment.crew_warning(crew), crew["lat"], crew["lng"]] for crew in database.get_crews()]
    return to_csv(header, rows)


def assignments_csv():
    """All assignments, with the incident and crew they belong to."""
    report_by_id = {report["id"]: report for report in database.get_reports()}
    crew_by_id = {crew["id"]: crew for crew in database.get_crews()}
    header = ["id", "report_id", "asset_type", "report_status", "crew_id", "crew_name",
              "assigned_at", "safety_checked"]
    rows = []
    for task in sorted(database.get_assignments(), key=lambda task: task["id"]):
        report = report_by_id.get(task["report_id"], {})
        crew = crew_by_id.get(task["crew_id"], {})
        rows.append([task["id"], task["report_id"], report.get("asset_type", ""), report.get("status", ""),
                     task["crew_id"], crew.get("name", ""), task["assigned_at"],
                     "Yes" if task["safety_checked"] else "No"])
    return to_csv(header, rows)


def daily_summary():
    """The numbers for the daily restoration summary."""
    today = database.now()[:10]
    all_incidents = incidents()
    tasks = database.get_assignments()

    by_status = {status: 0 for status in STATUSES}
    for report in all_incidents:
        by_status[report["status"]] = by_status.get(report["status"], 0) + 1

    return {
        "date": today,
        "by_status": by_status,
        "open": len(all_incidents) - by_status["Restored"],
        # Same rule as the dashboard card: restored_at falls on today's date
        "restored_today": sum((report["restored_at"] or "").startswith(today) for report in all_incidents),
        "top5": sorted(all_incidents, key=lambda report: report["impact"], reverse=True)[:5],
        "crew_hours": [{"id": crew["id"], "name": crew["name"], "skill": crew["skill"],
                        "hours_worked": crew["hours_worked"], "warning": assignment.crew_warning(crew)}
                       for crew in database.get_crews()],
        "safety_checklists": sum(1 for task in tasks if task["safety_checked"]),
        "assignments": len(tasks),
    }


def summary_csv():
    """The daily restoration summary as one CSV file, section by section."""
    summary = daily_summary()
    rows = [
        ["Date", summary["date"]],
        [],
        ["Incidents by status"],
        ["Status", "Count"],
        *[[status, count] for status, count in summary["by_status"].items()],
        ["Open (not restored)", summary["open"]],
        [],
        ["Restored today", summary["restored_today"]],
        [],
        ["Top 5 by impact"],
        ["Rank", "Asset type", "Description", "Status", "Days down", "Impact (rupees)"],
        *[[rank, report["asset_type"], report["description"], report["status"], report["days_down"],
           report["impact"]] for rank, report in enumerate(summary["top5"], start=1)],
        [],
        ["Crew hours"],
        ["Crew", "Skill", "Hours worked", "Warning"],
        *[[crew["name"], crew["skill"], crew["hours_worked"], crew["warning"]]
          for crew in summary["crew_hours"]],
        [],
        ["Safety checklists completed", summary["safety_checklists"]],
        ["Assignments made", summary["assignments"]],
        [],
        [analytics.ASSUMPTION],
    ]
    return to_csv(["ResQMesh daily restoration summary"], rows)
