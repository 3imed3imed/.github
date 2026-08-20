"""Unified CLI entry point: ``crime-factory <command>``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crime-factory", description="Crime YouTube Factory control CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Run health checks")
    sub.add_parser("setup", help="Run the setup wizard")
    p_run = sub.add_parser("run", help="Produce one story end-to-end")
    p_run.add_argument("--story", required=True)
    p_pipe = sub.add_parser("pipeline", help="Run the scheduled pipeline")
    p_pipe.add_argument("--stage-a", action="store_true")
    p_pipe.add_argument("--select-only", action="store_true")
    sub.add_parser("analytics", help="Run weekly analytics")
    sub.add_parser("cleanup", help="Prune intermediate render files")
    p_val = sub.add_parser("validate", help="Run a validation stage (A/B/C)")
    p_val.add_argument("--stage", required=True, choices=["a", "b", "c"])
    p_val.add_argument("--stories", default="")

    args = parser.parse_args(argv)

    if args.command == "health":
        from app.health import main as m

        return m([])
    if args.command == "setup":
        from app.setup_wizard import main as m

        return m(["--check"])
    if args.command == "run":
        from app.run import main as m

        return m(["--story", args.story])
    if args.command == "pipeline":
        extra = []
        if args.stage_a:
            extra.append("--stage-a")
        if args.select_only:
            extra.append("--select-only")
        from app.pipeline import main as m

        return m(extra)
    if args.command == "analytics":
        from app.analytics import AnalyticsEngine

        report = AnalyticsEngine().run_weekly()
        print(report.to_dict())
        return 0
    if args.command == "cleanup":
        from app.cleanup import main as m

        return m([])
    if args.command == "validate":
        extra = ["--stage", args.stage]
        if args.stories:
            extra += ["--stories", args.stories]
        from app.validate import main as m

        return m(extra)
    return 1


if __name__ == "__main__":
    sys.exit(main())
