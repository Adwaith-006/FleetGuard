import logging
import os
import sys
try:
    from config.settings import DATA_DIR
except ImportError:
    from driver_service.config.settings import DATA_DIR


def setup_logger(name: str = "VehicleMonitor") -> logging.Logger:
    """
    Configures and returns a standardized logger for the vehicle system.
    Supports both console output and persistent file logging in data/driver_monitor.log.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 1. Console Stream Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 2. File Handler in data directory
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            log_file = os.path.join(DATA_DIR, "driver_monitor.log")
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass

    return logger


logger = setup_logger()

