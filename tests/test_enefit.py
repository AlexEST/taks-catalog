import copy, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scraper"))
from parsers import enefit

# Fixture mirrors the observed API shape (values from live inspection 2026-08-02).
# The SPECIAL product is reproduced exactly as the live payload has it: three
# rows, no winter rate, and a margin whose prices stop with September while the
# green and fee rows run on to November.
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
      {"code": "EE_FS_SPOT_GR", "length": None, "retailProductRows": [
        {"currencySign": "cent", "unitOfMeasure": "kWh",
         "translation": {"translation": "EE_SPOT_MARGIN"},
         "prices": [{"salesMonth": "2026-08-01", "price": 0.9},
                    {"salesMonth": "2026-09-01", "price": 0.9}]},
        {"currencySign": "cent", "unitOfMeasure": "kWh",
         "translation": {"translation": "EE_SPOT_GREEN"},
         "prices": [{"salesMonth": "2026-08-01", "price": 0.0},
                    {"salesMonth": "2026-11-01", "price": 0.0}]},
        {"currencySign": "EUR", "unitOfMeasure": "MONTH",
         "translation": {"translation": "EE_SPOT_MONTHLY_FEE"},
         "prices": [{"salesMonth": "2026-08-01", "price": 2.05},
                    {"salesMonth": "2026-11-01", "price": 2.05}]}]}]},
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

# names come from BASE_NAMES, ids still come from the code
assert by_id["enefit-ee-spot-bl"]["name"] == "Muutuv"
assert by_id["enefit-ee-spot-gr"]["name"] == "Muutuv Roheline"
assert by_id["enefit-ee-fix-12m-bl"]["name"] == "Kindel (12 kuud)"
assert enefit._name("EE_FIX_24M_GR", 24) == "Kindel Roheline (24 kuud)"  # new term composes
assert enefit._name("EE_HOOAEG_BL", None) == "Hooaeg Bl"                 # unmapped: old behaviour

# Today's payload: every seasonal row is placeable, none of them is the winter
# rate, so Hooajakindel is withheld and the run stays green.
assert "enefit-ee-fs-spot-gr" not in by_id
assert enefit.SEASONAL_FIXED_ROW_KEYS == (), "the empty allowlist is the guard"

# The day Enefit publishes it, a cent/kWh row this parser cannot place appears.
# It must not be silently ignored: withholding forever with a green CI is how
# the package would stay missing for a year. The run fails and names the key.
arrived = copy.deepcopy(payload)
winter = {"currencySign": "cent", "unitOfMeasure": "kWh",
          "translation": {"translation": "EE_FIX_WINTER"},
          # priced from October, i.e. entirely in the future when it first shows
          "prices": [{"salesMonth": "2026-10-01", "price": 14.88},
                     {"salesMonth": "2026-11-01", "price": 14.88}]}
arrived["retailProductFamilies"][1]["retailProducts"][0]["retailProductRows"].append(winter)
try:
    enefit.parse_payload(arrived)
    raise AssertionError("an unplaceable seasonal row must fail the run, not vanish")
except RuntimeError as e:
    assert "EE_FIX_WINTER=14.88" in str(e), e
    assert "SEASONAL_FIXED_ROW_KEYS" in str(e), e

# ... and once the real key is known, it prices, even though every price entry
# for the winter rate is still in the future.
enefit.SEASONAL_FIXED_ROW_KEYS = ("EE_FIX_WINTER",)
try:
    season = {e["id"]: e for e in enefit.parse_payload(arrived)}["enefit-ee-fs-spot-gr"]
    assert season["name"] == "Hooajakindel" and season["type"] == "seasonal"
    assert season["rate_cents_kwh"] == round(14.88 / 1.24, 3)   # winter, Oct-Mar
    assert season["margin_cents_kwh"] == round(0.9 / 1.24, 3)   # summer, Apr-Sep
    assert season["spot_months"] == [4, 5, 6, 7, 8, 9]
    assert season["monthly_fee_cents"] == int(round(2.05 * 100 / 1.24))
finally:
    enefit.SEASONAL_FIXED_ROW_KEYS = ()

print("ALL TESTS PASSED,", len(entries), "packages:", sorted(by_id))
