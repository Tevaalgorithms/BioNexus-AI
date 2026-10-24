"""Worker entrypoint: `python -m bionexus.cli.worker`. Polls the durable job table."""

import signal
import time
from pathlib import Path

from bionexus.bootstrap import production_container
from bionexus.observability import configure_logging, log_event

POLL_SECONDS = 2.0
# Liveness marker read by the container health check; /tmp is a private tmpfs in the container.
HEARTBEAT_FILE = Path("/tmp/bionexus-worker-heartbeat")  # nosec B108


def main() -> None:
    configure_logging()
    app = production_container()
    running = True

    def stop(*_) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    log_event("worker.started")
    while running:
        app.worker.run_pending()
        HEARTBEAT_FILE.write_text(str(time.time()))  # read by the container health check
        time.sleep(POLL_SECONDS)
    log_event("worker.stopped")


if __name__ == "__main__":
    main()
