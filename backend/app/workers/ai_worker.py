import argparse
import time

from app.config import get_settings
from app.services.ai_job_queue import ai_job_queue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process durable BaladiGuard AI jobs.")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit.")
    parser.add_argument("--drain", action="store_true", help="Drain all currently available jobs.")
    parser.add_argument("--replay", metavar="JOB_ID", help="Replay one dead-lettered job.")
    args = parser.parse_args(argv)

    ai_job_queue.reconcile()
    if args.replay and not ai_job_queue.replay(args.replay):
        parser.error("job is missing, not dead-lettered, or its ticket cannot be reset")
    if args.once:
        ai_job_queue.run_once()
        return 0
    if args.drain:
        while ai_job_queue.run_once().outcome != "idle":
            pass
        return 0

    interval = get_settings().ai_job_poll_seconds
    while True:
        result = ai_job_queue.run_once()
        if result.outcome == "idle":
            time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
