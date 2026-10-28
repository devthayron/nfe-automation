import logging
from pathlib import Path


def setup_logging():
    """
    Configura o logging da aplicação no console e arquivo (logs/app.log).
    """

    Path("logs").mkdir(exist_ok=True)

    level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
        handlers=[
            logging.FileHandler("logs/app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
