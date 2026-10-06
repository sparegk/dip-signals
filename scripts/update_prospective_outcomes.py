"""Daily outcome attachment alias; original decisions and review embargo remain unchanged."""

from scripts.attach_prospective_outcomes import main


if __name__ == "__main__":
    root = main()
    import json
    from src.scanner_outcomes import attach_benchmarks
    print(json.dumps(attach_benchmarks(root)))
