import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scraper"))
from parsers import enefit

# Fixture mirrors the observed API shape (values from live inspection 2026-08-02)
payload = {
  "retailProductFamilies": [
    {"familyCode": "SPOT", "retailProducts": [
      {"code": "EE_SPOT_BL", "length": None, "retailProductRows": [
        {"currencySign": "cent", "unitOfMeasure": "kWh",
         "prices": [{"salesMonth": "2026-08-01", "price": 0.5}]},
        {"currencySign": "EUR", "unitOfMeasure": "MONTH",
         "prices": [{"salesMonth": "2026-08-01", "price": 2.05}]}]},
      {"code": "EE_SPOT_GR", "length": None, "retailProductRows": [
        {"currencySign": "cent", "unitOfMeasure": "kWh",
         "prices": [{"salesMonth": "2026-08-01", "price": 0.89}]},
        {"currencySign": "cent", "unitOfMeasure": "kWh",
         "prices": [{"salesMonth": "2026-08-01", "price": 0.3}]},
        {"currencySign": "EUR", "unitOfMeasure": "MONTH",
         "prices": [{"salesMonth": "2026-08-01", "price": 2.05}]}]}]},
    {"familyCode": "SPECIAL", "retailProducts": [
      {"code": "EE_FS_SPOT_GR", "length": None, "retailProductRows": []}]},
    {"familyCode": "FIX", "retailProducts": [
      {"code": "EE_FIX_12M_BL", "length": 12, "retailProductRows": [
        {"currencySign": "cent", "unitOfMeasure": "kWh",
         "prices": [{"salesMonth": "2026-07-01", "price": 13.5},
                    {"salesMonth": "2026-08-01", "price": 13.2}]},
        {"currencySign": "EUR", "unitOfMeasure": "MONTH",
         "prices": [{"salesMonth": "2026-08-01", "price": 1.99}]}]},
      {"code": "EE_SPOT_CEILING_BL", "length": 12, "retailProductRows": [
        {"currencySign": "cent", "unitOfMeasure": "kWh",
         "prices": [{"salesMonth": "2026-08-01", "price": 1.5}]}]}]}]}

entries = enefit.parse_payload(payload)
by_id = {e["id"]: e for e in entries}

assert len(entries) == 3, [e["id"] for e in entries]          # ceiling+special skipped
assert by_id["enefit-ee-spot-bl"]["type"] == "spot"
assert by_id["enefit-ee-spot-bl"]["margin_cents_kwh"] == round(0.5 / 1.24, 3)
assert by_id["enefit-ee-spot-gr"]["margin_cents_kwh"] == round(1.19 / 1.24, 3)  # margin+green summed
assert by_id["enefit-ee-fix-12m-bl"]["type"] == "fixed"
assert by_id["enefit-ee-fix-12m-bl"]["rate_cents_kwh"] == round(13.2 / 1.24, 3)  # latest salesMonth wins
assert by_id["enefit-ee-fix-12m-bl"]["contract_months"] == 12
print("ALL TESTS PASSED,", len(entries), "packages:", sorted(by_id))
