# ResQMesh – build prompts by phase (for A)

How to use:
- Paste one prompt at a time into Claude Code.
- At the end of each phase, run every check. Move to the next phase only when all pass.
- If a check fails, use the "When something breaks" prompt at the end.
- Push after every phase:  git add -A  →  git commit -m "Phase N done"  →  git push

---

## PHASE 1 · Foundation (hour 0–2)

### Prompt 1 – Database and demo data
```
Read resqmesh-brief.md first and follow it exactly.

Create:
1. server/database.py – SQLite database (resqmesh.db in the server folder) with the tables reports, crews, assignments, messages and alerts as described in the brief. Add simple helper functions: init_db(), add_report(), get_reports(), add_crew(), get_crews(), update_report_status().
2. server/demo_data.py – about 20 realistic damage reports around Vellore, Tamil Nadu (mix of power, bridge, road, water, telecom, hospital, industry; severities 1–5; real-looking lat/lng near 12.92 N, 79.13 E) and 8 crews with different skills and hours_worked.
3. server/seed.py – creates the database and loads the demo data. Running it twice must not create duplicates.

Keep the code simple with short comments. Tell me the exact command to run it on Windows (I use py, not python).
```

### Prompt 2 – NiceGUI skeleton
```
Read resqmesh-brief.md first.

Create server/main.py with NiceGUI:
- ui.run(host="0.0.0.0", port=8080, title="ResQMesh")
- A shared layout: navy left sidebar with links Dashboard, Incidents, Crews, Analytics, Mesh messages, Alerts; content area on the right.
- Pages: / (simple home), /dashboard, /crews. For now /dashboard shows a table of all reports from the database and /crews shows a table of crews.
- Colors: navy #0F2A44, teal #0B7A6F for buttons.

Tell me how to run it and which URL to open.
```

### ✅ Phase 1 checks
- [ ] `py server/seed.py` runs with no red errors, and `server/resqmesh.db` exists.
- [ ] Run `py server/seed.py` again: still about 20 reports and 8 crews, no duplicates.
- [ ] `py server/main.py` starts; `http://localhost:8080/dashboard` shows the reports table.
- [ ] `/crews` shows 8 crews, and the sidebar links switch pages.
- [ ] A phone on the same hotspot opens `http://<laptop-IP>:8080/dashboard` (find the IP with `ipconfig`; allow Python in the firewall popup).
- [ ] Pushed to GitHub; B, C and D ran `git pull`.

---

## PHASE 2 · Core triage (hour 2–6)

### Prompt 3 – Scoring and report API
```
Read resqmesh-brief.md first.

1. Create server/scoring.py with priority(report, hours_waiting) that returns (score 0–100, breakdown dict) exactly as in the brief, plus level(score) that returns Critical / High / Medium / Low.
2. In server/main.py add REST endpoints (NiceGUI's app is FastAPI):
   - POST /api/reports – save a new report (asset_type, lat, lng, severity, description, people_affected, businesses_affected), return its id and score.
   - GET /api/reports – all reports with score and level.
3. Change /dashboard to an incident queue sorted by score: score number, colored level badge, asset type, description, and a "Why?" button that shows the breakdown as small bars in a dialog.

Add a tiny test I can run with py to check scoring gives sensible numbers.
```

### Prompt 4 – Duplicate detection
```
Read resqmesh-brief.md first.

Create server/duplicates.py:
- haversine distance in metres
- find_duplicates(new_report, existing_reports): same asset_type, within 500 m, and difflib.SequenceMatcher description ratio > 0.6

When a report arrives through POST /api/reports, mark duplicates with merged_into pointing to the original. In the dashboard queue, show "3 reports" on the original and hide merged ones.
```

### ✅ Phase 2 checks
- [ ] The scoring test passes: a severity-5 hospital report scores higher than a severity-2 road report.
- [ ] Every score is 0–100, and the four "Why?" parts add up to the score.
- [ ] `/dashboard` is sorted highest first, with Critical / High / Medium / Low badges.
- [ ] `http://localhost:8080/docs` → POST /api/reports returns an id and score, and the report shows on the dashboard.
- [ ] The same report sent twice → one row showing "2 reports".
- [ ] Same asset type ~2 km away → NOT merged. Different asset type at the same spot → NOT merged.
- [ ] C's Report Damage screen on the phone sends a report that appears on the dashboard.
- [ ] Pushed to GitHub.

---

## PHASE 3 · Mesh node (hour 6–10)

### Prompt 5 – Mesh message format and node
```
Read resqmesh-brief.md first.

Create mesh/node.py:
- Message format from the brief (id, origin, type, payload, ttl, created_at).
- A MeshNode class with an outbox (saved to a small JSON file so it survives restarts), a set of seen ids, add_message(), receive(messages) that skips seen ids, decreases ttl and drops ttl 0, and upload(server_url) that POSTs the outbox to /api/messages when reachable.

Also add POST /api/messages to server/main.py that stores messages (deduplicated by id) and, for type "report", creates the report through the same code as /api/reports.

Show me how to test it with two nodes on one laptop.
```

### ✅ Phase 3 checks
- [ ] Two nodes on one laptop: a message added on node 1 appears on node 2 after sync.
- [ ] Syncing again does not create a duplicate (seen ids work).
- [ ] A message with ttl 1 is not passed on a second hop.
- [ ] Restart a node: its outbox is still there (saved to JSON).
- [ ] Node uploads to the server → the report appears on the dashboard; uploading twice does not duplicate it.
- [ ] B's map shows the reports. C has started the first `flet build apk`.
- [ ] Pushed to GitHub.

---

## PHASE 4 · Assignment, safety and Wi-Fi mesh (hour 10–14)

### Prompt 6 – Crew assignment and safety
```
Read resqmesh-brief.md first.

Create server/assignment.py:
- suggest_assignments(reports, crews) using scipy.optimize.linear_sum_assignment.
  Cost = distance in km + 1000 if skill does not match asset type + 1000 if hours_worked >= 12.
  Skill map: power→electrical, telecom→telecom, water→plumbing, road/bridge→civil, hospital→electrical, industry→electrical.
- Never suggest a crew with hours_worked >= 12.

In the dashboard, each unassigned incident shows "Suggested crew" with an Assign button. For power and bridge jobs, Assign first opens a safety checklist dialog (3 checkboxes); the assignment is saved only when all are ticked.

Add endpoints: GET /api/tasks/{crew_id}, POST /api/tasks/{report_id}/status, POST /api/checkin.
```

### Prompt 7 – Local Wi-Fi transport (laptops and phones)
```
Read resqmesh-brief.md first. We use NO Bluetooth – only local Wi-Fi (UDP) on a phone hotspot with no internet.

Create mesh/udp_transport.py in pure Python (socket, json, uuid only, so it also runs inside the Flet phone app):
- announce(node): UDP broadcast "I'm here" with node id and port every few seconds.
- listen(node): receives announcements and outboxes; calls node.receive() and replies with its own outbox.
- sync_with(peer_ip, node): sends the outbox to one peer and receives theirs.
- If broadcast is blocked on the hotspot, allow a fixed list of peer IPs instead.

Add mesh/run_node.py so a laptop can run as a node from the command line, and tell me how to test it with two laptops on the same phone hotspot.
```

### ✅ Phase 4 checks
- [ ] Power incidents get an electrical crew suggested; bridges get civil.
- [ ] A crew with 12+ hours is never suggested.
- [ ] Assigning a power or bridge job opens the safety checklist and only saves when all 3 boxes are ticked.
- [ ] GET /api/tasks/{crew_id} returns that crew's tasks, and C's My Tasks screen shows them.
- [ ] A status change from the phone (Start → Restored) shows on the dashboard.
- [ ] POST /api/checkin ("Safe" / "Needs Help") from the phone is stored.
- [ ] Two laptops on a phone hotspot (mobile data off): a message from laptop 2 arrives on laptop 1.
- [ ] Nodes find each other automatically by broadcast. If not (client isolation), the fixed peer IP list works.
- [ ] Pushed to GitHub.

---

## PHASE 5 · Mesh end-to-end (hour 14–18)

### Prompt 8 – Full offline relay
```
Read resqmesh-brief.md first.

Connect the pieces into one offline flow:
1. Run mesh/node.py and mesh/udp_transport.py inside the Flet phone app, so a phone with no server connection keeps reports in its outbox and passes them to nearby phones and laptops over the hotspot.
2. The node keeps it in its outbox, relays it to other nodes over local Wi-Fi (UDP), and any node that can reach the main server uploads it.
3. Add a "Mesh messages" page on the dashboard showing each message with status Queued / Relayed / Delivered and which node it came through.
4. Add GET /api/alerts and a simple "Broadcast alert" form on the dashboard.

Give me a step-by-step test with: phone A (field crew), phone B (relay), and the dashboard laptop, all on one phone hotspot with mobile data off.
```

### ✅ Phase 5 checks
- [ ] Phone A → phone B → dashboard (hotspot, no internet): the report arrives and is scored.
- [ ] Phone A out of the dashboard's reach still delivers through phone B.
- [ ] The Mesh messages page shows the path and status Delivered.
- [ ] Close the app on phone B mid-test → the message stays Queued on phone A, then delivers when B is back.
- [ ] A broadcast alert from the dashboard shows in the phone app's Alerts tab.
- [ ] The full flow works 3 times in a row with no errors.
- [ ] Pushed to GitHub.

---

## PHASE 6 · Analytics and demo mode (hour 18–21)

### Prompt 9 – Economic impact and analytics
```
Read resqmesh-brief.md first.

Create server/analytics.py with pandas:
- impact per report = businesses_affected × 15000 (average daily revenue in ₹, as a clearly labelled assumption) × days_down
- restore_first() – reports sorted by impact, not yet restored
- workforce_summary() – per crew: hours worked, tasks done; and skills that ran short

Add GET /api/analytics returning these, plus a CSV export button on the dashboard.
```

### Prompt 10 – Demo mode
```
Read resqmesh-brief.md first.

Add a "Demo mode" section on the dashboard:
- "Load demo data" – clears the database and reloads demo_data.py.
- "Simulate cyclone" – adds a new realistic report every 10 seconds for 2 minutes, so the queue, map and charts update live for the judges.
- "Clear demo data" – empties all tables.
Show a small "DEMO DATA" badge whenever demo data is loaded.
```

### ✅ Phase 6 checks
- [ ] Restore First is sorted by impact, highest first, and leaves out restored incidents.
- [ ] Spot-check one row by hand: businesses × 15000 × days down matches the number shown.
- [ ] The ₹15,000 figure is labelled as an assumption on screen.
- [ ] CSV export opens in Excel with the right columns.
- [ ] Workforce summary shows hours and tasks for each crew.
- [ ] "Simulate cyclone" adds reports to the queue and map without refreshing.
- [ ] "Load demo data" resets everything cleanly.
- [ ] Pushed to GitHub.

---

## PHASE 7 · Final test and submit (hour 21–24)

No new features from here. Only fixes.

### ✅ Final checks
- [ ] Fresh start: close everything, run `py server/seed.py`, then `py server/main.py`. The dashboard loads.
- [ ] The installed APK (not the Flet dev app) sends a report successfully.
- [ ] Full demo story works twice: report → mesh hop → scored → "Why?" → assign with safety check → Restored → Restore First.
- [ ] Backup video of the demo is recorded (D).
- [ ] README.md explains what ResQMesh does and how to run the server, install the APK and run a mesh node.
- [ ] Pitch slides cover Track 3 and SDG 8 & 9 (D).
- [ ] Final push done; GitHub shows the latest code.
- [ ] Laptops and phones charged, hotspot ready with mobile data off.

---

## When something breaks
```
Read resqmesh-brief.md first. Running <the command you ran> gives this error:

<paste the full error here>

Fix only this error. Don't change anything else.
```
