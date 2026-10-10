"""Tiny check that the scoring gives sensible numbers. Run:   py server/test_scoring.py"""

from scoring import level, priority


def report(asset_type, severity, people_affected):
    return {"asset_type": asset_type, "severity": severity, "people_affected": people_affected}


# (name, report, hours waiting, expected score, expected level)
CASES = [
    ("Worst case hospital", report("hospital", 5, 4000), 8, 100, "Critical"),    # 40 + 25 + 20 + 15
    ("Substation, 6 h old", report("power", 5, 4200), 6, 97, "Critical"),        # 40 + 25 + 20 + 12
    ("Power, medium damage", report("power", 3, 1000), 2, 58, "High"),           # 24 + 25 + 5 + 4
    ("Cracked culvert", report("bridge", 3, 700), 2, 46.5, "Medium"),            # 24 + 15 + 3.5 + 4
    ("Fallen tree, just in", report("road", 1, 0), 0, 18, "Low"),                # 8 + 10 + 0 + 0
    ("Caps hold (huge numbers)", report("road", 1, 1_000_000), 500, 53, "Medium"),  # 8 + 10 + 20 + 15
]

for name, data, hours, expected_score, expected_level in CASES:
    score, breakdown = priority(data, hours)
    print(f"{name:26} score {score:5}  {level(score):8}  {breakdown}")
    assert score == expected_score, f"{name}: expected {expected_score}, got {score}"
    assert level(score) == expected_level, f"{name}: expected {expected_level}, got {level(score)}"

# Level boundaries from the brief
assert [level(s) for s in (75, 74.9, 55, 54.9, 35, 34.9)] == \
    ["Critical", "High", "High", "Medium", "Medium", "Low"]

print("All scoring checks passed.")
