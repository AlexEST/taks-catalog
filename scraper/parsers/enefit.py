"""Enefit parser.

Discovered 2026-08 via XHR inspection: the public package widget on
https://www.enefit.ee/et/era/elekter/elektrileping-ja-paketid calls

    GET https://iseteenindus.enefit.ee/api/v2/retail-products
        ?country=EE&consumptionType=CONSUMER

anonymously (no auth) and receives full structured pricing:
  retailProductFamilies[].retailProducts[]
    .code (EE_SPOT_BL, EE_FIX_12M_GR, EE_SPOT_CEILING_BL, ...)
    .length (contract months for FIX)
    .retailProductRows[]  -> currencySign cent|EUR, unitOfMeasure kWh|MONTH,
                             prices[] entries keyed by salesMonth

Mapping:
  * SPOT family        -> type "spot": margin = sum of cent/kWh rows
  * FIX family         -> type "fixed": rate = sum of cent/kWh rows
  * *_CEILING_*        -> skipped (price-ceiling products, not backtestable v1)
  * SPECIAL family     -> skipped
  * EUR/MONTH rows     -> monthly_fee_cents

VAT: !! VERIFY ON FIRST LIVE RUN !! Assumed VAT-inclusive (consumer-facing,
consistent with Alexela's display and EE consumer price display rules);
normalized to VAT-exclusive below. If widget UI proves otherwise, drop VAT.
"""
from __future__ import annotations
import datetime

API_URL = ("https://iseteenindus.enefit.ee/api/v2/retail-products"
           "?country=EE&consumptionType=CONSUMER")
SOURCE_URL = "https://www.enefit.ee/et/era/elekter/elektrileping-ja-paketid"
SUPPLIER = "Enefit"
VAT = 1.24  # see VERIFY note above

SKIP_FAMILIES = {"SPECIAL"}
SKIP_CODE_SUBSTR = ("CEILING",)


def _current_price(prices: list[dict]) -> float | None:
    """Pick the price entry with the latest salesMonth not in the future."""
    today = datetime.date.today().isoformat()
    valid = [p for p in prices or [] if p.get("salesMonth") and p["salesMonth"] <= today]
    if not valid:
        valid = prices or []
    if not valid:
        return None
    return sorted(valid, key=lambda p: p["salesMonth"])[-1].get("price")


def _ex_vat(v: float) -> float:
    return round(v / VAT, 3)


def parse_payload(j: dict) -> list[dict]:
    out = []
    for fam in j.get("retailProductFamilies", []):
        fcode = fam.get("familyCode", "")
        if fcode in SKIP_FAMILIES:
            continue
        for p in fam.get("retailProducts", []):
            code = p.get("code", "")
            if any(s in code for s in SKIP_CODE_SUBSTR):
                continue
            kwh_total, fee_eur = 0.0, 0.0
            for row in p.get("retailProductRows", []):
                price = _current_price(row.get("prices"))
                if price is None:
                    continue
                if row.get("currencySign") == "cent" and row.get("unitOfMeasure") == "kWh":
                    kwh_total += price
                elif row.get("currencySign") == "EUR" and row.get("unitOfMeasure") == "MONTH":
                    fee_eur += price
            if kwh_total == 0 and fee_eur == 0:
                continue
            entry = {
                "id": "enefit-" + code.lower().replace("_", "-"),
                "name": code.replace("EE_", "").replace("_", " ").title(),
                "monthly_fee_cents": int(round(fee_eur * 100 / VAT)),
                "contract_months": p.get("length"),
                "source_url": SOURCE_URL,
                "day_rate_cents_kwh": None, "night_rate_cents_kwh": None,
            }
            if fcode == "SPOT":
                entry |= {"type": "spot",
                          "margin_cents_kwh": _ex_vat(kwh_total),
                          "rate_cents_kwh": None}
            elif fcode == "FIX":
                entry |= {"type": "fixed",
                          "rate_cents_kwh": _ex_vat(kwh_total),
                          "margin_cents_kwh": None}
            else:
                continue  # unknown family: skip loudly rather than guess
            out.append(entry)
    return out


def fetch_and_parse(session) -> list[dict]:
    r = session.get(API_URL, timeout=30,
                    headers={"Accept": "application/json"})
    r.raise_for_status()
    return parse_payload(r.json())
