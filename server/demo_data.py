"""Sample damage reports and crews around Vellore, Tamil Nadu (demo scenario: after heavy rain and flooding)."""

# hours_ago = how long ago the damage was reported (seed.py turns this into created_at)
DEMO_REPORTS = [
    # --- Power ---
    {"asset_type": "power", "lat": 12.9345, "lng": 79.1620, "severity": 5, "hours_ago": 6,
     "description": "110 kV substation at Sathuvachari flooded, feeders tripped",
     "people_affected": 4200, "businesses_affected": 85, "workers_affected": 640},
    {"asset_type": "power", "lat": 12.9560, "lng": 79.1400, "severity": 4, "hours_ago": 3,
     "description": "Transformer burnt out near Viruthampet junction",
     "people_affected": 1500, "businesses_affected": 40, "workers_affected": 210},
    {"asset_type": "power", "lat": 12.8950, "lng": 79.1330, "severity": 3, "hours_ago": 1.5,
     "description": "Three electric poles down on Thorapadi main road, live wires on ground",
     "people_affected": 600, "businesses_affected": 12, "workers_affected": 45},
    {"asset_type": "power", "lat": 12.9140, "lng": 79.1010, "severity": 2, "hours_ago": 0.5,
     "description": "Street lights and one feeder line out at Konavattam",
     "people_affected": 250, "businesses_affected": 4, "workers_affected": 10},

    # --- Bridges ---
    {"asset_type": "bridge", "lat": 12.9478, "lng": 79.1372, "severity": 5, "hours_ago": 5,
     "description": "Palar river bridge on Katpadi road: pier scouring, closed to heavy vehicles",
     "people_affected": 3800, "businesses_affected": 120, "workers_affected": 900},
    {"asset_type": "bridge", "lat": 12.9020, "lng": 79.1180, "severity": 3, "hours_ago": 2,
     "description": "Culvert bridge near Otteri lake has a cracked deck slab",
     "people_affected": 700, "businesses_affected": 9, "workers_affected": 60},

    # --- Roads ---
    {"asset_type": "road", "lat": 12.9360, "lng": 79.1370, "severity": 3, "hours_ago": 4,
     "description": "Green Circle underpass waterlogged, NH 48 service road blocked",
     "people_affected": 2500, "businesses_affected": 55, "workers_affected": 320},
    {"asset_type": "road", "lat": 12.9255, "lng": 79.1420, "severity": 2, "hours_ago": 2.5,
     "description": "Large potholes and washed-out stretch on Arcot Road near Kosapet",
     "people_affected": 900, "businesses_affected": 30, "workers_affected": 110},
    {"asset_type": "road", "lat": 12.8790, "lng": 79.1340, "severity": 4, "hours_ago": 7,
     "description": "Landslip has blocked the Bagayam - Adukkamparai road",
     "people_affected": 1800, "businesses_affected": 18, "workers_affected": 150},
    {"asset_type": "road", "lat": 12.9700, "lng": 79.1560, "severity": 1, "hours_ago": 1,
     "description": "Fallen tree partly blocking the road near VIT main gate",
     "people_affected": 300, "businesses_affected": 6, "workers_affected": 20},

    # --- Water ---
    {"asset_type": "water", "lat": 12.9210, "lng": 79.1300, "severity": 4, "hours_ago": 5.5,
     "description": "Main drinking water pipeline burst near Vellore Fort, supply cut",
     "people_affected": 3200, "businesses_affected": 70, "workers_affected": 260},
    {"asset_type": "water", "lat": 12.9480, "lng": 79.1440, "severity": 3, "hours_ago": 3.5,
     "description": "Pumping station motor damaged by flood water at Gandhi Nagar",
     "people_affected": 2100, "businesses_affected": 25, "workers_affected": 90},
    {"asset_type": "water", "lat": 12.9105, "lng": 79.1465, "severity": 2, "hours_ago": 1,
     "description": "Sewage mixing with drinking water line at Saidapet",
     "people_affected": 800, "businesses_affected": 15, "workers_affected": 40},

    # --- Telecom ---
    {"asset_type": "telecom", "lat": 12.9692, "lng": 79.1452, "severity": 4, "hours_ago": 4.5,
     "description": "Mobile tower at Katpadi down, backup battery room flooded",
     "people_affected": 5000, "businesses_affected": 95, "workers_affected": 380},
    {"asset_type": "telecom", "lat": 12.9300, "lng": 79.1340, "severity": 3, "hours_ago": 2,
     "description": "Fibre cable cut during road clearing near Long Bazaar",
     "people_affected": 1200, "businesses_affected": 140, "workers_affected": 420},
    {"asset_type": "telecom", "lat": 12.9410, "lng": 79.1710, "severity": 1, "hours_ago": 0.5,
     "description": "Broadband cabinet without power at Alamelumangapuram",
     "people_affected": 180, "businesses_affected": 8, "workers_affected": 15},

    # --- Hospitals ---
    {"asset_type": "hospital", "lat": 12.9246, "lng": 79.1353, "severity": 5, "hours_ago": 2,
     "description": "Hospital near Ida Scudder Road running on generator, fuel for 6 hours only",
     "people_affected": 2600, "businesses_affected": 35, "workers_affected": 1100},
    {"asset_type": "hospital", "lat": 12.8580, "lng": 79.1340, "severity": 3, "hours_ago": 3,
     "description": "Government hospital at Adukkamparai: ground floor ward and lift flooded",
     "people_affected": 1400, "businesses_affected": 5, "workers_affected": 350},

    # --- Industry ---
    {"asset_type": "industry", "lat": 12.9770, "lng": 79.1380, "severity": 4, "hours_ago": 6.5,
     "description": "Katpadi industrial estate: 20 small units without power, machines under water",
     "people_affected": 950, "businesses_affected": 20, "workers_affected": 780},
    {"asset_type": "industry", "lat": 12.9080, "lng": 79.1560, "severity": 2, "hours_ago": 1.5,
     "description": "Leather goods units at Melmonavoor stopped, access road damaged",
     "people_affected": 400, "businesses_affected": 11, "workers_affected": 230},
]

# Crew 4 is at the 10 h fatigue-warning zone (11 h) and crew 6 is at the 12 h shift limit
DEMO_CREWS = [
    {"name": "TNEB Line Crew A", "skill": "electrical", "lat": 12.9330, "lng": 79.1500,
     "status": "Available", "hours_worked": 4},
    {"name": "TNEB Line Crew B", "skill": "electrical", "lat": 12.9600, "lng": 79.1420,
     "status": "Available", "hours_worked": 7.5},
    {"name": "Highways Civil Team 1", "skill": "civil", "lat": 12.9200, "lng": 79.1320,
     "status": "Available", "hours_worked": 2},
    {"name": "Highways Civil Team 2", "skill": "civil", "lat": 12.9450, "lng": 79.1390,
     "status": "Available", "hours_worked": 11},
    {"name": "Corporation Roads Crew", "skill": "civil", "lat": 12.8900, "lng": 79.1300,
     "status": "Available", "hours_worked": 5.5},
    {"name": "Telecom Repair Unit 1", "skill": "telecom", "lat": 12.9650, "lng": 79.1480,
     "status": "Off-duty", "hours_worked": 12},
    {"name": "Telecom Repair Unit 2", "skill": "telecom", "lat": 12.9280, "lng": 79.1360,
     "status": "Available", "hours_worked": 3},
    {"name": "TWAD Water Crew", "skill": "plumbing", "lat": 12.9230, "lng": 79.1280,
     "status": "Available", "hours_worked": 6},
]
