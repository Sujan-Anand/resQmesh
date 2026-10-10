"""ResQMesh web dashboard + REST API (NiceGUI). Run from the resqmesh folder:   py server/main.py"""

from html import escape
from pathlib import Path

from fastapi import HTTPException
from nicegui import app, ui
from pydantic import BaseModel, Field

import database
import scoring

NAVY = "#0F2A44"
TEAL = "#0B7A6F"

# Colour for each priority level (used by the queue badges and the map markers)
LEVEL_COLORS = {"Critical": "#C62828", "High": "#EF6C00", "Medium": "#F9A825", "Low": "#1976D2"}
RESTORED_COLOR = "#2E7D32"

VELLORE = (12.92, 79.13)

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


def incident_marker(report):
    """How one incident looks on the map: (lat, lng, colour, size, popup text)."""
    # Open incidents are coloured by priority level; restored ones are green
    restored = report["status"] == "Restored"
    color = RESTORED_COLOR if restored else LEVEL_COLORS[report["level"]]
    # escape() stops text typed into a report from being run as HTML in the popup
    popup = (f"<b>{escape(report['asset_type'].title())}</b> - score {report['score']} ({report['level']})"
             f"<br>Status: {escape(report['status'])}"
             f"<br>{escape(report['description'] or '')}")
    return (report["lat"], report["lng"], color, 9, popup)


def crew_marker(crew):
    """How one crew looks on the map: a smaller navy dot."""
    popup = (f"<b>Crew: {escape(crew['name'])}</b>"
             f"<br>{escape(crew['skill'])} - {escape(crew['status'])}"
             f"<br>{crew['hours_worked']} h worked")
    return (crew["lat"], crew["lng"], NAVY, 5, popup)


def legend_dot(color, label, size=14):
    """One coloured dot with a label, for the map legend."""
    with ui.row().classes("items-center gap-1"):
        ui.element("div").style(f"width: {size}px; height: {size}px; border-radius: 50%; background: {color}")
        ui.label(label).classes("text-caption")


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
            counts = [int(field.value or 0) for field in (people, businesses, workers)]
            if min(counts) < 0:
                ui.notify("People, businesses and workers affected cannot be negative", type="warning")
                return
            report = save_report(
                asset_type=asset_type.value, lat=lat.value, lng=lng.value,
                severity=severity.value, description=description.value or "",
                people_affected=counts[0], businesses_affected=counts[1], workers_affected=counts[2],
            )
            ui.notify(f"Report #{report['id']} saved: score {report['score']} ({report['level']})",
                      type="positive")
            add_dialog.close()
            refresh()

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

    @ui.refreshable
    def summary_cards(reports):
        open_reports = [r for r in reports if r["status"] != "Restored"]
        today = database.now()[:10]
        with ui.row():
            summary_card("Critical incidents", sum(r["level"] == "Critical" for r in open_reports), "red")
            summary_card("In progress", sum(r["status"] == "In Progress" for r in reports), "orange")
            summary_card("Restored today",
                         sum((r["restored_at"] or "").startswith(today) for r in reports), "green")
            summary_card("Open incidents", len(open_reports), "blue-grey-9")

    @ui.refreshable
    def priority_queue(reports):
        # Open incidents only, highest score first (reports are already sorted by score)
        # minmax(0, 1fr) lets the text column shrink on phones so the Why? button stays visible
        with ui.grid(columns="44px 70px minmax(0, 1fr) 52px").classes("w-full items-center gap-x-2"):
            for heading in ("Score", "Level", "Incident", ""):
                ui.label(heading).classes("text-bold text-grey-7")
            for report in reports:
                if report["status"] == "Restored":
                    continue
                ui.label(str(report["score"])).classes("text-bold")
                ui.badge(report["level"], color=LEVEL_COLORS[report["level"]])
                with ui.column().classes("gap-0 w-full break-words"):
                    ui.label(f"{report['asset_type'].title()} - {report['status']}").classes("text-bold")
                    ui.label(report["description"]).classes("text-body2")
                ui.button("Why?", on_click=lambda r=report: show_why(r)).props("flat dense")

    # Markers now on the map: key -> (how it looks, map layer)
    markers = {}

    def update_map(reports):
        wanted = {f"report-{r['id']}": incident_marker(r) for r in reports}
        wanted.update({f"crew-{c['id']}": crew_marker(c) for c in database.get_crews()})

        # Take away markers that are gone or look different now.
        # Unchanged markers stay, so an open popup is not closed by the refresh.
        for key in list(markers):
            if wanted.get(key) != markers[key][0]:
                incident_map.remove_layer(markers.pop(key)[1])

        # Draw markers that are new or have changed
        for key, look in wanted.items():
            if key not in markers:
                lat, lng, color, size, popup = look
                # Crews go on a higher map layer, so a redrawn incident marker never hides a crew dot
                pane = "markerPane" if key.startswith("crew-") else "overlayPane"
                layer = incident_map.generic_layer(name="circleMarker", args=[
                    [lat, lng],
                    {"radius": size, "color": "white", "weight": 2, "fillColor": color,
                     "fillOpacity": 0.9, "pane": pane},
                ])
                layer.run_method("bindPopup", popup)  # clicking the marker shows the popup
                markers[key] = (look, layer)

    def refresh():
        """Reload the reports and redraw the cards, the queue and the map."""
        reports = scored_reports()
        summary_cards.refresh(reports)
        priority_queue.refresh(reports)
        update_map(reports)

    def map_ready():
        # Popups can only be attached once the browser has built the map,
        # so the markers are drawn (or redrawn) at that moment
        for _, layer in markers.values():
            incident_map.remove_layer(layer)
        markers.clear()
        update_map(scored_reports())

    with ui.row():
        ui.button("Add report", icon="add", on_click=open_add_form)
        ui.button("Refresh", icon="refresh", on_click=refresh).props("outline")

    reports = scored_reports()
    summary_cards(reports)

    # Queue and map side by side on wide screens, map below the queue on phones
    with ui.element("div").classes("w-full grid grid-cols-1 lg:grid-cols-2 gap-4"):
        with ui.column().classes("w-full min-w-0"):
            ui.label("Priority queue").classes("text-h6")
            with ui.card().classes("w-full").style("max-height: 65vh; overflow-y: auto"):
                priority_queue(reports)
        with ui.column().classes("w-full min-w-0"):
            ui.label("Live incident map").classes("text-h6")
            incident_map = ui.leaflet(center=VELLORE, zoom=12).classes("w-full").style("height: 65vh")
            incident_map.on("init", map_ready)
            with ui.row().classes("gap-4"):
                for level, color in LEVEL_COLORS.items():
                    legend_dot(color, level)
                legend_dot(RESTORED_COLOR, "Restored")
                legend_dot(NAVY, "Crew", size=10)

    # Pick up reports sent from the phones without reloading the page
    ui.timer(10, refresh)


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
# uvicorn_reload_dirs: restart only when server code changes, not when the mobile app is edited or built
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="0.0.0.0", port=8080, title="ResQMesh", show=False, fastapi_docs=True,
           uvicorn_reload_dirs=str(Path(__file__).parent))
