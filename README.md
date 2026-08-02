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
| Enefit | parser (`enefit.py`) | anonymous self-service API `iseteenindus.enefit.ee/api/v2/retail-products` discovered via XHR inspection 2026-08; VAT status to verify on first live run |
| Elektrum | manual override | calculator behind Smart-ID login (verified 2026-08); quarterly prices, hand-update ~4x/year |
| Viru Elektrivorgud (ex-VKG) | parser (`viru.py`) | server-rendered WordPress, ET labeled parsing, VAT-incl stated on page; sells nationwide despite Narva DSO roots |
| Elenger | parser (`elenger.py`) | spot margin public in HTML; fixed packages are quote-only ("from X") and intentionally not catalogued |
| 220 Energia | — merged into Alexela | invoices issued as AS Alexela; covered by the Alexela parser |

Non-backtestable package types (volume plans, virtual battery,
monthly-changing base rates) are intentionally excluded.

## Good-citizen rules
robots.txt respected; identifying User-Agent linking here; one run per day;
every entry carries `source_url` + `fetched_at`; prices are public facts,
always verify current terms with the supplier before signing anything.
