import argparse
import json
from dataclasses import asdict

from app.evaluation.retrieval import summarize


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output")
    parser.add_argument("--min-recall", type=float, default=0.0)
    parser.add_argument("--min-citation-coverage", type=float, default=0.0)
    args = parser.parse_args()
    summary = summarize([], args.top_k)
    payload = asdict(summary)
    print(json.dumps(payload, indent=2))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2)
    return int(
        summary.recall_at_k < args.min_recall
        or summary.citation_coverage < args.min_citation_coverage
    )


if __name__ == "__main__":
    raise SystemExit(main())
