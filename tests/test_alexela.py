import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scraper"))
from parsers import alexela

text = (pathlib.Path(__file__).parent
        / "fixtures/alexela_et_elekter.txt").read_text(encoding="utf-8")
entries = alexela.parse(text)
by_name = {e["name"]: e for e in entries}

assert len(entries) == 5, [e["name"] for e in entries]
assert by_name["Tähtajaline fikseeritud hind"]["type"] == "day_night"
assert by_name["Tähtajaline fikseeritud hind"]["day_rate_cents_kwh"] == round(12.8 / 1.24, 3)
assert by_name["Tähtajaline fikseeritud hind"]["night_rate_cents_kwh"] == round(10.8 / 1.24, 3)
assert by_name["Börsihinnaga elekter"]["type"] == "spot"
assert by_name["Börsihinnaga elekter"]["margin_cents_kwh"] == round(0.47 / 1.24, 3)
assert by_name["Vali ise"]["monthly_fee_cents"] == int(round(202 / 1.24))

# names are the page's own Estonian, ids fold the diacritics instead of eating them
assert by_name["Börsihinnaga elekter"]["id"] == "alexela-borsihinnaga-elekter"
assert by_name["Tähtajaline fikseeritud hind"]["id"] == "alexela-tahtajaline-fikseeritud-hind"
assert all("-" != i["id"][-1] and "--" not in i["id"] for i in entries), [e["id"] for e in entries]

# excluded, each for its own reason
assert "Kindel maht" not in by_name          # volume plan
assert "Pingevaba" not in by_name            # monthly-changing base price
assert "Virtuaalaku - 3kwh" not in by_name   # virtual battery
# Kodupakett is börsihind + 0 marginaal, but the page states that only in prose
# ("Börsihind + 0 marginaal") and prints last month's average where the other
# spot packages print a Marginaal line. A margin read out of marketing copy is a
# guess, so it stays out -- as it already is on the live EN page.
assert "Alexela Kodupakett elekter" not in by_name

# prose that resembles a labeled price must not be read as one
assert alexela.RX["margin"].search("Börsihind + marginaal") is None
assert alexela.RX["base"].search("Eelmise kuu keskmine börsihind 8,23 s/kWh") is None
assert alexela.RX["monthly_fee"].search("Kuutasu alusel tarbitav maht 200 kWh") is None

print("ALL TESTS PASSED,", len(entries), "packages:", [e["name"] for e in entries])
