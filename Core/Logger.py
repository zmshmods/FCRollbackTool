# --------------------------------------- Standard Libraries ---------------------------------------
import logging
import os
from datetime import datetime

# إنشاء مجلد خاص باللوق إذا لم يكن موجودًا
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# الحصول على التاريخ الحالي بتنسيق (YYYY-MM-DD)
current_date = datetime.now().strftime("%Y-%m-%d")

# إعداد نظام اللوقينق
logging.basicConfig(
    level=logging.INFO,  # مستوى اللوجينغ يتم ضبطه على INFO لتجاهل DEBUG
    format="%(asctime)s  [%(levelname)s]  %(message)s",  # تنسيق الرسالة مع إضافة التاريخ
    datefmt="%Y-%m-%d %H:%M:%S",  # تنسيق التاريخ
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"FC Rollback Tool {current_date}.log"), mode="a", encoding="utf-8"),  # تسجيل في ملف
        logging.StreamHandler(),  # طباعة إلى الـ terminal
    ],
)

# الحصول على logger instance
logger = logging.getLogger("FCRollbackTool")
