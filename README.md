# only_sender

Сервис автоматической отправки SMS-уведомлений по алертам из базы данных. Использует Celery для планирования задач и ModemManager (`mmcli`) для отправки SMS через физический сотовый модем.

## Назначение

Каждую минуту воркер проверяет таблицу `jobs_alert` в PostgreSQL, забирает новые алерты (до 5 штук) и отправляет их содержимое по SMS на заданный номер телефона.

## Как это работает

```
Celery Beat (каждую 1 минуту)
       │
       ▼
scan_alerts_and_send_sms()
       │
       ▼
PostgreSQL: SELECT из jobs_alert WHERE status = 'new'
            ORDER BY created_at LIMIT 5
            FOR UPDATE SKIP LOCKED
       │
       ▼
Пометка алертов как 'in_process'
       │
       ▼
Для каждого алерта:
  ├─ mmcli -m 1 --messaging-create-sms=text='...',number='...'
  ├─ mmcli -s <sms_id> --send
  ├─ Успех  → статус 'sent'
  └─ Ошибка → статус 'error'
```

### Жизненный цикл алерта

```
new → in_process → sent
                 → error
```

### Безопасность при конкурентном доступе

Выборка алертов использует `FOR UPDATE SKIP LOCKED` — несколько воркеров не будут обрабатывать один и тот же алерт.

## Структура проекта

```
only_sender/
├── celery_app.py         # Конфигурация Celery, расписание задач
├── tasks.py              # Определение периодической задачи
├── db.py                 # Работа с PostgreSQL (выборка, обновление статусов)
├── sms.py                # Отправка SMS через ModemManager (mmcli)
├── __init__.py           # Пустой файл, делает директорию Python-пакетом
├── requirements.txt      # Python-зависимости
├── celerybeat-schedule   # Файл состояния Beat (генерируется автоматически)
└── .env                  # Переменные окружения (создать вручную)
```

## Требования к инфраструктуре

- **Python 3.8+**
- **Redis** — брокер сообщений для Celery
- **PostgreSQL** — база данных с таблицей `jobs_alert`
- **ModemManager** — установлен и настроен, сотовый модем подключён с ID `1`
- **sudo** — доступ без пароля для команд `mmcli`

## Установка

```bash
git clone <repo-url>
cd only_sender
pip install -r requirements.txt
```

## Настройка

Создайте файл `.env` в корне проекта:

```env
CELERY_BROKER_URL=redis://172.20.10.2:6370/0
CELERY_RESULT_BACKEND=redis://172.20.10.2:6370/0

DB_HOST=172.20.10.2
DB_PORT=5433
DB_NAME=sms_send
DB_USER=sms_user
DB_PASSWORD=your_password

RECEIVER=+7XXXXXXXXXX
```

### Таблица в БД

```sql
CREATE TABLE jobs_alert (
    id         SERIAL PRIMARY KEY,
    message    TEXT NOT NULL,
    status     VARCHAR(20) DEFAULT 'new',
    created_at TIMESTAMP DEFAULT now()
);
```

Статусы: `new`, `in_process`, `sent`, `error`.

## Запуск

Запустите воркер и планировщик в отдельных терминалах (или через systemd/supervisor):

```bash
# Celery воркер
celery -A celery_app worker --loglevel=info

# Celery Beat (планировщик)
celery -A celery_app beat --loglevel=info
```

Или одной командой:

```bash
celery -A celery_app worker --beat --loglevel=info
```

## Основные зависимости

| Пакет         | Версия | Назначение                        |
|---------------|--------|-----------------------------------|
| celery        | 5.6.0  | Очередь задач и планировщик       |
| redis         | 7.1.0  | Брокер сообщений для Celery       |
| psycopg2      | 2.9.11 | Драйвер PostgreSQL                |
| python-dotenv | 1.2.1  | Загрузка переменных из `.env`     |

## Параметры задачи

| Параметр       | Значение       | Описание                                      |
|----------------|----------------|-----------------------------------------------|
| batch_size     | 5              | Алертов за один запуск                        |
| sleep_seconds  | 1              | Задержка между отправками SMS (секунды)       |
| modem_id       | `"1"`          | ID модема в ModemManager (задан в `db.py`)    |
| Расписание     | каждую минуту  | `crontab(minute="*/1")`                       |
| Часовой пояс   | Asia/Tashkent  | Задан в `celery_app.py`                       |

> **Примечание:** `modem_id` захардкожен как `"1"` в `db.py`. Если ваш модем имеет другой ID (проверить: `mmcli -L`), измените значение в `db.py:142`.
