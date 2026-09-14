"""Download the Smogon usage file the pool's items and spreads are drawn from.

    python experiments/0057-pool-from-usage/fetch.py

One request for one public file. Reg M-B, because Smogon publishes a month's
statistics after the month ends and Reg M-C began on 2026-09-09; M-C is a
superset of M-B, and species M-B lacks fall back to open team sheets. The 1500
cutoff weights toward stronger players. Stored under `data/usage/`, which is
gitignored: third-party data, used locally and never republished.
"""

import urllib.request
from pathlib import Path

MONTH = "2026-08"
FILE = "gen9championsvgc2026regmb-1500.json.gz"
URL = f"https://www.smogon.com/stats/{MONTH}/chaos/{FILE}"
OUT = Path("data/usage") / f"{MONTH}-{FILE}"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        print(f"already present: {OUT} ({OUT.stat().st_size:,} bytes)")
        return
    request = urllib.request.Request(URL, headers={"User-Agent": "champions-ai research"})
    with urllib.request.urlopen(request, timeout=120) as response:
        OUT.write_bytes(response.read())
    print(f"downloaded {URL}\n  -> {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
