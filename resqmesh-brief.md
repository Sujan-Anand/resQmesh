# ResQMesh – PySustain-2026 (Track 3)

Hackathon project for PySustain-2026, VIT (BACSE101 – Problem Solving using Python).
Track 3: Building Future-Ready Industries – Infrastructure, Innovation & Decent Work (SDG 8, SDG 9).
24-hour build. Everything must be written in **Python**.

## What ResQMesh does
A decision-support platform for restoring damaged infrastructure after disasters
(roads, bridges, power, telecom, water, hospitals, industries). It answers:
- **What** to restore first (explainable priority scoring)
- **Who** should restore it (skill- and distance-based crew assignment, with crew safety limits)
- **How** teams stay connected when networks fail (store-and-forward mesh messaging)

It is a decision-support prototype, not a replacement for official emergency or utility authorities.

## Project structure
```
resqmesh/
├── server/      # NiceGUI website + dashboard + REST API (runs on the laptop)
│   ├── main.py
│   ├── database.py      # SQLite
│   ├── scoring.py       # priority score + breakdown
│   ├── duplicates.py    # duplicate detection
│   ├── assignment.py    # crew-to-incident matching (scipy)
│   ├── analytics.py     # economic + workforce analytics (pandas)
│   └── demo_data.py     # sample reports, crews, assets
├── mobile/      # Flet app for field crews (built into an Android APK)
│   └── src/main.py
└── mesh/        # laptop mesh node (Bluetooth RFCOMM + Wi-Fi/UDP fallback)
    ├── node.py
    └── bt_transport.py
```

## Environment (important)
- Windows, PowerShell terminal in VS Code.
- Python 3.14. Use `py` instead of `python` (e.g. `py server/main.py`, `py -m pip install ...`).
- Flet 1.0.4: use the `flet` command, not `py -m flet` (`flet run mobile`, `flet run --android mobile`, `flet build apk`).
- Project lives in OneDrive; keep the SQLite DB file small and close connections properly.

## Tech stack
- **Server:** NiceGUI (UI, pages, maps via `ui.leaflet`, charts via `ui.echart`), SQLite (`sqlite3`), pandas, scikit-learn/difflib, scipy.
- **Mobile:** Flet + `requests` ONLY. No pandas/scipy/sklearn in the mobile app.
- **Mesh:** Python built-in `socket` with `AF_BLUETOOTH` / `BTPROTO_RFCOMM` (Windows/Linux), plus a UDP/Wi-Fi fallback with the same message format.

## Server
- Run with `ui.run(host="0.0.0.0", port=8080)` so phones on the same hotspot can reach it.
- Website pages: `/` Home (public intro, Track 3, SDG 8 & 9), `/alerts` (public), `/report` (public form),
  `/dashboard` (supervisors), `/crews` (supervisors).
- REST API for the mobile app and mesh nodes (NiceGUI's `app` is FastAPI):
  - `POST /api/reports` – new damage report
  - `POST /api/checkin` – crew status (Safe / Needs Help / Unreachable)
  - `GET  /api/tasks/{crew_id}` – incidents assigned to a crew
  - `POST /api/tasks/{report_id}/status` – status update
  - `GET  /api/alerts` – active alerts
  - `POST /api/messages` – batch upload of mesh messages (dedupe by message id)

## Database tables
- reports: id, asset_type, lat, lng, severity (1–5), description, people_affected, businesses_affected, status, created_at, merged_into
- crews: id, name, skill, lat, lng, status, hours_worked
- assignments: report_id, crew_id, assigned_at, safety_checked
- messages: msg_id, origin, type, payload, ttl, status, created_at
- alerts: id, zone, message, created_at
- Status workflow: Reported → Verified → Assigned → In Progress → Restored

## Core logic
- **Priority score (0–100, always return the breakdown):**
  - Severity: severity × 8 (max 40)
  - Asset criticality: CRITICALITY[asset_type] × 5 (max 25); hospital 5, power 5, water 4, telecom 4, bridge 3, industry 3, road 2
  - People affected: min(people_affected / 200, 20)
  - Time waiting: min(hours_waiting × 2, 15)
  - Levels: Critical ≥ 75, High ≥ 55, Medium ≥ 35, else Low
- **Duplicates:** same asset_type AND within 500 m (haversine) AND description similarity > 0.6 (difflib.SequenceMatcher).
- **Crew assignment:** cost = distance (km) + 1000 if skill mismatch + 1000 if hours_worked ≥ 12; solve with `scipy.optimize.linear_sum_assignment`. Supervisor can override.
- **Safety:** require a safety checklist before hazardous jobs (power, damaged bridge/structure); block crews over the shift limit.
- **Economic impact:** businesses_affected × avg daily revenue × days down; "Restore First" view sorts by impact.

## Mesh messages
```json
{"id": "uuid", "origin": "crew_03", "type": "report|checkin|status|alert",
 "payload": {}, "ttl": 5, "created_at": "ISO-8601"}
```
Each node keeps an outbox and a set of seen IDs. On contact, nodes exchange outboxes, skip seen IDs,
decrement TTL, and drop messages at TTL 0. Any node that can reach the server POSTs its outbox to `/api/messages`.
Message status: Queued → Relayed → Delivered.

## Mobile app (Flet) screens
1. Report Damage – asset type, severity, description, location (manual first), photo (optional)
2. Crew Check-in – Safe / Needs Help / Unreachable
3. My Tasks – assigned incidents with status buttons
4. Alerts – unsafe zones and critical incidents
5. Messages – queued / relayed / delivered
- Server URL must be configurable in the app (e.g. a settings field), default `http://192.168.x.x:8080`.
- If the server is unreachable, queue the item locally and retry.

## Features by phase
- **During disaster:** mesh messaging, alerts, crew safety check-in, live situation map.
- **After disaster:** damage reporting, priority scoring, duplicate detection, incident map, crew assignment,
  restoration tracking, economic impact analytics, restoration dashboard, workforce analytics, export + lessons learned.
- **Both:** crew management, demo mode (one-click sample data + simulated incoming reports).

## Build order
1. Database + demo data
2. Report form + API + priority scoring
3. Incident queue + live map
4. Crew registry + assignment + safety checks
5. Flet mobile screens connected to the API
6. Mesh messaging + UDP fallback
7. Dashboard, analytics, export
8. Testing, demo mode, pitch

## Coding guidelines
- Keep code simple and readable; the team must be able to explain it to judges.
- Small, working steps: run the app after each change.
- Add short comments on scoring, duplicate detection, assignment and mesh logic.
- Don't add heavy dependencies beyond the stack above without asking.
