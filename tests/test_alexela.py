import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scraper"))
from parsers import alexela

text = (pathlib.Path(__file__).parent
        / "fixtures/alexela_en_elekter.txt").read_text(encoding="utf-8")
entries = alexela.parse(text)
by_name = {e["name"]: e for e in entries}

assert len(entries) == 6, [e["name"] for e in entries]
assert by_name["Term fixed rate"]["type"] == "day_night"
assert by_name["Term fixed rate"]["day_rate_cents_kwh"] == round(12.8 / 1.24, 3)
assert by_name["Exchange rate electricity"]["type"] == "spot"
assert by_name["Exchange rate electricity"]["margin_cents_kwh"] == round(0.47 / 1.24, 3)
assert by_name["Choose Yourself"]["monthly_fee_cents"] == int(round(202 / 1.24))
assert "Stressless" not in by_name and "Fixed Plan" not in by_name
print("ALL TESTS PASSED,", len(entries), "packages:", [e["name"] for e in entries])
