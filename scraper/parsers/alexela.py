"""Alexela parser.

Verified 2026-08: https://www.alexela.ee/et/elekter is server-rendered (Drupal),
all package prices are present in the HTML. Displayed prices INCLUDE 24% VAT.

Reads the Estonian page, not /en/. The EN locale carries the same packages at
the same prices, but its headings are English ("Exchange rate electricity"),
which is what the catalogue then published while every other supplier here is
named in Estonian. Names come from the page, so the locale is the fix; nothing
downstream can rename a package it only ever receives in English.

Strategy: parse at TEXT level (labeled lines), not CSS selectors — survives
theme/class renames; breaks only if label wording changes, which is rare and
loudly detectable (zero packages extracted -> stale + CI failure).

Note the labels sit next to prose that reads much like them: the bullet
"Börsihind + marginaal" carries no number, and "Eelmise kuu keskmine börsihind
8,23 s/kWh" is last month's average exchange price, not a contract rate. Both
are excluded by requiring the exact label word immediately before the figure.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

SOURCE_URL = "https://www.alexela.ee/et/elekter"
SUPPLIER = "Alexela"
VAT = 1.24  # prices on page are VAT-inclusive

# Labeled-value patterns as seen on the live page (ET locale; cents are "senti",
# so the unit reads s/kWh). The page spells its diacritics properly today; the
# vowel classes are the same cheap ASCII insurance viru.py already carries.
RX = {
    "margin": re.compile(r"Marginaal\s+([\d.,]+)\s*s\s*/\s*kWh", re.I),
    "monthly_fee": re.compile(r"Kuutasu\s+([\d.,]+)\s*€", re.I),
    "day": re.compile(r"P[aä]eva hind\s+([\d.,]+)\s*s\s*/\s*kWh", re.I),
    "night": re.compile(r"[oö][oö] hind\s+([\d.,]+)\s*s\s*/\s*kWh", re.I),
    "base": re.compile(r"Baashind\s+([\d.,]+)\s*s\s*/\s*kWh", re.I),
    "volume": re.compile(r"mahu piires|mahtu [uü]letava", re.I),
}
# Package block = heading line followed by its labeled lines, until next heading.
# Headings on the page are short lines without a labeled value.
KNOWN_HEADINGS = re.compile(
    r"^(Vali ise|Paindlik fiks|Kindel maht|T[aä]htajaline fikseeritud hind|"
    r"Pingevaba|Virtuaalaku.*|Fikseeritud hinnaga elekter|"
    r"Alexela Kodupakett elekter|B[oö]rsihinnaga elekter)$",
    re.I,
)

# Estonian ids, same convention as elektrum.py: diacritics fold to ASCII rather
# than being dropped, or "Börsihinnaga" would slug to "b-rsihinnaga".
TRANSLIT = str.maketrans({"õ": "o", "ä": "a", "ö": "o", "ü": "u",
                          "š": "s", "ž": "z"})


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().translate(TRANSLIT)).strip("-")


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

    if RX["volume"].search(t) or "virtuaalaku" in b.name.lower():
        return None  # volume plans / virtual battery: not representable in v1
    if base and margin:
        return None  # Pingevaba: monthly-changing base price, not backtestable v1
    entry = {
        "id": "alexela-" + _slug(b.name),
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
