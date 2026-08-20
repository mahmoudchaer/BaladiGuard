import argparse
import time

from app.config import get_settings
from app.services.content_safety.queue import content_safety_queue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process ticket content-safety screening jobs.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--drain", action="store_true")
    args = parser.parse_args(argv)
    if args.once:
        content_safety_queue.run_once()
        return 0
    if args.drain:
        while content_safety_queue.run_once() != "idle":
            pass
        return 0
    while True:
        if content_safety_queue.run_once() == "idle":
            time.sleep(get_settings().ai_job_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
