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
  * SPECIAL / *_FS_*   -> type "seasonal" (Hooajakindel), see _seasonal_entry
  * EUR/MONTH rows     -> monthly_fee_cents

Names: the API carries none — `translation` holds the key "EE_FIX_12M", not a
label — so BASE_NAMES below maps the code to what the ET page actually calls
the product. Read off the live widget 2026-08 and confirmed by price, not by
guesswork: the "Energiatootmise allikad" toggle flips every card between
Tavaline and Roheline, which is exactly the _BL / _GR suffix.

    Kindel, 36 kuud     12,90 s/kWh  = EE_FIX_36M_BL  10.403 x 1.24
    Kindel Roheline     13,13 s/kWh  = EE_FIX_36M_GR  10.589 x 1.24
    Muutuv              + 0,50       = EE_SPOT_BL      0.403 x 1.24
    Muutuv Roheline     + 0,89       = EE_SPOT_GR      0.718 x 1.24

"Hinnalaega borsipakett" (*_CEILING_*) stays out of the catalogue; the
seasonal "Hooajakindel" is EE_FS_SPOT_GR, confirmed the same way - its
0,90 s/kWh summer margin on the page is this payload's 0.9 cent row.

VAT: verified 2026-08, the four figures above are the page's own VAT-inclusive
prices against this parser's output, so the /1.24 normalisation below is right.
"""
from __future__ import annotations
import datetime
import re

API_URL = ("https://iseteenindus.enefit.ee/api/v2/retail-products"
           "?country=EE&consumptionType=CONSUMER")
SOURCE_URL = "https://www.enefit.ee/et/era/elekter/elektrileping-ja-paketid"
SUPPLIER = "Enefit"
VAT = 1.24  # see VAT note above

SKIP_FAMILIES = {"SPECIAL"}
SKIP_CODE_SUBSTR = ("CEILING",)

# Hooajakindel lives in SPECIAL as EE_FS_SPOT_GR: exchange price plus margin
# from April to September, a fixed rate from October to March. The months come
# from the page copy; the API states no season anywhere.
SEASONAL_CODE_SUBSTR = ("_FS_",)
SEASONAL_SPOT_MONTHS = [4, 5, 6, 7, 8, 9]
SEASONAL_MARGIN_ROW_KEYS = ("EE_SPOT_MARGIN", "EE_SPOT_GREEN")
# !! Deliberately empty. As of 2026-08 Enefit has not published the winter
# rate (the page promises it in August 2026), so the row key it will arrive
# under is unknown and no cent/kWh row may be assumed to be it. Until the real
# key is added here the package is withheld rather than half-priced.
SEASONAL_FIXED_ROW_KEYS: tuple[str, ...] = ()

# Keyed by the code with its term stripped, so a new term (EE_FIX_24M_BL)
# composes on its own and only a genuinely new product needs an entry here.
BASE_NAMES = {
    "SPOT_BL": "Muutuv",
    "SPOT_GR": "Muutuv Roheline",
    "FIX_BL": "Kindel",
    "FIX_GR": "Kindel Roheline",
    "FS_SPOT_GR": "Hooajakindel",
}


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


def _name(code: str, length: int | None) -> str:
    """Marketing name for a product code; unmapped codes keep the old
    code-derived name, which reads as machine output and says "add me"."""
    stripped = code.removeprefix("EE_")
    marketing = BASE_NAMES.get(re.sub(r"_\d+M", "", stripped))
    if marketing is None:
        return stripped.replace("_", " ").title()
    return f"{marketing} ({length} kuud)" if length else marketing


def _base_entry(p: dict, code: str, fee_eur: float) -> dict:
    return {
        "id": "enefit-" + code.lower().replace("_", "-"),
        "name": _name(code, p.get("length")),
        "monthly_fee_cents": int(round(fee_eur * 100 / VAT)),
        "contract_months": p.get("length"),
        "source_url": SOURCE_URL,
        "day_rate_cents_kwh": None, "night_rate_cents_kwh": None,
    }


def _seasonal_entry(p: dict, code: str) -> dict | None:
    """Hooajakindel -> type "seasonal": the exchange price plus margin during
    SEASONAL_SPOT_MONTHS, the fixed rate the rest of the year.

    Yields nothing while SEASONAL_FIXED_ROW_KEYS is empty, which is the point:
    the winter rate is not in the payload yet and picking whichever cent/kWh
    row shows up next would publish a wrong price on the day it appears."""
    margin, rate, fee_eur = 0.0, None, 0.0
    for row in p.get("retailProductRows", []):
        price = _current_price(row.get("prices"))
        if price is None:
            continue
        key = ((row.get("translation") or {}).get("translation")) or ""
        if row.get("currencySign") == "EUR" and row.get("unitOfMeasure") == "MONTH":
            fee_eur += price
        elif key in SEASONAL_FIXED_ROW_KEYS:
            rate = price
        elif key in SEASONAL_MARGIN_ROW_KEYS:
            margin += price
    if rate is None:
        return None
    return _base_entry(p, code, fee_eur) | {
        "type": "seasonal",
        "rate_cents_kwh": _ex_vat(rate),
        "margin_cents_kwh": _ex_vat(margin),
        "spot_months": list(SEASONAL_SPOT_MONTHS),
    }


def parse_payload(j: dict) -> list[dict]:
    out = []
    for fam in j.get("retailProductFamilies", []):
        fcode = fam.get("familyCode", "")
        if fcode in SKIP_FAMILIES:
            for p in fam.get("retailProducts", []):
                code = p.get("code", "")
                if any(s in code for s in SEASONAL_CODE_SUBSTR):
                    entry = _seasonal_entry(p, code)
                    if entry:
                        out.append(entry)
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
            entry = _base_entry(p, code, fee_eur)
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
