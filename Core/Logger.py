import logging
import os
from datetime import datetime

LOG_DIR = "Logs"

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

current_date = datetime.now().strftime("%Y-%m-%d")

logging.basicConfig(
    level=logging.INFO,
    #level=logging.DEBUG,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"FC Rollback Tool {current_date}.log"), mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("FCRollbackTool")