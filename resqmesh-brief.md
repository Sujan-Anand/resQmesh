# ResQMesh – PySustain-2026 (Track 3)

Hackathon project for PySustain-2026, VIT (BACSE101 – Problem Solving using Python).
Track 3: Building Future-Ready Industries – Infrastructure, Innovation & Decent Work (SDG 8, SDG 9).
24-hour build. Everything must be written in **Python**.

## What ResQMesh does
A decision-support app for restoring damaged infrastructure after disasters
(roads, bridges, power, telecom, water, hospitals, industries). It answers:
- **What** to restore first (explainable priority scoring)
- **Who** should restore it (skill- and distance-based crew assignment, with decent-work safeguards)
- **What it costs** the local economy (economic impact analytics)

It is a decision-support prototype, not a replacement for official emergency or utility authorities.

## Scope – exactly these 8 features (nothing else)
1. **Damage Reporting** – crews report damage from the phone app; supervisors can also add reports on the web.
2. **Smart Priority Scoring** – explainable 0–100 score with a "Why?" breakdown.
3. **Live Incident Map** – incidents on a map, colored by priority.
4. **Crew Management** – crew registry: skills, location, status, hours worked.
5. **Smart Crew Assignment** – best crew per incident by skill and distance.
6. **Decent Work & Safety Safeguards** – shift-hour limits, fatigue blocking, safety checklist for hazardous jobs.
7. **Economic Impact Analytics** – businesses/workers affected, "Restore First" ranking.
8. **Reports & Export** – CSV export and an end-of-day restoration summary.

Out of scope (do NOT build): mesh/Bluetooth/offline relay, duplicate detection, public website pages, alerts/broadcasts, SOS, multilingual.

## Two parts
- **Web dashboard (NiceGUI)** – for supervisors. Runs on the laptop. Features 2–8, plus adding reports.
- **Phone app (Flet)** – for field crews. Feature 1 (Report Damage), My Tasks (see assigned jobs, update status) and My Shift (own hours and fatigue warning).
- Both use one server and one SQLite database. The phone app talks to the server's REST API over the same Wi-Fi/hotspot.

## Project structure
```
resqmesh/
├── server/              # NiceGUI dashboard + REST API (runs on the laptop)
│   ├── main.py          # pages + API endpoints
│   ├── database.py      # SQLite
│   ├── scoring.py       # priority score + breakdown
│   ├── assignment.py    # crew-to-incident matching (scipy) + safeguards
│   ├── analytics.py     # economic + workforce analytics (pandas)
│   ├── reports.py       # CSV export + daily summary
│   ├── demo_data.py     # sample reports and crews
│   └── seed.py          # create + fill the database
└── mobile/              # Flet app for field crews (built into an Android APK)
    └── src/main.py
```

## Environment (important)
- Windows, PowerShell terminal in VS Code.
- Python 3.14. Use `py` instead of `python` (e.g. `py server/main.py`, `py -m pip install ...`).
- Flet 1.0.4: use the `flet` command, not `py -m flet` (`flet run mobile`, `flet run --android mobile`, `flet build apk`).
- Project lives in OneDrive; keep the SQLite DB file small and close connections properly.

## Tech stack
- **Server:** NiceGUI (pages, `ui.leaflet` map, `ui.echart` charts, `ui.table`, `ui.dialog`), SQLite (`sqlite3`), pandas, scipy.
- **Mobile:** Flet + `requests` ONLY. No pandas/scipy in the mobile app.

## Server
- Run with `ui.run(host="0.0.0.0", port=8080, title="ResQMesh")` so phones on the same Wi-Fi can reach it.
- Dashboard pages (left sidebar): `/` Dashboard (summary cards + priority queue + map), `/crews`, `/analytics`, `/reports`.
- REST API for the phone app (NiceGUI's `app` is FastAPI):
  - `POST /api/reports` – new damage report, returns id, score and level
  - `GET  /api/reports` – all reports with score and level
  - `GET  /api/crews/{crew_id}` – crew details incl. hours worked and warnings
  - `GET  /api/tasks/{crew_id}` – incidents assigned to a crew
  - `POST /api/tasks/{report_id}/status` – crew updates status

## Database tables
- reports: id, asset_type, lat, lng, severity (1–5), description, people_affected, businesses_affected, workers_affected, status, created_at, restored_at
- crews: id, name, skill, lat, lng, status (Available / Assigned / On-site / Off-duty), hours_worked
- assignments: id, report_id, crew_id, assigned_at, safety_checked
- Status workflow: Reported → Assigned → In Progress → Restored

## Core logic
- **Priority score (0–100, always return the breakdown):**
  - Severity: severity × 8 (max 40)
  - Asset criticality: CRITICALITY[asset_type] × 5 (max 25); hospital 5, power 5, water 4, telecom 4, bridge 3, industry 3, road 2
  - People affected: min(people_affected / 200, 20)
  - Time waiting: min(hours_waiting × 2, 15)
  - Levels: Critical ≥ 75, High ≥ 55, Medium ≥ 35, else Low
- **Crew assignment:** cost = distance (km) + 1000 if skill mismatch + 1000 if the crew is blocked by safeguards; solve with `scipy.optimize.linear_sum_assignment`. Supervisor can accept or override.
  Skill map: power→electrical, telecom→telecom, water→plumbing, road/bridge→civil, hospital→electrical, industry→electrical.
- **Decent work & safety safeguards:**
  - Shift limit 12 h: crews at ≥ 12 h are blocked from new assignments; ≥ 10 h shows a fatigue warning.
  - Hazardous jobs (power, bridge, hospital) need a 3-item safety checklist ticked before the assignment is saved.
  - Show each crew's hours and warnings on the Crews page and in the phone app.
- **Economic impact:** impact (₹) = businesses_affected × 15000 (avg daily revenue, labelled as an assumption) × days_down; also show workers_affected. "Restore First" sorts open incidents by impact.
- **Reports & export:** CSV export of incidents, crews and assignments; a daily summary (incidents by status, restored today, top 5 by impact, crew hours).

## Phone app (Flet) screens
1. Report Damage – asset type tiles, severity 1–5 buttons, description, location (manual lat/lng or a preset area), people/businesses affected.
2. My Tasks – assigned incidents with Start / Restored buttons.
3. My Shift – hours worked and fatigue warning.
- Server URL and crew ID are set in a Settings field (default server `http://192.168.x.x:8080`).
- If the server can't be reached, show a clear error and keep the form filled so the crew can retry.

## Build order
1. Database + demo data
2. Dashboard skeleton
3. Scoring + report API + priority queue; phone Report Damage screen
4. Live incident map
5. Crew management
6. Crew assignment + safety safeguards; phone My Tasks + My Shift
7. Economic impact analytics
8. Reports & export
9. Testing, demo reset, pitch

## Coding guidelines
- Keep code simple and readable; the team must be able to explain it to judges.
- Small, working steps: run the app after each change.
- Add short comments on scoring, assignment, safeguards and impact logic.
- Don't add features outside the 8 in scope. Don't add heavy dependencies.
