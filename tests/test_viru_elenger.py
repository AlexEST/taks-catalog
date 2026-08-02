import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scraper"))
from parsers import viru, elenger

viru_text = """
Viru Kindel pakett lukustab elektrihinna kogu lepinguperioodiks.
Fikseeritud hind (käibemaksuga) 8 kuud
Kahetariifne: päev 14,02 s/kWh ja öö 12,26 s/kWh, kuutasu 1,91 €
Ühetariifne: 13,14 s/kWh, kuutasu 1,91 €
Viru Roheline on börsihinnaga lahendus
Korter: marginaal 0,56 s/kWh ja kuutasu 1,76 eurot (käibemaksuga).
Maja: marginaal 0,775 s/kWh ja kuutasu 0 eurot (käibemaksuga).
"""
v = {e["id"]: e for e in viru.parse(viru_text)}
assert len(v) == 4, sorted(v)
assert v["viru-kindel-2tar"]["day_rate_cents_kwh"] == round(14.02/1.24, 3)
assert v["viru-kindel-2tar"]["contract_months"] == 8
assert v["viru-kindel-1tar"]["type"] == "fixed"
assert v["viru-vaba-maja"]["margin_cents_kwh"] == round(0.775/1.24, 3)
assert v["viru-vaba-maja"]["monthly_fee_cents"] == 0

e = elenger.parse("Price (with VAT): Excange rate price + 0,67 cents/kWh")
assert len(e) == 1 and e[0]["margin_cents_kwh"] == round(0.67/1.24, 3)
print("ALL TESTS PASSED: viru=4 packages, elenger=1 package")
