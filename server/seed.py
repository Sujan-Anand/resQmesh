"""Create and fill the demo database (server/resqmesh_demo.db) from demo_data.py.

Run from the resqmesh folder:   py server/seed.py
Safe to run twice: if the demo database already has data, nothing is added.
Everything here works on resqmesh_demo.db only. The real database (resqmesh.db) is never touched.
"""

from datetime import datetime, timedelta

import database
from demo_data import DEMO_CREWS, DEMO_REPORTS


def fill_demo_database():
    """Load demo_data.py into resqmesh_demo.db."""
    for report in DEMO_REPORTS:
        data = dict(report)
        # Turn "hours_ago" into a real created_at time
        created = datetime.now() - timedelta(hours=data.pop("hours_ago"))
        database.add_report(**data, created_at=created.strftime(database.TIME_FORMAT), path=database.DEMO_DB)
    for crew in DEMO_CREWS:
        database.add_crew(**crew, path=database.DEMO_DB)


def ensure_demo_database():
    """Create resqmesh_demo.db from demo_data.py if it is missing or empty. Returns True if it was filled."""
    database.init_db(database.DEMO_DB)
    has_reports = database.fetch("SELECT id FROM reports LIMIT 1", path=database.DEMO_DB)
    has_crews = database.fetch("SELECT id FROM crews LIMIT 1", path=database.DEMO_DB)
    if has_reports or has_crews:
        return False
    fill_demo_database()
    return True


def reset_demo_data():
    """Demo reset: empty resqmesh_demo.db and load the demo data again (the starting demo state)."""
    database.init_db(database.DEMO_DB)
    database.clear_all(database.DEMO_DB)
    fill_demo_database()


if __name__ == "__main__":
    if ensure_demo_database():
        print(f"Added {len(DEMO_REPORTS)} reports and {len(DEMO_CREWS)} crews.")
    else:
        print("Demo data already loaded - skipped.")
    print(f"Demo database ready: {database.DEMO_DB}")
