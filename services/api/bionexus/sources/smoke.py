"""Live smoke test: `python -m bionexus.sources.smoke`. Proves a real request worked (SOURCE-09)."""

from bionexus.contracts.errors import SourceUnavailable
from bionexus.sources.http import GuardedHttp
from bionexus.sources.live import live_sources


def main() -> int:
    failures = 0
    for source in live_sources(GuardedHttp()):
        try:
            records = source.search("Crohn disease", ("NOD2",))
            print(f"{source.name:15} OK   {len(records)} record(s)")
        except SourceUnavailable as error:
            failures += 1
            print(f"{source.name:15} FAIL {error}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
