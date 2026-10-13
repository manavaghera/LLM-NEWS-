"""Validated command-line options for the quick news writer."""
import argparse
import re
from datetime import datetime


def parse_options(feeds):
    parser = argparse.ArgumentParser(description="Build website articles from RSS feeds with one LLM.")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--per-category", type=int, help="articles per category (default 3; 2 per --update)")
    parser.add_argument("--per-feed", type=int, default=6, help="newest items read from each feed (default 6)")
    parser.add_argument("--similarity", type=float, default=0.2, help="story similarity, 0-1 (default 0.2)")
    parser.add_argument("--no-images", action="store_true", help="don't download article images")
    parser.add_argument("--no-audio", action="store_true", help="don't generate audio summaries")
    parser.add_argument("--no-full-text", action="store_true", help="use RSS summaries only")
    parser.add_argument("--no-checks", action="store_true", help="skip fact-check and coverage comparison")
    parser.add_argument("--source-briefs", action="store_true",
                        help="publish concise source-feed briefs without calling the writing model")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing edition after generation succeeds")
    parser.add_argument("--append", action="store_true", help="add to an edition")
    parser.add_argument("--update", action="store_true", help="append only events not already covered today")
    parser.add_argument("--categories", default=",".join(feeds), help="comma-separated categories")
    args = parser.parse_args()
    args.append = args.append or args.update
    if args.source_briefs:
        args.no_checks = True
    if args.overwrite and args.append:
        parser.error("--overwrite cannot be combined with --append or --update")
    if (args.per_category is not None and args.per_category < 1) or args.per_feed < 1:
        parser.error("--per-category and --per-feed must be positive")
    if not 0 <= args.similarity <= 1:
        parser.error("--similarity must be between 0 and 1")
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
            raise ValueError("non-canonical date")
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        parser.error("--date must be a real date in YYYY-MM-DD format")
    args.categories = list(dict.fromkeys(c.strip() for c in args.categories.split(",") if c.strip()))
    if not args.categories or any(c not in feeds for c in args.categories):
        parser.error(f"--categories must be chosen from {', '.join(feeds)}")
    return args
