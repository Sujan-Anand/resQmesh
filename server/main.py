"""ResQMesh web dashboard + REST API (NiceGUI). Run from the resqmesh folder:   py server/main.py"""

from fastapi import HTTPException
from nicegui import app, ui
from pydantic import BaseModel, Field

import database
import scoring

NAVY = "#0F2A44"
TEAL = "#0B7A6F"

# Badge colour for each priority level
LEVEL_COLORS = {"Critical": "red", "High": "orange", "Medium": "amber-8", "Low": "green"}

# Sidebar links: (label, page address, icon)
NAV_LINKS = [
    ("Dashboard", "/", "dashboard"),
    ("Crews", "/crews", "engineering"),
    ("Analytics", "/analytics", "insights"),
    ("Reports", "/reports", "description"),
]


def scored_reports():
    """All reports with score, level and breakdown, highest score first."""
    reports = [scoring.score_report(report) for report in database.get_reports()]
    return sorted(reports, key=lambda report: report["score"], reverse=True)


def save_report(**fields):
    """Save a new report (from the phone API or the web form) and return it scored."""
    report_id = database.add_report(**fields)
    return next(report for report in scored_reports() if report["id"] == report_id)


# ---------- REST API for the phone app ----------

class NewReport(BaseModel):
    """Fields the phone app sends for a new damage report."""
    asset_type: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    severity: int = Field(ge=1, le=5)
    description: str = ""
    people_affected: int = Field(default=0, ge=0)
    businesses_affected: int = Field(default=0, ge=0)
    workers_affected: int = Field(default=0, ge=0)


@app.post("/api/reports")
def api_add_report(new_report: NewReport):
    # Accept "Power" or " power " from the phone as well as "power"
    new_report.asset_type = new_report.asset_type.strip().lower()
    if new_report.asset_type not in scoring.CRITICALITY:
        raise HTTPException(400, f"asset_type must be one of: {', '.join(scoring.CRITICALITY)}")
    report = save_report(**new_report.model_dump())
    return {"id": report["id"], "score": report["score"], "level": report["level"]}


@app.get("/api/reports")
def api_get_reports():
    return scored_reports()


# ---------- Shared layout ----------

def layout(title):
    """Shared page layout: navy sidebar on the left, page title on the right."""
    # "primary" is the colour NiceGUI uses for buttons, so all buttons become teal
    ui.colors(primary=TEAL)

    with ui.left_drawer(fixed=True).props("width=220").style(f"background-color: {NAVY}"):
        ui.label("ResQMesh").classes("text-white text-h5 text-bold")
        ui.label("Restore what matters first").classes("text-white text-caption q-mb-md")
        for label, target, icon in NAV_LINKS:
            with ui.link(target=target).classes("text-white no-underline w-full"):
                with ui.row().classes("items-center q-py-sm"):
                    ui.icon(icon)
                    ui.label(label).classes("text-subtitle1")

    ui.label(title).classes("text-h4 text-bold").style(f"color: {NAVY}")


def columns(*names):
    """Build simple sortable table columns from field names."""
    return [
        {"name": name, "label": name.replace("_", " ").title(), "field": name,
         "sortable": True, "align": "left"}
        for name in names
    ]


def summary_card(title, value, color):
    """One small card with a big number."""
    with ui.card().classes("w-48"):
        ui.label(title).classes("text-caption text-grey-7")
        ui.label(str(value)).classes(f"text-h4 text-bold text-{color}")


# ---------- Pages ----------

@ui.page("/")
def dashboard_page():
    layout("Dashboard")

    # "Why?" dialog: filled in by show_why() each time a button is clicked
    with ui.dialog() as why_dialog, ui.card().classes("w-96"):
        why_content = ui.column().classes("w-full")

    def show_why(report):
        why_content.clear()
        with why_content:
            ui.label(f"Why {report['score']} / 100?").classes("text-h6")
            ui.label(f"#{report['id']} {report['asset_type']} - {report['description']}").classes("text-caption")
            # One bar per part of the score, filled to points / maximum points
            for part, points in report["breakdown"].items():
                max_points = scoring.MAX_POINTS[part]
                ui.label(f"{part}: {points} / {max_points}").classes("q-mt-sm")
                ui.linear_progress(value=points / max_points, show_value=False, size="12px")
            ui.button("Close", on_click=why_dialog.close).classes("q-mt-md self-end")
        why_dialog.open()

    # "Add report" dialog: same fields as POST /api/reports
    with ui.dialog() as add_dialog, ui.card().classes("w-96"):
        ui.label("Add damage report").classes("text-h6")
        asset_type = ui.select(list(scoring.CRITICALITY), value="power", label="Asset type").classes("w-full")
        ui.label("Severity (1 = minor, 5 = severe)").classes("text-caption")
        severity = ui.toggle([1, 2, 3, 4, 5], value=3)
        description = ui.textarea("Description").props("rows=2").classes("w-full")
        with ui.row().classes("w-full no-wrap"):
            lat = ui.number("Latitude", value=12.92, format="%.4f").classes("w-1/2")
            lng = ui.number("Longitude", value=79.13, format="%.4f").classes("w-1/2")
        people = ui.number("People affected", value=0, min=0, precision=0).classes("w-full")
        with ui.row().classes("w-full no-wrap"):
            businesses = ui.number("Businesses affected", value=0, min=0, precision=0).classes("w-1/2")
            workers = ui.number("Workers affected", value=0, min=0, precision=0).classes("w-1/2")

        def submit():
            if lat.value is None or lng.value is None:
                ui.notify("Please enter latitude and longitude", type="warning")
                return
            if not (-90 <= lat.value <= 90 and -180 <= lng.value <= 180):
                ui.notify("Latitude must be -90 to 90 and longitude -180 to 180", type="warning")
                return
            report = save_report(
                asset_type=asset_type.value, lat=lat.value, lng=lng.value,
                severity=severity.value, description=description.value or "",
                people_affected=int(people.value or 0),
                businesses_affected=int(businesses.value or 0),
                workers_affected=int(workers.value or 0),
            )
            ui.notify(f"Report #{report['id']} saved: score {report['score']} ({report['level']})",
                      type="positive")
            add_dialog.close()
            content.refresh()

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=add_dialog.close).props("flat")
            ui.button("Save report", on_click=submit)

    def open_add_form():
        # Start each new report with a clean form (asset type and location are kept,
        # because a supervisor often enters several reports from the same area)
        severity.value = 3
        description.value = ""
        people.value = 0
        businesses.value = 0
        workers.value = 0
        add_dialog.open()

    with ui.row():
        ui.button("Add report", icon="add", on_click=open_add_form)
        ui.button("Refresh", icon="refresh", on_click=lambda: content.refresh()).props("outline")

    @ui.refreshable
    def content():
        reports = scored_reports()
        open_reports = [r for r in reports if r["status"] != "Restored"]
        today = database.now()[:10]

        with ui.row():
            summary_card("Critical incidents", sum(r["level"] == "Critical" for r in open_reports), "red")
            summary_card("In progress", sum(r["status"] == "In Progress" for r in reports), "orange")
            summary_card("Restored today",
                         sum((r["restored_at"] or "").startswith(today) for r in reports), "green")
            summary_card("Open incidents", len(open_reports), "blue-grey-9")

        # Priority queue: open incidents, highest score first
        ui.label("Priority queue").classes("text-h6 q-mt-md")
        with ui.card().classes("w-full"):
            with ui.grid(columns="60px 90px 90px 1fr 110px 80px").classes("w-full items-center"):
                for heading in ("Score", "Level", "Asset", "Description", "Status", ""):
                    ui.label(heading).classes("text-bold text-grey-7")
                for report in open_reports:
                    ui.label(str(report["score"])).classes("text-bold")
                    ui.badge(report["level"], color=LEVEL_COLORS[report["level"]])
                    ui.label(report["asset_type"].title())
                    ui.label(report["description"])
                    ui.label(report["status"])
                    ui.button("Why?", on_click=lambda r=report: show_why(r)).props("flat dense")

    content()
    # Pick up reports sent from the phones without reloading the page
    ui.timer(15, content.refresh)


@ui.page("/crews")
def crews_page():
    layout("Crews")
    ui.table(
        columns=columns("id", "name", "skill", "status", "hours_worked", "lat", "lng"),
        rows=database.get_crews(),
        row_key="id",
    ).classes("w-full")


@ui.page("/analytics")
def analytics_page():
    layout("Analytics")
    ui.label("Coming soon").classes("text-h5 text-grey")


@ui.page("/reports")
def reports_page():
    layout("Reports")
    ui.label("Coming soon").classes("text-h5 text-grey")


# Make sure the tables exist even if seed.py has not been run yet
database.init_db()

# host 0.0.0.0 lets phones on the same Wi-Fi reach the server
# fastapi_docs=True turns on http://localhost:8080/docs for trying the API
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="0.0.0.0", port=8080, title="ResQMesh", show=False, fastapi_docs=True)
