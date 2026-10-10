"""SQLite database for ResQMesh: reports, crews and assignments."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

# Two separate database files sit next to this file, in the server folder.
# Demo mode only chooses which one the app reads and writes, so real data is never deleted by it.
REAL_DB = Path(__file__).parent / "resqmesh.db"       # real data
DEMO_DB = Path(__file__).parent / "resqmesh_demo.db"  # demo data
SETTINGS_PATH = Path(__file__).parent / "settings.json"  # remembers the Demo mode choice

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Columns that update_crew() is allowed to change
CREW_COLUMNS = ("name", "skill", "lat", "lng", "status", "hours_worked")


def saved_demo_mode():
    """Read the Demo mode choice from settings.json. Default: ON."""
    try:
        return bool(json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))["demo_mode"])
    except (OSError, ValueError, KeyError, TypeError):
        return True  # no settings file yet (or it is unreadable): start in Demo mode


# The database file in use right now
DB_PATH = DEMO_DB if saved_demo_mode() else REAL_DB


def demo_mode():
    """True when the app is using the demo database."""
    return DB_PATH == DEMO_DB


def set_demo_mode(on):
    """Switch between the demo and the real database, and remember the choice."""
    global DB_PATH
    DB_PATH = DEMO_DB if on else REAL_DB
    SETTINGS_PATH.write_text(json.dumps({"demo_mode": bool(on)}, indent=2) + "\n", encoding="utf-8")
    init_db()  # make sure the tables exist in the file now in use


def now():
    """Current local time as text, e.g. 2026-10-10 14:30:00."""
    return datetime.now().strftime(TIME_FORMAT)


def connect(path=None):
    """Open a connection to the database in use (or to `path`). Rows can be turned into dicts."""
    target = Path(path or DB_PATH)
    # A missing or empty file (e.g. deleted while the server runs) gets its tables straight away
    is_new = not target.exists() or target.stat().st_size == 0
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    if is_new:
        conn.executescript(SCHEMA)
        conn.commit()
    return conn


def run(sql, params=(), path=None):
    """Run an INSERT/UPDATE/DELETE, save it, and return the new row id."""
    # closing() makes sure the connection is closed (important on OneDrive)
    with closing(connect(path)) as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def fetch(sql, params=(), path=None):
    """Run a SELECT and return the rows as a list of dicts."""
    with closing(connect(path)) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def init_db(path=None):
    """Create the three tables if they do not exist yet."""
    with closing(connect(path)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


# The three tables from the brief
SCHEMA = """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_type TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                severity INTEGER NOT NULL,          -- 1 to 5
                description TEXT,
                people_affected INTEGER DEFAULT 0,
                businesses_affected INTEGER DEFAULT 0,
                workers_affected INTEGER DEFAULT 0,
                status TEXT DEFAULT 'Reported',     -- Reported / Assigned / In Progress / Restored
                created_at TEXT NOT NULL,
                restored_at TEXT
            );

            CREATE TABLE IF NOT EXISTS crews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                skill TEXT NOT NULL,                -- electrical / civil / telecom / plumbing
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                status TEXT DEFAULT 'Available',    -- Available / Assigned / On-site / Off-duty
                hours_worked REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL REFERENCES reports(id),
                crew_id INTEGER NOT NULL REFERENCES crews(id),
                assigned_at TEXT NOT NULL,
                safety_checked INTEGER DEFAULT 0    -- 1 = safety checklist was ticked
            );
"""


def clear_all(path):
    """Delete every report, crew and assignment in `path`, and start their ids again from 1."""
    # Safety: the real database can never be emptied by this function
    if Path(path).resolve() == REAL_DB.resolve():
        raise ValueError("Refusing to clear the real database")
    with closing(connect(path)) as conn:
        conn.executescript("""
            DELETE FROM assignments;
            DELETE FROM reports;
            DELETE FROM crews;
            DELETE FROM sqlite_sequence WHERE name IN ('assignments', 'reports', 'crews');
        """)
        conn.commit()


# ---------- Reports ----------

def add_report(asset_type, lat, lng, severity, description="",
               people_affected=0, businesses_affected=0, workers_affected=0,
               status="Reported", created_at=None, path=None):
    """Save a new damage report and return its id."""
    return run(
        """INSERT INTO reports (asset_type, lat, lng, severity, description,
                                people_affected, businesses_affected, workers_affected,
                                status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (asset_type, lat, lng, severity, description,
         people_affected, businesses_affected, workers_affected,
         status, created_at or now()),
        path,
    )


def get_reports():
    """All reports, newest first."""
    return fetch("SELECT * FROM reports ORDER BY created_at DESC, id DESC")


def get_report(report_id):
    """One report as a dict, or None if there is no report with this id."""
    rows = fetch("SELECT * FROM reports WHERE id = ?", (report_id,))
    return rows[0] if rows else None


def update_report_status(report_id, status):
    """Move a report along: Reported -> Assigned -> In Progress -> Restored."""
    # Remember when it was restored (used by the analytics and daily summary)
    restored_at = now() if status == "Restored" else None
    run("UPDATE reports SET status = ?, restored_at = ? WHERE id = ?",
        (status, restored_at, report_id))


# ---------- Crews ----------

def add_crew(name, skill, lat, lng, status="Available", hours_worked=0, path=None):
    """Save a new crew and return its id."""
    return run(
        "INSERT INTO crews (name, skill, lat, lng, status, hours_worked) VALUES (?, ?, ?, ?, ?, ?)",
        (name, skill, lat, lng, status, hours_worked),
        path,
    )


def get_crews():
    """All crews, by id."""
    return fetch("SELECT * FROM crews ORDER BY id")


def get_crew(crew_id):
    """One crew as a dict, or None if there is no crew with this id."""
    rows = fetch("SELECT * FROM crews WHERE id = ?", (crew_id,))
    return rows[0] if rows else None


def update_crew(crew_id, **changes):
    """Change crew fields, e.g. update_crew(3, status="Assigned", hours_worked=9.5)."""
    for column in changes:
        if column not in CREW_COLUMNS:
            raise ValueError(f"Unknown crew column: {column}")
    if not changes:
        return
    assignments = ", ".join(f"{column} = ?" for column in changes)
    run(f"UPDATE crews SET {assignments} WHERE id = ?", (*changes.values(), crew_id))


# ---------- Assignments ----------

def add_assignment(report_id, crew_id, safety_checked=False):
    """Link a crew to a report and return the assignment id."""
    return run(
        "INSERT INTO assignments (report_id, crew_id, assigned_at, safety_checked) VALUES (?, ?, ?, ?)",
        (report_id, crew_id, now(), int(safety_checked)),
    )


def get_assignments():
    """All assignments, newest first."""
    return fetch("SELECT * FROM assignments ORDER BY assigned_at DESC, id DESC")
