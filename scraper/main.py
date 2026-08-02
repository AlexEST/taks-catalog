"""taks-catalog orchestrator: parsers + manual overrides -> catalog.json"""
import json, os, sys, pathlib, datetime
import requests

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from parsers import alexela, elektrum, enefit, viru, elenger

UA = "TaksCatalogBot/1.0 (+https://github.com/AlexEST/taks-catalog)"
PARSERS = {"Alexela": alexela.fetch_and_parse,
           "Elektrum": elektrum.fetch_and_parse,  # overrides UA, see elektrum.py
           "Enefit": enefit.fetch_and_parse,
           "Viru Elektrivorgud": viru.fetch_and_parse,
           "Elenger": elenger.fetch_and_parse}


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(p: pathlib.Path, default):
    # explicit utf-8: package names carry Estonian letters and the default
    # locale encoding is not utf-8 everywhere (cp1251 on the maintainer's box)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def write_atomic(p: pathlib.Path, text: str) -> None:
    """Temp file + os.replace, so a write that dies halfway (disk full, encoding
    error, killed job) leaves the published catalog.json untouched rather than
    truncated. os.replace is atomic on POSIX and on Windows."""
    tmp = p.with_name(p.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)
    finally:
        tmp.unlink(missing_ok=True)  # no-op after a successful replace


def main() -> int:
    previous = load_json(ROOT / "catalog.json", {"suppliers": []})
    prev_by_name = {s["name"]: s for s in previous.get("suppliers", [])}
    overrides = load_json(ROOT / "overrides.json", {"suppliers": []})

    session = requests.Session()
    session.headers["User-Agent"] = UA

    suppliers, failures = [], []
    for name, fn in PARSERS.items():
        try:
            packages = fn(session)
            assert packages, f"{name}: parser returned 0 packages"
            for p in packages:
                p["fetched_at"] = now()
            suppliers.append({"name": name, "stale": False, "packages": packages})
        except Exception as e:  # soft-fail: keep previous data, mark stale
            failures.append(f"{name}: {e}")
            prev = prev_by_name.get(name)
            if prev:
                prev["stale"] = True
                suppliers.append(prev)

    # manual overrides win on (supplier, package id); whole-supplier entries allowed
    for os_ in overrides.get("suppliers", []):
        existing = next((s for s in suppliers if s["name"] == os_["name"]), None)
        if existing is None:
            suppliers.append({**os_, "stale": False})
        else:
            ids = {p["id"] for p in os_["packages"]}
            existing["packages"] = [p for p in existing["packages"] if p["id"] not in ids]
            existing["packages"] += os_["packages"]

    catalog = {"schema_version": 1, "generated_at": now(),
               "suppliers": sorted(suppliers, key=lambda s: s["name"])}
    write_atomic(ROOT / "catalog.json",
                 json.dumps(catalog, indent=1, ensure_ascii=False) + "\n")

    print(f"OK: {sum(len(s['packages']) for s in suppliers)} packages, "
          f"{len(suppliers)} suppliers")
    if failures:
        print("FAILURES (kept previous data):", *failures, sep="\n  ")
        return 1  # CI goes red -> email notification, but catalog.json stays usable
    return 0


if __name__ == "__main__":
    sys.exit(main())
