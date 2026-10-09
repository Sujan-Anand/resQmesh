# ResQMesh – build prompts (for A)

Copy one prompt at a time into Claude Code. Run and test after each one, then commit and push:

```
git add -A
git commit -m "what you added"
git push
```

Tips to save usage:
- Paste a whole prompt at once instead of many small messages.
- Fix small things (text, colors, typos) by hand.
- When something breaks, paste the full error and say "fix only this error".

---

## Phase 1 · Foundation (hour 0–2)

### Prompt 1 – Database and demo data
```
Read resqmesh-brief.md first and follow it exactly.

Create:
1. server/database.py – SQLite database (resqmesh.db in the server folder) with the tables
   reports, crews, assignments, messages and alerts as described in the brief. Add simple helper
   functions: init_db(), add_report(), get_reports(), add_crew(), get_crews(), update_report_status().
2. server/demo_data.py – about 20 realistic damage reports around Vellore, Tamil Nadu
   (mix of power, bridge, road, water, telecom, hospital, industry; severities 1–5; real-looking
   lat/lng near 12.92 N, 79.13 E) and 8 crews with different skills and hours_worked.
3. server/seed.py – creates the database and loads the demo data. Running it twice must not
   create duplicates.

Keep the code simple with short comments. Tell me the exact command to run it on Windows
(I use `py`, not `python`).
```

### Prompt 2 – NiceGUI skeleton
```
Read resqmesh-brief.md first.

Create server/main.py with NiceGUI:
- ui.run(host="0.0.0.0", port=8080, title="ResQMesh")
- A shared layout: navy left sidebar with links Dashboard, Incidents, Crews, Analytics,
  Mesh messages, Alerts; content area on the right.
- Pages: / (simple home), /dashboard, /crews. For now /dashboard shows a table of all reports
  from the database and /crews shows a table of crews.
- Colors: navy #0F2A44, teal #0B7A6F for buttons.

Tell me how to run it and which URL to open.
```

---

## Phase 2 · Core triage (hour 2–6)

### Prompt 3 – Scoring and report API
```
Read resqmesh-brief.md first.

1. Create server/scoring.py with priority(report, hours_waiting) that returns
   (score 0–100, breakdown dict) exactly as in the brief, plus level(score) that returns
   Critical / High / Medium / Low.
2. In server/main.py add REST endpoints (NiceGUI's app is FastAPI):
   - POST /api/reports  – save a new report (asset_type, lat, lng, severity, description,
     people_affected, businesses_affected), return its id and score.
   - GET  /api/reports  – all reports with score and level.
3. Change /dashboard to an incident queue sorted by score: score number, colored level badge,
   asset type, description, and a "Why?" button that shows the breakdown as small bars in a dialog.

Add a tiny test I can run with py to check scoring gives sensible numbers.
```

### Prompt 4 – Duplicate detection
```
Read resqmesh-brief.md first.

Create server/duplicates.py:
- haversine distance in metres
- find_duplicates(new_report, existing_reports): same asset_type, within 500 m, and
  difflib.SequenceMatcher description ratio > 0.6
When a report arrives through POST /api/reports, mark duplicates with merged_into pointing to
the original. In the dashboard queue show "3 reports" on the original and hide merged ones.
```

---

## Phase 3 · Map and crews (hour 6–10)

### Prompt 5 – Mesh message format and node
```
Read resqmesh-brief.md first.

Create mesh/node.py:
- Message format from the brief (id, origin, type, payload, ttl, created_at).
- A MeshNode class with an outbox (saved to a small JSON file so it survives restarts),
  a set of seen ids, add_message(), receive(messages) that skips seen ids, decreases ttl and
  drops ttl 0, and upload(server_url) that POSTs the outbox to /api/messages when reachable.
Also add POST /api/messages to server/main.py that stores messages (deduplicated by id) and,
for type "report", creates the report through the same code as /api/reports.
Show me how to test it with two nodes on one laptop.
```

---

## Phase 4 · Assignment and safety (hour 10–14)

### Prompt 6 – Crew assignment and safety
```
Read resqmesh-brief.md first.

Create server/assignment.py:
- suggest_assignments(reports, crews) using scipy.optimize.linear_sum_assignment.
  Cost = distance in km + 1000 if skill does not match asset type + 1000 if hours_worked >= 12.
  Skill map: power→electrical, telecom→telecom, water→plumbing, road/bridge→civil,
  hospital→electrical, industry→electrical.
- Never suggest a crew with hours_worked >= 12.
In the dashboard, each unassigned incident shows "Suggested crew" with an Assign button.
For power and bridge jobs, Assign first opens a safety checklist dialog (3 checkboxes);
the assignment is saved only when all are ticked.
Add endpoints: GET /api/tasks/{crew_id}, POST /api/tasks/{report_id}/status, POST /api/checkin.
```

### Prompt 7 – Bluetooth transport
```
Read resqmesh-brief.md first.

Create mesh/bt_transport.py for Windows:
- Bluetooth RFCOMM with Python's socket module (AF_BLUETOOTH, BTPROTO_RFCOMM, channel 4).
- run_server(own_mac, node) listens and calls node.receive() on incoming outboxes, then replies
  with its own outbox.
- sync_with(peer_mac, node) connects, sends the outbox, receives the peer's outbox.
- A UDP fallback with the same functions (sync over the local network), chosen with a
  --udp flag.
Add mesh/run_node.py with simple command-line options, and tell me exactly how to find each
laptop's Bluetooth MAC address on Windows and test it between two paired laptops.
```

---

## Phase 6 · Analytics (hour 18–21)

### Prompt 8 – Economic impact
```
Read resqmesh-brief.md first.

Create server/analytics.py with pandas:
- impact per report = businesses_affected × 15000 (average daily revenue in ₹, as a clearly
  labelled assumption) × days_down
- restore_first() – reports sorted by impact, not yet restored
- workforce_summary() – per crew: hours worked, tasks done; and skills that ran short
Add GET /api/analytics returning these, plus a CSV export button on the dashboard.
```

---

## When something breaks
```
Read resqmesh-brief.md first. Running `py server/main.py` gives this error:

<paste the full error here>

Fix only this error. Don't change anything else.
```
