import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scraper"))
import main

spot = main.normalize({"id": "x-spot", "name": "X", "type": "spot",
                       "margin_cents_kwh": 0.5, "monthly_fee_cents": 100,
                       "source_url": "https://example.test"})

# the whole field set, in schema order, whatever the parser bothered to emit
assert list(spot) == list(main.PACKAGE_FIELDS), list(spot)
assert spot["rate_cents_kwh"] is None and spot["fixed_share"] is None
assert spot["spot_months"] is None and spot["fetched_at"] is None
assert spot["margin_cents_kwh"] == 0.5

# the v2 types keep their own fields
mixed = main.normalize({"id": "x-mixed", "type": "mixed", "rate_cents_kwh": 13.367,
                        "margin_cents_kwh": 0.446, "fixed_share": 0.5})
assert mixed["fixed_share"] == 0.5 and mixed["rate_cents_kwh"] == 13.367
seasonal = main.normalize({"id": "x-seasonal", "type": "seasonal",
                           "spot_months": [4, 5, 6, 7, 8, 9]})
assert seasonal["spot_months"] == [4, 5, 6, 7, 8, 9]

# an unknown key is kept and pushed to the end, never silently dropped
odd = main.normalize({"id": "x-odd", "surprise": 42})
assert odd["surprise"] == 42 and list(odd)[-1] == "surprise"

# normalizing twice changes nothing (previous-run data goes through it again)
assert main.normalize(spot) == spot

print("ALL TESTS PASSED, schema_version", 2, "fields:", len(main.PACKAGE_FIELDS))
