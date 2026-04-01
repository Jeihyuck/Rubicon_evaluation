"""CLI entry point. Run with: python run.py"""

from __future__ import annotations

import sys

from app.main import run


def main() -> None:
    """Execute the Samsung Chat QA automation pipeline."""
    results = run()
    failed = sum(1 for r in results if r.status == "failed")
    print(f"\nDone. {len(results)} case(s) executed, {failed} failed.")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
