# ResQMesh – build prompts by phase (for A)

Scope: the 8 features in resqmesh-brief.md only. No mesh, no duplicates, no public pages.

How to use:
- Paste one prompt at a time into Claude Code.
- At the end of each phase, run every check. Move on only when all pass.
- If a check fails, use the "When something breaks" prompt at the end.
- Push after every phase:  git add -A  →  git commit -m "Phase N done"  →  git push

---

## PHASE 1 · Foundation (hour 0–2)

### Prompt 1 – Database and demo data
```
Read resqmesh-brief.md first and follow it exactly.

Create:
1. server/database.py – SQLite database (resqmesh.db in the server folder) with the tables reports, crews and assignments as described in the brief. Add simple helper functions: init_db(), add_report(), get_reports(), update_report_status(), add_crew(), get_crews(), update_crew(), add_assignment(), get_assignments().
2. server/demo_data.py – about 20 realistic damage reports around Vellore, Tamil Nadu (mix of power, bridge, road, water, telecom, hospital, industry; severities 1–5; lat/lng near 12.92 N, 79.13 E; realistic people, businesses and workers affected; some created a few hours ago) and 8 crews with different skills (electrical, civil, telecom, plumbing), locations and hours_worked (include one at 11 h and one at 12 h).
3. server/seed.py – creates the database and loads the demo data. Running it twice must not create duplicates.

Keep the code simple with short comments. Tell me the exact command to run it on Windows (I use py, not python).
```

### Prompt 2 – Dashboard skeleton
```
Read resqmesh-brief.md first.

Create server/main.py with NiceGUI:
- ui.run(host="0.0.0.0", port=8080, title="ResQMesh")
- A shared layout: navy left sidebar (#0F2A44) with links Dashboard, Crews, Analytics, Reports; content area on the right; teal (#0B7A6F) buttons.
- Pages: / (Dashboard), /crews, /analytics, /reports. For now / shows a table of all reports, /crews a table of crews, and the other two a "coming soon" heading.

Tell me how to run it and which URL to open.
```

### ✅ Phase 1 checks
- [ ] `py server/seed.py` runs with no red errors, and `server/resqmesh.db` exists.
- [ ] Run it again: still about 20 reports and 8 crews, no duplicates.
- [ ] `py server/main.py` starts; `http://localhost:8080` shows the reports table.
- [ ] `/crews` shows 8 crews; sidebar links switch pages.
- [ ] A phone on the same Wi-Fi opens `http://<laptop-IP>:8080` (find the IP with `ipconfig`; allow Python in the firewall popup).
- [ ] Pushed to GitHub; B, C and D ran `git pull`.

---

## PHASE 2 · Damage Reporting + Smart Priority Scoring (hour 2–6)

### Prompt 3 – Scoring, report API and priority queue
```
Read resqmesh-brief.md first.

1. Create server/scoring.py with priority(report, hours_waiting) returning (score 0–100, breakdown dict) exactly as in the brief, and level(score) returning Critical / High / Medium / Low.
2. In server/main.py add the endpoints POST /api/reports (returns id, score, level) and GET /api/reports (all reports with score and level).
3. Change the Dashboard page to:
   - summary cards: Critical incidents, In progress, Restored today, Open incidents
   - a priority queue sorted by score: score, colored level badge, asset type, description, status, and a "Why?" button that opens a dialog with the four breakdown parts as small bars
   - an "Add report" button that opens a form (same fields as the API) for supervisors.

Add a tiny test I can run with py to check scoring gives sensible numbers.
```

### ✅ Phase 2 checks
- [ ] Scoring test passes: a severity-5 hospital report scores higher than a severity-2 road report.
- [ ] Every score is 0–100, and the four "Why?" parts add up to the score.
- [ ] Queue is sorted highest first with Critical / High / Medium / Low badges.
- [ ] "Add report" on the web saves a report and it appears in the queue.
- [ ] `http://localhost:8080/docs` → POST /api/reports returns id, score and level.
- [ ] C's phone Report Damage screen sends a report that appears in the queue.
- [ ] Pushed to GitHub.

---

## PHASE 3 · Live Incident Map + Crew Management (hour 6–10)

### Prompt 4 – Live incident map
```
Read resqmesh-brief.md first.

Add a live incident map to the Dashboard page with ui.leaflet, centred on Vellore:
- one marker per open incident, colored by level (Critical red, High orange, Medium amber, Restored green)
- clicking a marker shows asset type, score, status and description
- crews shown as small separate markers
- the map and the queue refresh every 10 seconds so new reports appear without reloading
Put the map beside the queue on wide screens and below it on phones.
```

### Prompt 5 – Crew management
```
Read resqmesh-brief.md first.

Build the /crews page:
- table of crews: name, skill, status, hours worked, location
- hours shown with a warning chip: "Fatigue warning" at 10 h or more, "Blocked – shift limit" at 12 h or more
- buttons to add a crew, edit a crew, change status (Available / Assigned / On-site / Off-duty) and reset hours for a new shift
Add GET /api/crews/{crew_id} returning the crew with hours_worked and its warning, for the phone app's My Shift screen.
```

### ✅ Phase 3 checks
- [ ] The map shows every open incident with the right color.
- [ ] Clicking a marker shows its details.
- [ ] A report sent from the phone appears on the map within about 10 seconds, without reloading.
- [ ] Crew page shows 8 crews; the 11 h crew has a fatigue warning, the 12 h crew is shown as blocked.
- [ ] Adding, editing and changing a crew's status works and survives a page reload.
- [ ] GET /api/crews/{crew_id} returns hours and warning.
- [ ] Pushed to GitHub.

---

## PHASE 4 · Smart Crew Assignment + Decent Work & Safety Safeguards (hour 10–14)

### Prompt 6 – Assignment and safeguards
```
Read resqmesh-brief.md first.

Create server/assignment.py:
- skill_for(asset_type) using the skill map in the brief
- is_blocked(crew) – True at 12 h or more, or status Off-duty; fatigue_warning(crew) – True at 10 h or more
- suggest_assignments(reports, crews) using scipy.optimize.linear_sum_assignment with cost = distance km + 1000 skill mismatch + 1000 blocked. Never return a blocked crew or a mismatched skill.

In the Dashboard queue, each unassigned incident shows "Suggested crew: name · skill · distance km · hours" with Assign and Choose another buttons.
For hazardous jobs (power, bridge, hospital), Assign first opens a safety checklist dialog with 3 checkboxes (power isolated / area secured / protective gear worn); the assignment saves only when all are ticked, and safety_checked is stored.
Assigning sets the report to Assigned and the crew to Assigned.

Add endpoints GET /api/tasks/{crew_id} and POST /api/tasks/{report_id}/status (In Progress / Restored). When a task is Restored, set restored_at, free the crew, and add the hours spent to hours_worked.
```

### ✅ Phase 4 checks
- [ ] Power incidents get an electrical crew suggested; bridges get civil.
- [ ] The 12 h crew is never suggested; the 11 h crew shows a fatigue warning when suggested.
- [ ] Assigning a power, bridge or hospital job opens the safety checklist and saves only when all 3 are ticked.
- [ ] After assigning, the incident shows Assigned and the crew shows Assigned.
- [ ] C's My Tasks screen shows the assigned job; Start → Restored on the phone updates the dashboard and map.
- [ ] C's My Shift screen shows hours and the fatigue warning.
- [ ] Pushed to GitHub.

---

## PHASE 5 · Economic Impact Analytics + Reports & Export (hour 14–18)

### Prompt 7 – Economic impact analytics
```
Read resqmesh-brief.md first.

Create server/analytics.py with pandas:
- impact(report) = businesses_affected × 15000 × days_down (days_down from created_at to now, or to restored_at)
- restore_first() – open incidents sorted by impact, highest first
- totals() – businesses affected, workers affected, total daily loss in ₹, restored vs open
- workforce_summary() – per crew: hours worked, tasks done; and skills in short supply (open incidents needing a skill with no available crew)

Build the /analytics page: total cards, a "Restore First" table, a bar chart of impact by asset type (ui.echart), and the workforce summary. Show "Assumption: average daily revenue ₹15,000 per business" clearly on the page.
```

### Prompt 8 – Reports and export
```
Read resqmesh-brief.md first.

Create server/reports.py and build the /reports page:
- buttons to download CSV files of incidents (with score, level, impact), crews and assignments
- a "Daily restoration summary" section: incidents by status, restored today, top 5 by impact, crew hours, safety checklists completed
- a button to download that summary as a CSV
Use ui.download so the files save from the browser.
```

### ✅ Phase 5 checks
- [ ] Restore First puts high-business outages (industry, power) at the top and leaves out restored incidents.
- [ ] Spot-check one row by hand: businesses × 15000 × days down matches the number shown.
- [ ] The ₹15,000 assumption is visible on the page.
- [ ] Impact chart shows one bar per asset type.
- [ ] Workforce summary shows hours and tasks per crew.
- [ ] Each CSV downloads and opens in Excel with the right columns.
- [ ] Daily summary numbers match what the dashboard shows.
- [ ] Pushed to GitHub.

---

## PHASE 6 · Polish and APK (hour 18–21)

### Prompt 9 – Demo reset and polish
```
Read resqmesh-brief.md first.

1. Add a small "Demo" menu on the Dashboard with "Reset demo data" (clears tables and reloads demo_data.py) and a "DEMO DATA" badge when demo data is loaded.
2. Check every page works at phone width: tables scroll sideways inside their box, the sidebar collapses to a menu button.
3. Make sure all colors follow the brief and every button has a clear label.
Don't add any new features.
```

### ✅ Phase 6 checks
- [ ] "Reset demo data" restores the starting state.
- [ ] Every page is usable on a phone browser.
- [ ] C's APK is built and installed; it reports to the server using the laptop IP.
- [ ] Pushed to GitHub.

---

## PHASE 7 · Final test and submit (hour 21–24)

No new features. Only fixes.

### ✅ Final checks
- [ ] Fresh start: `py server/seed.py`, then `py server/main.py`. Dashboard loads.
- [ ] Full demo story works twice: phone report → appears on map and queue with score → "Why?" → suggested crew → safety checklist → assign → phone Start → Restored → Restore First updates → export CSV.
- [ ] Backup video of the demo is recorded (D).
- [ ] README.md explains what ResQMesh does, how to run the server and how to install the APK.
- [ ] Pitch slides cover the 8 features and Track 3 / SDG 8 & 9 (D).
- [ ] Final push done; GitHub shows the latest code.
- [ ] Laptop and phones charged, all on the same Wi-Fi or hotspot.

---

## When something breaks
```
Read resqmesh-brief.md first. Running <the command you ran> gives this error:

<paste the full error here>

Fix only this error. Don't change anything else.
```
