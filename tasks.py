from celery_app import app
import db


@app.task
def scan_alerts_and_send_sms():
    """
    Периодическая задача Celery:
      - достаёт new-алерты
      - помечает их processing
      - отправляет SMS
      - обновляет статус done/error
    """
    result = db.process_alerts_and_send_sms(batch_size=5, sleep_seconds=1)
    
    if result["processed"] == 0:
        return "no alerts"
    
    return f"processed {result['processed']} alerts: {result['success']} success, {result['errors']} errors"
