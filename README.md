# taks-catalog

Public, versioned catalog of Estonian household electricity packages
(energy component only, prices VAT-exclusive, in euro cents per kWh).
Consumed by the Taks Android app as static JSON; git history doubles as
a free price archive.

## How it works
Daily GitHub Actions cron runs `scraper/main.py`:
site parsers (`scraper/parsers/`) + manual `overrides.json` -> `catalog.json`.
Commit happens only on change. A broken parser keeps the supplier's previous
data marked `"stale": true` and turns CI red (email notification) without
breaking the published file.

## Supplier status (recon 2026-08)
| Supplier | Method | Notes |
|---|---|---|
| Alexela | parser (`alexela.py`) | server-rendered Drupal, text-level labeled parsing, verified |
| Enefit | parser (`enefit.py`) | anonymous self-service API `iseteenindus.enefit.ee/api/v2/retail-products` discovered via XHR inspection 2026-08; VAT-inclusive, confirmed against the ET page; API ships no product names, so `BASE_NAMES` maps codes to the page's own labels |
| Elektrum | parser (`elektrum.py`) | public calculator API `minu.elektrum.ee/api/products`, found 2026-08 in the package page's `data-api-endpoints`; Smart-ID gates signing, not prices; ships VAT-exclusive values; quarterly Kaljukindel price rolls over on its own |
| Viru Elektrivõrgud (ex-VKG) | parser (`viru.py`) | server-rendered WordPress, ET labeled parsing, VAT-incl stated on page; sells nationwide despite Narva DSO roots |
| Elenger | parser (`elenger.py`) | spot margin public in HTML; fixed packages are quote-only ("from X") and intentionally not catalogued |
| 220 Energia | — merged into Alexela | invoices issued as AS Alexela; covered by the Alexela parser |

Non-backtestable package types (volume plans, virtual battery,
monthly-changing base rates, price-ceiling products, and packages whose green
surcharge is priced outside the energy component) are intentionally excluded.

## Package types (`schema_version: 2`)
Every package carries the full field set in a fixed order; fields that do not
apply are `null`. Cost of one kWh, given the hour's exchange price `spot`:

| `type` | cost per kWh | fields that matter |
|---|---|---|
| `fixed` | `rate` | `rate_cents_kwh` |
| `day_night` | `day` or `night` by hour | `day_rate_cents_kwh`, `night_rate_cents_kwh` |
| `spot` | `spot + margin` | `margin_cents_kwh` |
| `mixed` | `share * rate + (1 - share) * (spot + margin)` | `rate_cents_kwh`, `margin_cents_kwh`, `fixed_share` |
| `seasonal` | `spot + margin` in `spot_months`, `rate` otherwise | `rate_cents_kwh`, `margin_cents_kwh`, `spot_months` |

`mixed` and `spot_months` arrived with schema 2 (2026-08), for Elektrum's
Paindlik Klõps and Enefit's Hooajakindel. Version 1 consumers see no change to
the three original types, but will meet `type` values they do not know.
Hooajakindel is withheld until Enefit publishes its winter rate — see
`SEASONAL_FIXED_ROW_KEYS` in `enefit.py`.

## Good-citizen rules
robots.txt respected; identifying User-Agent linking here; one run per day;
every entry carries `source_url` + `fetched_at`; prices are public facts,
always verify current terms with the supplier before signing anything.

One exception to the User-Agent rule: `minu.elektrum.ee` answers 451 to any
User-Agent carrying a contact URL or e-mail, so `elektrum.py` sends the bare
product token `TaksCatalog/1.0` instead. Its robots.txt forbids nothing.
