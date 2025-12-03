from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv
load_dotenv()



BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://172.20.10.2:6370/0")
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)

app = Celery(
    "alerts_worker",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["tasks"],  # используем относительный путь
)

app.conf.timezone = "Asia/Tashkent"

app.conf.beat_schedule = {
    "scan-alerts-every-5-min": {
        "task": "tasks.scan_alerts_and_send_sms",  # используем относительный путь
        "schedule": crontab(minute="*/5"),  # каждые 5 минут
    },
}
