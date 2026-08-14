import argparse
import time

from app.config import get_settings
from app.services.redaction.queue import image_redaction_queue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process private report image redaction jobs.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--drain", action="store_true")
    args = parser.parse_args(argv)
    if args.once:
        image_redaction_queue.run_once()
        return 0
    if args.drain:
        while image_redaction_queue.run_once() != "idle":
            pass
        return 0
    while True:
        if image_redaction_queue.run_once() == "idle":
            time.sleep(get_settings().ai_job_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
