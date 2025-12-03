import os
import psycopg2
from sms import send_sms
import time
from dotenv import load_dotenv

load_dotenv()

RECEIVER = os.getenv("RECEIVER", "+998909192558")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "172.20.10.2"),  # это порт, проброшенный из Docker
    "port": int(os.getenv("DB_PORT", 5433)),
    "dbname": os.getenv("DB_NAME", "sms_send"),
    "user": os.getenv("DB_USER", "sms_user"),
    "password": os.getenv("DB_PASSWORD", "123456"),
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_new_alerts_and_mark_processing(batch_size=20):
    """
    Берёт пачку new-алертов и сразу помечает их как processing.
    Возвращает список dict'ов.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, message
                    FROM jobs_alert
                    WHERE status = 'new'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                    """,
                    (batch_size,),
                )
                rows = cur.fetchall()
                if not rows:
                    return []

                ids = [r[0] for r in rows]

                cur.execute(
                    """
                    UPDATE jobs_alert
                    SET status = 'in_process'
                    WHERE id = ANY(%s)
                    """,
                    (ids,),
                )

        # преобразуем в список словарей
        return [{"id": r[0], "message": r[1]} for r in rows]
    finally:
        conn.close()


def mark_done(alert_id):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs_alert
                    SET status = 'sent'
                    WHERE id = %s
                    """,
                    (alert_id,),
                )
    finally:
        conn.close()


def mark_error(alert_id, error_text):
    """
    Помечает алерт как error.
    Примечание: если в таблице есть колонка error_text, можно раскомментировать её использование.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # Если колонка error_text существует, используйте:
                # cur.execute(
                #     """
                #     UPDATE jobs_alert
                #     SET status = 'error', error_text = %s, processed_at = now()
                #     WHERE id = %s
                #     """,
                #     (error_text[:500], alert_id),
                # )
                # Иначе просто обновляем статус:
                cur.execute(
                    """
                    UPDATE jobs_alert
                    SET status = 'error'
                    WHERE id = %s
                    """,
                    (alert_id,),
                )
                # Логируем ошибку в консоль для отладки
                print(f"Alert {alert_id} failed: {error_text[:200]}")
    finally:
        conn.close()


def process_alerts_and_send_sms(batch_size=20, receiver=None, sleep_seconds=1):
    """
    Обрабатывает алерты и отправляет SMS.
    
    Args:
        batch_size: количество алертов для обработки за раз
        receiver: номер телефона получателя (если None, используется RECEIVER)
        sleep_seconds: задержка между отправками SMS
    
    Returns:
        dict с результатами обработки
    """
    if receiver is None:
        receiver = RECEIVER
    
    alerts = fetch_new_alerts_and_mark_processing(batch_size=batch_size)
    
    if not alerts:
        return {"processed": 0, "success": 0, "errors": 0}
    
    success_count = 0
    error_count = 0
    
    for alert in alerts:
        alert_id = alert["id"]
        message = alert["message"]
        
        try:
            send_sms(receiver, message, modem_id="1")
            mark_done(alert_id)
            success_count += 1
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        except Exception as e:
            mark_error(alert_id, str(e))
            error_count += 1
    
    return {
        "processed": len(alerts),
        "success": success_count,
        "errors": error_count
    }

