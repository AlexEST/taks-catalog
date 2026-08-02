"""Elenger parser.

Verified 2026-08: https://elenger.ee/en/estonian-gas/electricity/ is
server-rendered WordPress. Only the exchange (spot) package carries a
concrete public price ("Ex[c]hange rate price + 0,67 cents/kWh", VAT incl,
no monthly fee stated -> 0). Fixed packages are quote-based ("from X,
ask for an offer") and therefore intentionally NOT catalogued.
Regex tolerates the site's own spelling ("Excange").
"""
from __future__ import annotations
import re

SOURCE_URL = "https://elenger.ee/en/estonian-gas/electricity/"
SUPPLIER = "Elenger"
VAT = 1.24

RX_SPOT = re.compile(r"Exc?h?ange rate price\s*\+\s*([\d,\.]+)\s*cents?\s*/?\s*kWh", re.I)


def parse(text: str) -> list[dict]:
    m = RX_SPOT.search(text)
    if not m:
        return []
    margin = float(m.group(1).replace(",", "."))
    return [{
        "id": "elenger-exchange", "name": "Elenger Exchange",
        "type": "spot",
        "margin_cents_kwh": round(margin / VAT, 3),
        "rate_cents_kwh": None,
        "day_rate_cents_kwh": None, "night_rate_cents_kwh": None,
        "monthly_fee_cents": 0, "contract_months": None,
        "source_url": SOURCE_URL,
    }]


def fetch_and_parse(session) -> list[dict]:
    from bs4 import BeautifulSoup
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    return parse(BeautifulSoup(r.text, "html.parser").get_text("\n"))
