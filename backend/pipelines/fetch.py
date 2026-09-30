"""Download raw data (cached; safe to re-run).

uv run python -m pipelines.fetch --source wb2 [--phase 1] [--dry-run]
uv run python -m pipelines.fetch --source open_meteo [--dry-run]
uv run python -m pipelines.fetch --source imd
uv run python -m pipelines.fetch --source synthetic    # nothing to download
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="wb2", choices=["wb2", "open_meteo", "imd", "synthetic"])
    ap.add_argument("--phase", help="WeatherBench 2 phase name or index")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.source == "wb2":
        from ml.data import weatherbench2

        extra = (["--phase", args.phase] if args.phase else []) + (
            ["--dry-run"] if args.dry_run else []
        )
        weatherbench2.main(extra)
    elif args.source == "open_meteo":
        from ml.data import open_meteo

        open_meteo.fetch(dry_run=args.dry_run)
    elif args.source == "imd":
        from ml.data import imd

        imd.fetch()
    else:
        print(
            "synthetic data is generated locally by `make dataset SOURCE=synthetic`; nothing to fetch."
        )


if __name__ == "__main__":
    main()
