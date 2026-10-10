"""Create the database and load the demo data.

Run from the resqmesh folder:   py server/seed.py
Safe to run twice: if the tables already have data, nothing is added.
"""

from datetime import datetime, timedelta

import database
from demo_data import DEMO_CREWS, DEMO_REPORTS


def seed():
    database.init_db()

    # Only fill empty tables, so running this again never creates duplicates
    if database.get_reports():
        print("Reports already loaded - skipped.")
    else:
        for report in DEMO_REPORTS:
            data = dict(report)
            # Turn "hours_ago" into a real created_at time
            created = datetime.now() - timedelta(hours=data.pop("hours_ago"))
            database.add_report(**data, created_at=created.strftime(database.TIME_FORMAT))
        print(f"Added {len(DEMO_REPORTS)} reports.")

    if database.get_crews():
        print("Crews already loaded - skipped.")
    else:
        for crew in DEMO_CREWS:
            database.add_crew(**crew)
        print(f"Added {len(DEMO_CREWS)} crews.")

    print(f"Database ready: {database.DB_PATH}")


if __name__ == "__main__":
    seed()
