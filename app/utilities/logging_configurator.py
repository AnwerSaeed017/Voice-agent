import logging
import sys

from app.interfaces.utilities import ILoggingConfigurator


class StdoutLoggingConfigurator(ILoggingConfigurator):
    """Sends application logs to stdout, where Railway (or any host) collects them."""

    def configure(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            stream=sys.stdout,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
