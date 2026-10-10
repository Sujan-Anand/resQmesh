"""ResQMesh web dashboard + REST API (NiceGUI). Run from the resqmesh folder:   py server/main.py"""

import time
from datetime import datetime
from html import escape
from pathlib import Path

from fastapi import HTTPException
from nicegui import app, ui
from pydantic import BaseModel, Field

import analytics
import assignment
import database
import reports
import scoring
import seed

NAVY = "#0F2A44"
TEAL = "#0B7A6F"

SKILLS = ["electrical", "civil", "telecom", "plumbing"]
CREW_STATUSES = ["Available", "Assigned", "On-site", "Off-duty"]

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
    description: str | None = ""  # the phone may send null for an empty description
    people_affected: int = Field(default=0, ge=0)
    businesses_affected: int = Field(default=0, ge=0)
    workers_affected: int = Field(default=0, ge=0)


@app.post("/api/reports")
def api_add_report(new_report: NewReport):
    # Accept "Power" or " power " from the phone as well as "power"
    new_report.asset_type = new_report.asset_type.strip().lower()
    if new_report.asset_type not in scoring.CRITICALITY:
        raise HTTPException(400, f"asset_type must be one of: {', '.join(scoring.CRITICALITY)}")
    new_report.description = new_report.description or ""
    report = save_report(**new_report.model_dump())
    return {"id": report["id"], "score": report["score"], "level": report["level"]}


@app.get("/api/reports")
def api_get_reports():
    return scored_reports()


@app.get("/api/crews/{crew_id}")
def api_get_crew(crew_id: int):
    """Crew details for the phone app's My Shift screen."""
    crew = database.get_crew(crew_id)
    if crew is None:
        raise HTTPException(404, f"No crew with id {crew_id}")
    # warning is "" when the crew is fine; blocked is True at the 12 h shift limit
    return {
        **crew,
        "warning": assignment.crew_warning(crew),
        "blocked": crew["hours_worked"] >= assignment.SHIFT_LIMIT_HOURS,
    }


def crews_on_a_job():
    """Ids of the crews that have an open task (assigned or in progress)."""
    open_reports = {report["id"] for report in database.get_reports()
                    if report["status"] in ("Assigned", "In Progress")}
    return {task["crew_id"] for task in database.get_assignments() if task["report_id"] in open_reports}


def on_a_job_problem(crew, new_status):
    """A crew that is on a job cannot be marked free by hand. Returns the reason, or ""."""
    if new_status in ("Available", "Off-duty") and crew["id"] in crews_on_a_job():
        return (f"{crew['name']} is on a job. Its status changes by itself "
                f"when the job is started or restored.")
    return ""


def assign_crew(report_id, crew_id, safety_checked):
    """Save a crew assignment. Returns "" when saved, or the reason it was refused."""
    report = database.get_report(report_id)
    crew = database.get_crew(crew_id)
    if report is None or crew is None:
        return "This incident or crew no longer exists"
    if report["status"] != "Reported":
        return "This incident is already assigned"
    # Safeguards: never assign a blocked crew, a busy crew or the wrong skill
    if assignment.is_blocked(crew):
        return f"{crew['name']} is blocked by the shift-hour safeguard"
    if crew["status"] != "Available" or crew_id in crews_on_a_job():
        return f"{crew['name']} is no longer available"
    if crew["skill"] != assignment.skill_for(report["asset_type"]):
        return f"{crew['name']} does not have the skill for {report['asset_type']} work"
    # Hazardous jobs are saved only when the safety checklist was completed
    if report["asset_type"] in assignment.HAZARDOUS and not safety_checked:
        return "The safety checklist must be completed for this job"

    database.add_assignment(report_id, crew_id, safety_checked)
    database.update_report_status(report_id, "Assigned")
    database.update_crew(crew_id, status="Assigned")
    return ""


class TaskStatus(BaseModel):
    """What the phone app sends when a crew updates a task."""
    status: str  # "In Progress" or "Restored"


@app.get("/api/tasks/{crew_id}")
def api_get_tasks(crew_id: int):
    """Open incidents assigned to a crew, for the phone app's My Tasks screen."""
    if database.get_crew(crew_id) is None:
        raise HTTPException(404, f"No crew with id {crew_id}")
    reports = {report["id"]: report for report in scored_reports()}
    tasks = []
    for task in database.get_assignments():
        report = reports.get(task["report_id"])
        if task["crew_id"] == crew_id and report and report["status"] in ("Assigned", "In Progress"):
            tasks.append({**report, "assigned_at": task["assigned_at"],
                          "safety_checked": bool(task["safety_checked"])})
    return sorted(tasks, key=lambda task: task["score"], reverse=True)


@app.post("/api/tasks/{report_id}/status")
def api_set_task_status(report_id: int, update: TaskStatus):
    """A crew moves its task on: Assigned -> In Progress -> Restored."""
    statuses = {"in progress": "In Progress", "restored": "Restored"}
    new_status = statuses.get(update.status.strip().lower())
    if new_status is None:
        raise HTTPException(400, "status must be In Progress or Restored")
    report = database.get_report(report_id)
    if report is None:
        raise HTTPException(404, f"No report with id {report_id}")
    task = next((t for t in database.get_assignments() if t["report_id"] == report_id), None)
    if task is None:
        raise HTTPException(400, "This incident has not been assigned to a crew")
    crew = database.get_crew(task["crew_id"])

    # Sending the same status again (a retry on bad Wi-Fi) changes nothing
    if new_status != report["status"]:
        allowed_from = {"In Progress": ("Assigned",), "Restored": ("Assigned", "In Progress")}
        if report["status"] not in allowed_from[new_status]:
            raise HTTPException(400, f"Cannot change this incident from {report['status']} to {new_status}")
        database.update_report_status(report_id, new_status)  # Restored also sets restored_at
        if crew and new_status == "In Progress":
            database.update_crew(crew["id"], status="On-site")
        elif crew:
            # Restored: free the crew and add the hours spent on this job to its shift hours
            assigned = datetime.strptime(task["assigned_at"], database.TIME_FORMAT)
            hours_spent = max((datetime.now() - assigned).total_seconds() / 3600, 0)
            database.update_crew(crew["id"], status="Available",
                                 hours_worked=round(crew["hours_worked"] + hours_spent, 2))
            crew = database.get_crew(crew["id"])

    return {
        "report_id": report_id,
        "status": new_status,
        "crew_id": task["crew_id"],
        "hours_worked": crew["hours_worked"] if crew else None,
        "warning": assignment.crew_warning(crew) if crew else "",
    }


def shift_limit_problem(hours_worked, status):
    """Safeguard: a crew at the shift limit cannot be put to work. Returns the reason, or ""."""
    if hours_worked >= assignment.SHIFT_LIMIT_HOURS and status in ("Assigned", "On-site"):
        return (f"Blocked: this crew has worked {hours_worked:g} h (shift limit "
                f"{assignment.SHIFT_LIMIT_HOURS} h). Reset hours for a new shift first.")
    return ""


# ---------- Shared layout ----------

def layout(title):
    """Shared page layout: navy sidebar on the left, page title on the right."""
    # "primary" is the colour NiceGUI uses for buttons, so all buttons become teal
    ui.colors(primary=TEAL)

    with ui.left_drawer(fixed=True).props("width=220").style(f"background-color: {NAVY}") as drawer:
        ui.label("ResQMesh").classes("text-white text-h5 text-bold")
        ui.label("Restore what matters first").classes("text-white text-caption q-mb-md")
        for label, target, icon in NAV_LINKS:
            with ui.link(target=target).classes("text-white no-underline w-full"):
                with ui.row().classes("items-center q-py-sm"):
                    ui.icon(icon)
                    ui.label(label).classes("text-subtitle1")

    with ui.row().classes("items-center"):
        # On phones the sidebar is hidden; this button (shown only on narrow screens) opens it
        ui.button("Menu", icon="menu", on_click=drawer.toggle).props("outline dense").classes("lt-md")
        ui.label(title).classes("text-h4 text-bold").style(f"color: {NAVY}")


def summary_card(title, value, color=NAVY):
    """One small card with a big number."""
    with ui.card().classes("w-48"):
        ui.label(title).classes("text-caption text-grey-7")
        ui.label(str(value)).classes("text-h4 text-bold").style(f"color: {color}")


def incident_marker(report):
    """How one incident looks on the map: (lat, lng, colour, size, popup text)."""
    # Open incidents are coloured by priority level; restored ones are green
    restored = report["status"] == "Restored"
    color = RESTORED_COLOR if restored else LEVEL_COLORS[report["level"]]
    # escape() stops text typed into a report from being run as HTML in the popup
    popup = (f"<b>{escape(report['asset_type'].title())}</b> - score {report['score']} ({report['level']})"
             f"<br>Status: {escape(report['status'])}"
             f"<br><span style='overflow-wrap: anywhere'>{escape(report['description'] or '')}</span>")
    return (report["lat"], report["lng"], color, 9, popup)


def crew_marker(crew):
    """How one crew looks on the map: a smaller navy dot."""
    popup = (f"<b>Crew: {escape(crew['name'])}</b>"
             f"<br>{escape(crew['skill'])} - {escape(crew['status'])}"
             f"<br>{crew['hours_worked']:g} h worked")
    warning = assignment.crew_warning(crew)
    if warning:
        popup += f"<br><b>{warning}</b>"
    return (crew["lat"], crew["lng"], NAVY, 5, popup)


def crew_line(crew, km):
    """One line describing a crew for an incident: name · skill · distance km · hours."""
    return f"{crew['name']} · {crew['skill']} · {km} km · {crew['hours_worked']:g} h"


def fatigue_chip(crew):
    """Show the orange fatigue chip when the crew has worked 10 h or more."""
    if assignment.fatigue_warning(crew):
        ui.chip("Fatigue warning", icon="warning", color=LEVEL_COLORS["High"], text_color="white").props("dense")


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
            ui.label(f"#{report['id']} {report['asset_type']} - {report['description']}") \
                .classes("text-caption").style("overflow-wrap: anywhere")
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
            refresh(force=True)

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

    # Safety checklist dialog: hazardous jobs (power, bridge, hospital) are assigned
    # only after all three boxes are ticked
    pending = {"report_id": None, "crew_id": None}  # the assignment waiting for the checklist
    with ui.dialog() as safety_dialog, ui.card().classes("w-96"):
        ui.label("Safety checklist").classes("text-h6")
        safety_text = ui.label().classes("text-body2")
        safety_boxes = [ui.checkbox(item) for item in assignment.SAFETY_CHECKLIST]

        def confirm_safety():
            if not all(box.value for box in safety_boxes):
                ui.notify("Tick all 3 safety checks before assigning", type="warning")
                return
            safety_dialog.close()
            finish_assign(pending["report_id"], pending["crew_id"], safety_checked=True)

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=safety_dialog.close).props("flat")
            ui.button("Confirm and assign", on_click=confirm_safety)

    def start_assign(report, crew):
        """Assign button: hazardous jobs go through the safety checklist first."""
        if report["asset_type"] in assignment.HAZARDOUS:
            pending["report_id"], pending["crew_id"] = report["id"], crew["id"]
            safety_text.text = (f"{report['asset_type'].title()} work is hazardous. Tick all three checks "
                                f"to assign {crew['name']}.")
            for box in safety_boxes:
                box.value = False
            safety_dialog.open()
        else:
            finish_assign(report["id"], crew["id"], safety_checked=False)

    def finish_assign(report_id, crew_id, safety_checked):
        problem = assign_crew(report_id, crew_id, safety_checked)
        if problem:
            ui.notify(problem, type="warning")
        else:
            ui.notify("Crew assigned", type="positive")
        refresh(force=True)

    # "Choose another" dialog: the supervisor overrides the suggestion
    with ui.dialog() as choose_dialog, ui.card().classes("w-96"):
        choose_content = ui.column().classes("w-full")

    def choose_another(report):
        options = assignment.eligible_crews(report, database.get_crews())
        choose_content.clear()
        with choose_content:
            ui.label("Choose a crew").classes("text-h6")
            ui.label(f"#{report['id']} {report['asset_type']} - needs "
                     f"{assignment.skill_for(report['asset_type'])} skill").classes("text-caption")
            if not options:
                ui.label("No free crew with this skill right now.").classes("q-mt-sm")
            for option in options:
                with ui.row().classes("w-full items-center justify-between no-wrap q-mt-sm"):
                    with ui.column().classes("gap-0"):
                        ui.label(crew_line(option["crew"], option["distance_km"])).classes("text-body2")
                        fatigue_chip(option["crew"])
                    ui.button("Assign", on_click=lambda o=option: choose(report, o["crew"])).props("dense")
            ui.button("Cancel", on_click=choose_dialog.close).props("flat").classes("q-mt-md self-end")
        choose_dialog.open()

    def choose(report, crew):
        choose_dialog.close()
        start_assign(report, crew)

    @ui.refreshable
    def summary_cards(reports):
        open_reports = [r for r in reports if r["status"] != "Restored"]
        today = database.now()[:10]
        with ui.row():
            summary_card("Critical incidents", sum(r["level"] == "Critical" for r in open_reports),
                         LEVEL_COLORS["Critical"])
            summary_card("In progress", sum(r["status"] == "In Progress" for r in reports), TEAL)
            summary_card("Restored today",
                         sum((r["restored_at"] or "").startswith(today) for r in reports), RESTORED_COLOR)
            summary_card("Open incidents", len(open_reports))

    def queue_rows(reports):
        """One row per open incident (highest score first) with its suggested or assigned crew."""
        crews = database.get_crews()
        crew_by_id = {crew["id"]: crew for crew in crews}
        assigned_crew = {task["report_id"]: crew_by_id.get(task["crew_id"])
                         for task in database.get_assignments()}
        # Best crew for each unassigned incident (skill, distance and safeguards)
        suggestions = assignment.suggest_assignments(reports, crews)
        return [{"report": report, "suggestion": suggestions.get(report["id"]),
                 "crew": assigned_crew.get(report["id"])}
                for report in reports if report["status"] != "Restored"]

    def queue_signature(rows):
        """Everything the queue shows, except the slowly rising scores."""
        return [(row["report"]["id"], row["report"]["status"], row["report"]["level"],
                 row["report"]["asset_type"], row["report"]["description"],
                 row["suggestion"] and (row["suggestion"]["crew"]["id"], row["suggestion"]["crew"]["name"],
                                        row["suggestion"]["distance_km"],
                                        row["suggestion"]["crew"]["hours_worked"]),
                 row["crew"] and row["crew"]["name"])
                for row in rows]

    @ui.refreshable
    def priority_queue(rows):
        # minmax(0, 1fr) lets the text column shrink on phones so the Why? button stays visible
        with ui.grid(columns="44px 70px minmax(0, 1fr) 52px").classes("w-full items-center gap-x-2"):
            for heading in ("Score", "Level", "Incident", ""):
                ui.label(heading).classes("text-bold text-grey-7")
            for row in rows:
                report, suggestion = row["report"], row["suggestion"]
                ui.label(str(report["score"])).classes("text-bold")
                ui.badge(report["level"], color=LEVEL_COLORS[report["level"]])
                # overflow-wrap: anywhere breaks a very long word (e.g. a pasted link) instead of overflowing
                with ui.column().classes("gap-0 w-full").style("overflow-wrap: anywhere"):
                    ui.label(f"{report['asset_type'].title()} - {report['status']}").classes("text-bold")
                    ui.label(report["description"]).classes("text-body2")
                    if report["status"] == "Reported":
                        if suggestion:
                            crew = suggestion["crew"]
                            ui.label("Suggested crew: " + crew_line(crew, suggestion["distance_km"])) \
                                .classes("text-body2").style(f"color: {TEAL}")
                            fatigue_chip(crew)
                        else:
                            ui.label("Suggested crew: none free right now").classes("text-body2 text-grey-7")
                        with ui.row().classes("gap-2 q-mt-xs"):
                            if suggestion:
                                ui.button("Assign", on_click=lambda r=report, c=crew: start_assign(r, c)) \
                                    .props("dense size=sm")
                            ui.button("Choose another", on_click=lambda r=report: choose_another(r)) \
                                .props("dense outline size=sm")
                    elif row["crew"]:
                        ui.label(f"Crew: {row['crew']['name']}").classes("text-body2").style(f"color: {TEAL}")
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

    # What the queue showed when it was last drawn, and when that was
    drawn = {"signature": None, "at": 0.0}

    def refresh(force=False):
        """Reload the reports and update the cards, the queue and the map."""
        reports = scored_reports()
        rows = queue_rows(reports)
        summary_cards.refresh(reports)
        # A click that lands while the queue is being redrawn is lost. So the queue is redrawn only
        # when something in it changed, or once a minute to show the slowly rising scores.
        signature = queue_signature(rows)
        if force or signature != drawn["signature"] or time.monotonic() - drawn["at"] > 60:
            drawn["signature"], drawn["at"] = signature, time.monotonic()
            priority_queue.refresh(rows)
        update_map(reports)

    def map_ready():
        # Popups can only be attached once the browser has built the map,
        # so the markers are drawn (or redrawn) at that moment
        for _, layer in markers.values():
            incident_map.remove_layer(layer)
        markers.clear()
        update_map(scored_reports())

    # Demo reset: asks first, because it deletes everything
    with ui.dialog() as reset_dialog, ui.card().classes("w-96"):
        ui.label("Reset demo data?").classes("text-h6")
        ui.label("This deletes every report, crew and assignment and loads the demo data again.") \
            .classes("text-body2")

        def reset_demo():
            seed.reset_demo_data()
            reset_dialog.close()
            ui.navigate.reload()  # redraw the whole page from the fresh data

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=reset_dialog.close).props("flat")
            ui.button("Reset demo data", on_click=reset_demo)

    with ui.row().classes("items-center"):
        ui.button("Add report", icon="add", on_click=open_add_form)
        ui.button("Refresh", icon="refresh", on_click=lambda: refresh(force=True)).props("outline")
        with ui.button("Demo", icon="arrow_drop_down").props("outline"):
            with ui.menu():
                ui.menu_item("Reset demo data", on_click=reset_dialog.open)
        if seed.demo_data_loaded():
            ui.badge("DEMO DATA", color=LEVEL_COLORS["Medium"], text_color="black").classes("text-bold q-pa-xs")

    reports = scored_reports()
    summary_cards(reports)
    rows = queue_rows(reports)
    drawn["signature"], drawn["at"] = queue_signature(rows), time.monotonic()

    # Queue and map side by side on wide screens, map below the queue on phones
    with ui.element("div").classes("w-full grid grid-cols-1 lg:grid-cols-2 gap-4"):
        with ui.column().classes("w-full min-w-0"):
            ui.label("Priority queue").classes("text-h6")
            with ui.card().classes("w-full").style("max-height: 65vh; overflow-y: auto"):
                priority_queue(rows)
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

    # Which crew the form is editing; None means the form is adding a new crew
    editing = {"id": None}

    # One form for both "Add crew" and "Edit crew"
    with ui.dialog() as crew_dialog, ui.card().classes("w-96"):
        form_title = ui.label().classes("text-h6")
        name = ui.input("Crew name").classes("w-full")
        skill = ui.select(SKILLS, value=SKILLS[0], label="Skill").classes("w-full")
        status = ui.select(CREW_STATUSES, value="Available", label="Status").classes("w-full")
        with ui.row().classes("w-full no-wrap"):
            lat = ui.number("Latitude", value=VELLORE[0], format="%.4f").classes("w-1/2")
            lng = ui.number("Longitude", value=VELLORE[1], format="%.4f").classes("w-1/2")
        hours = ui.number("Hours worked this shift", value=0, min=0, step=0.5).classes("w-full")

        def save():
            crew_name = (name.value or "").strip()
            hours_worked = float(hours.value or 0)
            if not crew_name:
                ui.notify("Please enter a crew name", type="warning")
                return
            if lat.value is None or lng.value is None:
                ui.notify("Please enter latitude and longitude", type="warning")
                return
            if not (-90 <= lat.value <= 90 and -180 <= lng.value <= 180):
                ui.notify("Latitude must be -90 to 90 and longitude -180 to 180", type="warning")
                return
            if not 0 <= hours_worked <= 24:
                ui.notify("Hours worked must be between 0 and 24", type="warning")
                return
            problem = shift_limit_problem(hours_worked, status.value)
            if not problem and editing["id"] is not None:
                problem = on_a_job_problem({"id": editing["id"], "name": crew_name}, status.value)
            if problem:
                ui.notify(problem, type="warning")
                return

            fields = {"name": crew_name, "skill": skill.value, "status": status.value,
                      "lat": lat.value, "lng": lng.value, "hours_worked": hours_worked}
            if editing["id"] is None:
                database.add_crew(**fields)
                ui.notify(f"Crew {crew_name} added", type="positive")
            else:
                database.update_crew(editing["id"], **fields)
                ui.notify(f"Crew {crew_name} updated", type="positive")
            crew_dialog.close()
            crew_table.refresh()

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=crew_dialog.close).props("flat")
            ui.button("Save crew", on_click=save)

    def find_crew(crew_id):
        """Load a crew for a button click. If it no longer exists, say so and redraw the table."""
        crew = database.get_crew(crew_id)
        if crew is None:
            ui.notify("This crew no longer exists - the list has been refreshed", type="warning")
            crew_table.refresh()
        return crew

    def open_form(crew_id=None):
        """Open the form empty (add) or filled with one crew's details (edit)."""
        crew = find_crew(crew_id) if crew_id else None
        if crew_id and crew is None:
            return
        editing["id"] = crew["id"] if crew else None
        form_title.text = "Edit crew" if crew else "Add crew"
        name.value = crew["name"] if crew else ""
        skill.value = crew["skill"] if crew else SKILLS[0]
        status.value = crew["status"] if crew else "Available"
        lat.value = crew["lat"] if crew else VELLORE[0]
        lng.value = crew["lng"] if crew else VELLORE[1]
        hours.value = crew["hours_worked"] if crew else 0
        crew_dialog.open()

    def change_status(crew_id, new_status):
        crew = find_crew(crew_id)
        if crew is None:
            return
        # Safeguard: a crew at the 12 h shift limit cannot be set to Assigned or On-site,
        # and a crew that is on a job cannot be marked free by hand
        problem = shift_limit_problem(crew["hours_worked"], new_status) or on_a_job_problem(crew, new_status)
        if problem:
            ui.notify(problem, type="warning")
        else:
            database.update_crew(crew_id, status=new_status)
            ui.notify(f"{crew['name']} is now {new_status}", type="positive")
        crew_table.refresh()  # also puts the dropdown back if the change was refused

    def reset_hours(crew_id):
        crew = find_crew(crew_id)
        if crew is None:
            return
        database.update_crew(crew_id, hours_worked=0)
        ui.notify(f"Hours reset for {crew['name']} (new shift)", type="positive")
        crew_table.refresh()

    ui.button("Add crew", icon="add", on_click=lambda: open_form())

    # The crews as last drawn, so the page only redraws when something really changed
    shown = {"crews": None}

    @ui.refreshable
    def crew_table():
        crews = database.get_crews()
        shown["crews"] = crews
        # The card scrolls sideways on narrow screens instead of squashing the columns
        with ui.card().classes("w-full").style("overflow-x: auto"):
            with ui.grid(columns="minmax(130px, 1.3fr) 90px 140px minmax(210px, 1.2fr) 125px 150px") \
                    .classes("w-full items-center gap-x-4").style("min-width: 920px"):
                for heading in ("Name", "Skill", "Status", "Hours worked", "Location", ""):
                    ui.label(heading).classes("text-bold text-grey-7")
                for crew in crews:
                    ui.label(crew["name"]).classes("text-bold")
                    ui.label(crew["skill"].title())
                    ui.select(CREW_STATUSES, value=crew["status"],
                              on_change=lambda e, c=crew: change_status(c["id"], e.value)) \
                        .props("dense outlined").classes("w-full")
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        ui.label(f"{crew['hours_worked']:g} h")
                        # Decent-work warning chip: fatigue at 10 h, blocked at 12 h
                        warning = assignment.crew_warning(crew)
                        if warning:
                            blocked = crew["hours_worked"] >= assignment.SHIFT_LIMIT_HOURS
                            ui.chip(warning, icon="block" if blocked else "warning",
                                    color=LEVEL_COLORS["Critical" if blocked else "High"],
                                    text_color="white").props("dense")
                    ui.label(f"{crew['lat']:.4f}, {crew['lng']:.4f}")
                    with ui.row().classes("gap-1 no-wrap"):
                        ui.button("Edit", on_click=lambda c=crew: open_form(c["id"])).props("flat dense")
                        ui.button("Reset hours", on_click=lambda c=crew: reset_hours(c["id"])).props("flat dense")

    crew_table()

    def refresh_if_changed():
        # Pick up changes made elsewhere (another browser, the phone app) without
        # redrawing every time, which would close a dropdown the supervisor has open
        if database.get_crews() != shown["crews"]:
            crew_table.refresh()

    ui.timer(10, refresh_if_changed)


def rupees(amount):
    """Format a number as rupees, e.g. ₹1,275,000."""
    return f"₹{amount:,.0f}"


@ui.page("/analytics")
def analytics_page():
    layout("Analytics")

    # The assumption behind every rupee figure on this page
    ui.label(analytics.ASSUMPTION).classes("text-subtitle1 text-bold q-pa-sm rounded-borders") \
        .style("background: #FFF8E1; border-left: 4px solid #F9A825")

    def total_card(title, value, note=""):
        with ui.card().classes("min-w-48"):
            ui.label(title).classes("text-caption text-grey-7")
            ui.label(value).classes("text-h4 text-bold").style(f"color: {NAVY}")
            if note:
                ui.label(note).classes("text-caption text-grey-7")

    @ui.refreshable
    def content():
        totals = analytics.totals()
        with ui.row():
            total_card("Businesses affected", f"{totals['businesses_affected']:,}", "by open incidents")
            total_card("Workers affected", f"{totals['workers_affected']:,}", "by open incidents")
            total_card("Total daily loss", rupees(totals["daily_loss"]), "businesses × ₹15,000 per day")
            total_card("Restored vs open", f"{totals['restored']} / {totals['open']}", "restored / still open")

        # Restore First: open incidents ranked by economic impact
        ui.label("Restore First").classes("text-h6 q-mt-md")
        ui.label("Open incidents ranked by impact = businesses × ₹15,000 × days down") \
            .classes("text-caption text-grey-7")
        rows = [{
            "rank": rank,
            "asset": report["asset_type"].title(),
            "description": report["description"],
            "businesses": report["businesses_affected"],
            "workers": report["workers_affected"],
            "days_down": f"{report['days_down']:.2f}",
            "impact": rupees(report["impact"]),
            "status": report["status"],
        } for rank, report in enumerate(analytics.restore_first(), start=1)]
        ui.table(
            columns=[
                {"name": "rank", "label": "#", "field": "rank", "align": "left"},
                {"name": "asset", "label": "Asset", "field": "asset", "align": "left"},
                {"name": "description", "label": "Description", "field": "description", "align": "left"},
                {"name": "businesses", "label": "Businesses", "field": "businesses"},
                {"name": "workers", "label": "Workers", "field": "workers"},
                {"name": "days_down", "label": "Days down", "field": "days_down"},
                {"name": "impact", "label": "Impact (₹)", "field": "impact"},
                {"name": "status", "label": "Status", "field": "status", "align": "left"},
            ],
            rows=rows, row_key="rank",
        ).classes("w-full")

        # Bar chart: one bar per asset type
        ui.label("Impact by asset type").classes("text-h6 q-mt-md")
        ui.label("Economic impact so far, open and restored incidents (₹)").classes("text-caption text-grey-7")
        by_type = analytics.impact_by_asset_type()
        ui.echart({
            "animation": False,
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 90, "right": 20, "top": 30, "bottom": 50},
            # interval 0 = show the name under every bar
            "xAxis": {"type": "category", "data": [asset.title() for asset in by_type],
                      "axisLabel": {"interval": 0, "rotate": 30}},
            "yAxis": {"type": "value", "name": "₹"},
            "series": [{"type": "bar", "data": list(by_type.values()), "itemStyle": {"color": TEAL}}],
        }).classes("w-full h-72")

        # Workforce summary: hours and tasks per crew, and skills in short supply
        ui.label("Workforce summary").classes("text-h6 q-mt-md")
        workforce = analytics.workforce_summary()
        ui.table(
            columns=[
                {"name": "name", "label": "Crew", "field": "name", "align": "left"},
                {"name": "skill", "label": "Skill", "field": "skill", "align": "left"},
                {"name": "status", "label": "Status", "field": "status", "align": "left"},
                {"name": "hours", "label": "Hours worked", "field": "hours"},
                {"name": "tasks_done", "label": "Tasks done", "field": "tasks_done"},
                {"name": "warning", "label": "Warning", "field": "warning", "align": "left"},
            ],
            rows=[{**crew, "hours": f"{crew['hours_worked']:g} h"} for crew in workforce["crews"]],
            row_key="id",
        ).classes("w-full")

        ui.label("Skills in short supply").classes("text-subtitle1 text-bold q-mt-sm")
        if workforce["short_supply"]:
            for item in workforce["short_supply"]:
                ui.chip(f"{item['skill'].title()}: {item['open_incidents']} open incident(s), no crew available",
                        icon="warning", color=LEVEL_COLORS["High"], text_color="white")
        else:
            ui.label("None - every skill needed by an open incident has a crew available.") \
                .classes("text-body2 text-grey-7")

    content()
    # Impact grows with time and changes when incidents are restored, so keep the page current
    ui.timer(10, content.refresh)


def download_csv(text, name):
    """Send CSV text to the browser as a file, e.g. resqmesh_incidents_2026-10-10.csv."""
    filename = f"resqmesh_{name}_{database.now()[:10]}.csv"
    # utf-8-sig lets Excel show ₹ and other non-English characters correctly
    ui.download.content(text.encode("utf-8-sig"), filename, "text/csv")


@ui.page("/reports")
def reports_page():
    layout("Reports")

    # CSV export: each file is built from the database at the moment the button is clicked
    ui.label("Export data").classes("text-h6")
    with ui.row():
        ui.button("Incidents CSV", icon="download",
                  on_click=lambda: download_csv(reports.incidents_csv(), "incidents"))
        ui.button("Crews CSV", icon="download",
                  on_click=lambda: download_csv(reports.crews_csv(), "crews"))
        ui.button("Assignments CSV", icon="download",
                  on_click=lambda: download_csv(reports.assignments_csv(), "assignments"))
    ui.label("Incidents include score, level and economic impact.").classes("text-caption text-grey-7")

    @ui.refreshable
    def summary_section():
        summary = reports.daily_summary()
        ui.label(f"Daily restoration summary - {summary['date']}").classes("text-h6 q-mt-md")

        # Incidents by status, restored today and safety checklists
        with ui.row():
            for status, count in summary["by_status"].items():
                summary_card(status, count)
            summary_card("Restored today", summary["restored_today"], RESTORED_COLOR)
            summary_card("Safety checklists completed", summary["safety_checklists"], TEAL)

        ui.label("Top 5 by impact").classes("text-subtitle1 text-bold q-mt-md")
        ui.table(
            columns=[
                {"name": "rank", "label": "#", "field": "rank", "align": "left"},
                {"name": "asset", "label": "Asset", "field": "asset", "align": "left"},
                {"name": "description", "label": "Description", "field": "description", "align": "left"},
                {"name": "status", "label": "Status", "field": "status", "align": "left"},
                {"name": "days_down", "label": "Days down", "field": "days_down"},
                {"name": "impact", "label": "Impact (₹)", "field": "impact"},
            ],
            rows=[{"rank": rank, "asset": report["asset_type"].title(), "description": report["description"],
                   "status": report["status"], "days_down": f"{report['days_down']:.2f}",
                   "impact": rupees(report["impact"])}
                  for rank, report in enumerate(summary["top5"], start=1)],
            row_key="rank",
        ).classes("w-full")

        ui.label("Crew hours").classes("text-subtitle1 text-bold q-mt-md")
        ui.table(
            columns=[
                {"name": "name", "label": "Crew", "field": "name", "align": "left"},
                {"name": "skill", "label": "Skill", "field": "skill", "align": "left"},
                {"name": "hours", "label": "Hours worked", "field": "hours"},
                {"name": "warning", "label": "Warning", "field": "warning", "align": "left"},
            ],
            rows=[{**crew, "hours": f"{crew['hours_worked']:g} h"} for crew in summary["crew_hours"]],
            row_key="id",
        ).classes("w-full")

    summary_section()
    ui.button("Download summary CSV", icon="download",
              on_click=lambda: download_csv(reports.summary_csv(), "daily_summary")).classes("q-mt-md")

    # Keep the summary current while the page is open
    ui.timer(10, summary_section.refresh)


# Make sure the tables exist even if seed.py has not been run yet
database.init_db()

# host 0.0.0.0 lets phones on the same Wi-Fi reach the server
# fastapi_docs=True turns on http://localhost:8080/docs for trying the API
# uvicorn_reload_dirs: restart only when server code changes, not when the mobile app is edited or built
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="0.0.0.0", port=8080, title="ResQMesh", show=False, fastapi_docs=True,
           uvicorn_reload_dirs=str(Path(__file__).parent))
