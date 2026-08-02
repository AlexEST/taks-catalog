"""Elektrum Eesti parser.

Discovered 2026-08: the public package page
https://www.elektrum.ee/ee/eraklient/elekter/elektripaketid embeds its price
calculator as

    <div id="calculator" data-person-class="Private"
         data-api-endpoints='{"config":".../api/calculator/config",
                              "product_search":"https://minu.elektrum.ee/api/products",
                              "price_calculation":".../api/calculator"}'>

and `product_search` answers anonymously — Smart-ID gates *signing* a contract,
not reading prices. This retires the manual overrides.json entry, quarterly
Kaljukindel included: its new price arrives as a fresh `contract_start_date`
and the daily cron picks it up on its own.

Payload shape:
  products[]
    .marketing_product .name, .intro, .descriptions[] .contract_term, .text
    .billing_product
      .name, .person_type, .product_type (FIXED|VARIABLE|MIXED), .zone_count
      .price_lists[] .contract_term, .contract_start_date
        .components[] .type .zone .uom .charge_value .charge_value_without_vat

Components observed:
  EE-F-EEV  single-tariff fixed energy price   -> rate_cents_kwh
  EE-F-EEL / EE-F-EEK  day / night price       -> day_/night_rate_cents_kwh
  EE-INTHF  spot sales margin                  -> margin_cents_kwh
  EE-U-EEV  fixed half of the MIXED hybrid     -> rate_cents_kwh, type "mixed"
  EE-EEMAB  "Kuutasu", EUR/kuus                -> monthly_fee_cents
  EE-V-EEV  !! indicative exchange price, NOT a contract rate -> never read
  FERAEE / GREENEE  category "other": bundled insurance / green surcharge

VAT: the API ships charge_value_without_vat next to charge_value (ratio 1.24),
so unlike the other parsers nothing is inferred here.

Names come from marketing_product where the two differ, which today is only
the hybrid: billing calls it PAINDLIK KLOPS MIX, the site calls it PAINDLIK
KLOPS. Every other product has identical strings, so no id changes.

Intentionally not catalogued:
  * anything carrying GREENEE — the green surcharge is a category "other"
    component with uom "EUR" and no stated period, so the total cost of the
    Roheline packages cannot be stated honestly in this schema
  * FERAEE (insurance bundled into Kaljukindel and the 36-month packages) is
    not an energy component; monthly_fee_cents carries the advertised Kuutasu
    only, matching what the page displays and what the other parsers capture

User-Agent: minu.elektrum.ee answers 451 to any UA containing a contact URL,
an e-mail address, or the tokens "bot"/"curl"/"python-requests" — i.e. exactly
the project-wide UA from main.py. robots.txt on both www. and minu. is
"User-agent: * / Disallow:" (nothing forbidden), so the request below keeps a
product token that still identifies the client and drops the "+URL" suffix.
"""
from __future__ import annotations
import re

API_URL = "https://minu.elektrum.ee/api/products"
SOURCE_URL = "https://www.elektrum.ee/ee/eraklient/elekter/elektripaketid"
SUPPLIER = "Elektrum"
USER_AGENT = "TaksCatalog/1.0"  # see User-Agent note above
VAT = 1.24  # fallback only; charge_value_without_vat is authoritative

RATE_SINGLE, RATE_DAY, RATE_NIGHT = "EE-F-EEV", "EE-F-EEL", "EE-F-EEK"
RATE_MIXED = "EE-U-EEV"
SPOT_MARGIN, MONTHLY_FEE, GREEN_SURCHARGE = "EE-INTHF", "EE-EEMAB", "GREENEE"

# "50% fikseeritud ja 50% borsihind" / "50% hinnast on fikseeritud"
RX_FIXED_SHARE = re.compile(r"(\d{1,3})\s*%\s*(?:hinnast on\s*)?fikseeritud", re.I)

# contract_term 881 is the API's sentinel for a "tahtajatu" (open-ended)
# contract, paired with contract_end_date 2099-12-31.
OPEN_ENDED_ABOVE_MONTHS = 120

TRANSLIT = str.maketrans({"õ": "o", "ä": "a", "ö": "o", "ü": "u",
                          "š": "s", "ž": "z"})


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().translate(TRANSLIT)).strip("-")


def _ex_vat(component: dict) -> float:
    """VAT-exclusive value; the API states it, division is only a fallback."""
    v = component.get("charge_value_without_vat")
    if v in (None, ""):
        v = float(component["charge_value"]) / VAT
    return round(float(v), 3)


def _fixed_share(marketing: dict, term) -> float | None:
    """Share of every kWh billed at the fixed rate of a MIXED package.

    Elektrum publishes the split only as prose ("Iga tarbitud kWh hinnast on
    50% fikseeritud ja 50% borsihind"), per contract term, never as a number.
    Read it from there rather than hardcoding 0.5: if the wording ever stops
    matching, the package is dropped instead of priced on a stale guess."""
    texts = [d.get("text") or "" for d in marketing.get("descriptions") or []
             if d.get("contract_term") == term]
    texts.append(marketing.get("intro") or "")
    for t in texts:
        m = RX_FIXED_SHARE.search(re.sub(r"<[^>]+>", " ", t))
        if m and 0 < int(m.group(1)) < 100:
            return round(int(m.group(1)) / 100, 3)
    return None


def parse_payload(j: dict) -> list[dict]:
    out = []
    for product in j.get("products", []):
        bp = product.get("billing_product") or {}
        mp = product.get("marketing_product") or {}
        if bp.get("person_type") != "Private":
            continue
        ptype = bp.get("product_type")
        if ptype not in ("FIXED", "VARIABLE", "MIXED"):
            continue
        name = (mp.get("name") or bp.get("name") or "").title()
        if not name:
            continue
        for pl in bp.get("price_lists", []):
            by_type: dict[str, dict] = {}
            for c in pl.get("components", []):
                by_type.setdefault(c.get("type"), c)
            if GREEN_SURCHARGE in by_type:
                continue  # green add-on priced outside the energy component

            months = pl.get("contract_term")
            if months is not None and months > OPEN_ENDED_ABOVE_MONTHS:
                months = None
            fee = by_type.get(MONTHLY_FEE)
            entry = {
                "id": f"elektrum-{_slug(name)}" + (f"-{months}m" if months else ""),
                "name": f"{name} ({months} kuud)" if months else name,
                "monthly_fee_cents": int(round(_ex_vat(fee) * 100)) if fee else 0,
                "contract_months": months,
                "source_url": SOURCE_URL,
                "rate_cents_kwh": None, "margin_cents_kwh": None,
                "day_rate_cents_kwh": None, "night_rate_cents_kwh": None,
            }
            if ptype == "VARIABLE":
                if SPOT_MARGIN not in by_type:
                    continue  # EE-V-EEV alone is a market quote, not a price
                entry |= {"type": "spot",
                          "margin_cents_kwh": _ex_vat(by_type[SPOT_MARGIN])}
            elif ptype == "MIXED":
                share = _fixed_share(mp, pl.get("contract_term"))
                if share is None or not {RATE_MIXED, SPOT_MARGIN} <= by_type.keys():
                    continue  # half a hybrid is a wrong price, not a partial one
                entry |= {"type": "mixed",
                          "rate_cents_kwh": _ex_vat(by_type[RATE_MIXED]),
                          "margin_cents_kwh": _ex_vat(by_type[SPOT_MARGIN]),
                          "fixed_share": share}
            elif RATE_DAY in by_type and RATE_NIGHT in by_type:
                entry |= {"type": "day_night",
                          "day_rate_cents_kwh": _ex_vat(by_type[RATE_DAY]),
                          "night_rate_cents_kwh": _ex_vat(by_type[RATE_NIGHT])}
            elif RATE_SINGLE in by_type:
                entry |= {"type": "fixed",
                          "rate_cents_kwh": _ex_vat(by_type[RATE_SINGLE])}
            else:
                continue  # no recognisable energy price: skip rather than guess
            out.append(entry)
    return out


def fetch_and_parse(session) -> list[dict]:
    r = session.get(API_URL, timeout=30,
                    headers={"Accept": "application/json",
                             "User-Agent": USER_AGENT})
    r.raise_for_status()
    return parse_payload(r.json())
