import logging
from logging.handlers import RotatingFileHandler

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s – %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    if name == "llm":
        console.setLevel(logging.WARNING)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        "rag_pipeline.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(file_handler)

    return logger