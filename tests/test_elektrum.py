import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scraper"))
from parsers import elektrum


def comp(type_, value_incl, value_excl, uom, zone=""):
    return {"name": type_, "category": "electricity ", "type": type_, "zone": zone,
            "charge_value": value_incl, "charge_value_without_vat": value_excl,
            "uom": uom}


def product(name, ptype, zones, price_lists, person="Private"):
    return {"billing_product": {"id": "0", "name": name, "person_type": person,
                                "product_type": ptype, "zone_count": zones,
                                "price_lists": price_lists}}


FEE = comp("EE-EEMAB", "1.91", "1.54", "EUR/kuus")

# Fixture mirrors the observed API shape (values from live inspection 2026-08-02)
payload = {"status": 200, "products": [
    product("KALJUKINDEL KLÕPS", "FIXED", "1", [
        {"contract_term": 881, "contract_start_date": "2026-08-01 00:00:00",
         "contract_end_date": "2099-12-31 00:00:00", "components": [
             {"name": "EE Insurance fee (PRI)", "category": "other", "type": "FERAEE",
              "zone": "", "charge_value": "0.50000",
              "charge_value_without_vat": "0.50000", "uom": "EUR"},
             comp("EE-F-EEV", "13.770", "11.105", "s/kWh", "single"),
             comp("EE-EEMAB", "3.62", "2.92", "EUR/kuus")]}]),
    product("KASULIK KLÕPS", "FIXED", "2", [
        {"contract_term": 9, "contract_start_date": "2026-08-01 00:00:00", "components": [
            comp("EE-F-EEL", "21.499", "17.338", "s/kWh", "day"),
            comp("EE-F-EEK", "15.419", "12.435", "s/kWh", "night"), FEE]},
        {"contract_term": 24, "contract_start_date": "2026-08-01 00:00:00", "components": [
            comp("EE-F-EEL", "16.390", "13.218", "s/kWh", "day"),
            comp("EE-F-EEK", "11.885", "9.585", "s/kWh", "night"), FEE]}]),
    product("BÖRSI KLÕPS", "VARIABLE", "INT", [
        {"contract_term": 881, "contract_start_date": "2026-08-01 00:00:00", "components": [
            comp("EE-V-EEV", "10.448", "8.426", "s/kWh", "single"),
            comp("EE-INTHF", "0.533", "0.430", "s/kWh"), FEE]}]),
    product("PAINDLIK KLÕPS MIX", "MIXED", "INT", [
        {"contract_term": 12, "contract_start_date": "2026-08-01 00:00:00", "components": [
            comp("EE-U-EEV", "16.572", "13.367", "s/kWh", "single"),
            comp("EE-INTHF", "0.553", "0.446", "s/kWh"), FEE]}]),
    product("ROHELINE KLÕPS", "FIXED", "1", [
        {"contract_term": 12, "contract_start_date": "2026-08-01 00:00:00", "components": [
            {"name": "EE Green Energy (PRI)", "category": "other", "type": "GREENEE",
             "zone": "", "charge_value": "1.56000",
             "charge_value_without_vat": "1.56000", "uom": "EUR"},
            comp("EE-F-EEV", "16.892", "13.623", "s/kWh", "single"), FEE]}]),
    product("ARI KLÕPS", "FIXED", "1", [
        {"contract_term": 12, "contract_start_date": "2026-08-01 00:00:00", "components": [
            comp("EE-F-EEV", "12.400", "10.000", "s/kWh", "single"), FEE]}],
            person="Business"),
]}

entries = elektrum.parse_payload(payload)
by_id = {e["id"]: e for e in entries}

# hybrid, green and business products skipped; one entry per contract term
assert len(entries) == 4, sorted(by_id)
assert sorted(by_id) == ["elektrum-borsi-klops", "elektrum-kaljukindel-klops",
                         "elektrum-kasulik-klops-24m", "elektrum-kasulik-klops-9m"]

k = by_id["elektrum-kaljukindel-klops"]
assert k["name"] == "Kaljukindel Klõps"
assert k["type"] == "fixed" and k["rate_cents_kwh"] == 11.105
assert k["contract_months"] is None            # contract_term 881 = open-ended
assert k["monthly_fee_cents"] == 292           # advertised Kuutasu, FERAEE excluded

d = by_id["elektrum-kasulik-klops-9m"]
assert d["type"] == "day_night" and d["contract_months"] == 9
assert (d["day_rate_cents_kwh"], d["night_rate_cents_kwh"]) == (17.338, 12.435)
assert d["monthly_fee_cents"] == 154

s = by_id["elektrum-borsi-klops"]
assert s["type"] == "spot" and s["margin_cents_kwh"] == 0.43
assert s["rate_cents_kwh"] is None             # EE-V-EEV is a market quote, not a rate

# VAT-exclusive values come from the API; division is the fallback path only
assert elektrum._ex_vat({"charge_value": "12.40"}) == 10.0

print("ALL TESTS PASSED,", len(entries), "packages:", sorted(by_id))
