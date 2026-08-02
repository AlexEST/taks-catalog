"""Viru Elektrivõrgud (ex-VKG) parser.

Verified 2026-08: https://viruev.ee/elektrimuuk/elektrienergia-pakett/
is server-rendered WordPress; prices in HTML, explicitly VAT-inclusive
("käibemaksuga"). Estonian labeled-text parsing.

Packages observed:
  Viru Kindel  -> fixed, N-month term, 1-tariff and 2-tariff variants
  Viru Vaba    -> spot, margin differs by dwelling (Korter/Maja)
  Viru Roheline-> green spot, no public price on page -> skipped
"""
from __future__ import annotations
import re

SOURCE_URL = "https://viruev.ee/elektrimuuk/elektrienergia-pakett/"
SUPPLIER = "Viru Elektrivõrgud"
VAT = 1.24

RX_TERM = re.compile(r"Fikseeritud hind.*?(\d+)\s*kuud", re.S | re.I)
RX_2TAR = re.compile(
    r"Kahetariifne:\s*p[aä]ev\s+([\d,]+)\s*s/kWh\s+ja\s+[oö][oö]\s+([\d,]+)\s*s/kWh,\s*kuutasu\s+([\d,]+)", re.I)
RX_1TAR = re.compile(r"[UÜ]hetariifne:\s*([\d,]+)\s*s/kWh,\s*kuutasu\s+([\d,]+)", re.I)
RX_SPOT = re.compile(
    r"(Korter|Maja):\s*marginaal\s+([\d,]+)\s*s/kWh\s+ja\s+kuutasu\s+([\d,]+)", re.I)


def _n(s: str) -> float:
    return float(s.replace(",", "."))


def _ex(v: float) -> float:
    return round(v / VAT, 3)


def parse(text: str) -> list[dict]:
    out = []
    term = RX_TERM.search(text)
    months = int(term.group(1)) if term else None
    base = {"source_url": SOURCE_URL, "margin_cents_kwh": None,
            "rate_cents_kwh": None, "day_rate_cents_kwh": None,
            "night_rate_cents_kwh": None}

    m = RX_2TAR.search(text)
    if m:
        out.append(base | {
            "id": "viru-kindel-2tar", "name": "Viru Kindel (2-tariifne)",
            "type": "day_night",
            "day_rate_cents_kwh": _ex(_n(m.group(1))),
            "night_rate_cents_kwh": _ex(_n(m.group(2))),
            "monthly_fee_cents": int(round(_n(m.group(3)) * 100 / VAT)),
            "contract_months": months})
    m = RX_1TAR.search(text)
    if m:
        out.append(base | {
            "id": "viru-kindel-1tar", "name": "Viru Kindel (1-tariifne)",
            "type": "fixed",
            "rate_cents_kwh": _ex(_n(m.group(1))),
            "monthly_fee_cents": int(round(_n(m.group(2)) * 100 / VAT)),
            "contract_months": months})
    for dwell, margin, fee in RX_SPOT.findall(text):
        out.append(base | {
            "id": f"viru-vaba-{dwell.lower()}", "name": f"Viru Vaba ({dwell})",
            "type": "spot",
            "margin_cents_kwh": _ex(_n(margin)),
            "monthly_fee_cents": int(round(_n(fee) * 100 / VAT)),
            "contract_months": None})
    return out


def fetch_and_parse(session) -> list[dict]:
    from bs4 import BeautifulSoup
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    return parse(BeautifulSoup(r.text, "html.parser").get_text("\n"))
