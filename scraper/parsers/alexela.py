"""Alexela parser.

Verified 2026-08: https://www.alexela.ee/en/elekter is server-rendered (Drupal),
all package prices are present in the HTML. Displayed prices INCLUDE 24% VAT.

Strategy: parse at TEXT level (labeled lines), not CSS selectors — survives
theme/class renames; breaks only if label wording changes, which is rare and
loudly detectable (zero packages extracted -> stale + CI failure).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

SOURCE_URL = "https://www.alexela.ee/en/elekter"
SUPPLIER = "Alexela"
VAT = 1.24  # prices on page are VAT-inclusive

# Labeled-value patterns as seen on the live page (EN locale)
RX = {
    "margin": re.compile(r"Margin\s+([\d.,]+)\s*c\s*/\s*kWh", re.I),
    "monthly_fee": re.compile(r"Monthly fee\s+([\d.,]+)\s*€", re.I),
    "day": re.compile(r"Daytime rate\s+([\d.,]+)\s*c\s*/\s*kWh", re.I),
    "night": re.compile(r"Nighttime rate\s+([\d.,]+)\s*c\s*/\s*kWh", re.I),
    "base": re.compile(r"Base price\s+([\d.,]+)\s*c\s*/\s*kWh", re.I),
    "volume": re.compile(r"volume limit", re.I),
}
# Package block = heading line followed by its labeled lines, until next heading.
# Headings on the page are short lines without a labeled value.
KNOWN_HEADINGS = re.compile(
    r"^(Choose Yourself|Flexible Fix|Fixed Plan|Term fixed rate|Stressless|"
    r"Virtual battery.*|Fixed price|Alexela'?s Home package|Exchange rate electricity)$",
    re.I,
)


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _ex_vat(cents: float) -> float:
    return round(cents / VAT, 3)


@dataclass
class Block:
    name: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def split_blocks(page_text: str) -> list[Block]:
    blocks: list[Block] = []
    cur: Block | None = None
    for raw in page_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if KNOWN_HEADINGS.match(line):
            cur = Block(name=line)
            blocks.append(cur)
        elif cur is not None:
            cur.lines.append(line)
    return blocks


def classify(b: Block) -> dict | None:
    """Map a block to catalog schema; return None for non-backtestable types."""
    t = b.text
    margin = RX["margin"].search(t)
    fee = RX["monthly_fee"].search(t)
    day, night = RX["day"].search(t), RX["night"].search(t)
    base = RX["base"].search(t)

    if RX["volume"].search(t) or "battery" in b.name.lower():
        return None  # volume plans / virtual battery: not representable in v1
    if base and margin:
        return None  # Stressless: monthly-changing base price, not backtestable v1
    entry = {
        "id": "alexela-" + re.sub(r"[^a-z0-9]+", "-", b.name.lower()).strip("-"),
        "name": b.name,
        "monthly_fee_cents": int(round(_num(fee.group(1)) * 100 / VAT)) if fee else 0,
        "contract_months": None,
        "source_url": SOURCE_URL,
    }
    if day and night:
        entry |= {
            "type": "day_night",
            "day_rate_cents_kwh": _ex_vat(_num(day.group(1))),
            "night_rate_cents_kwh": _ex_vat(_num(night.group(1))),
            "rate_cents_kwh": None, "margin_cents_kwh": None,
        }
        return entry
    if margin:
        entry |= {
            "type": "spot",
            "margin_cents_kwh": _ex_vat(_num(margin.group(1))),
            "rate_cents_kwh": None,
            "day_rate_cents_kwh": None, "night_rate_cents_kwh": None,
        }
        return entry
    return None


def parse(page_text: str) -> list[dict]:
    out = []
    for b in split_blocks(page_text):
        e = classify(b)
        if e:
            out.append(e)
    return out


def fetch_and_parse(session) -> list[dict]:
    from bs4 import BeautifulSoup
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    text = BeautifulSoup(r.text, "html.parser").get_text("\n")
    return parse(text)
