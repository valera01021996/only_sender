# only_sender

Сервис автоматической отправки SMS-уведомлений по алертам из базы данных. Использует Celery для планирования задач и ModemManager (`mmcli`) для отправки SMS через сотовый модем.

## Назначение

Проект решает задачу автоматической рассылки SMS-уведомлений. Каждую минуту воркер проверяет таблицу `jobs_alert` в PostgreSQL, забирает новые алерты и отправляет их содержимое по SMS на заданный номер телефона через физический модем.

## Как это работает

```
Celery Beat (каждую 1 минуту)
       │
       ▼
scan_alerts_and_send_sms()
       │
       ▼
PostgreSQL: SELECT из jobs_alert WHERE status = 'new' (до 5 штук)
       │
       ▼
Пометка алертов как 'in_process'
       │
       ▼
Для каждого алерта:
  ├─ mmcli --messaging-create-sms  (создание SMS)
  ├─ mmcli -s <id> --send          (отправка SMS)
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
├── celery_app.py      # Конфигурация Celery, расписание задач
├── tasks.py           # Определение периодической задачи
├── db.py              # Работа с PostgreSQL (выборка, обновление статусов)
├── sms.py             # Отправка SMS через ModemManager (mmcli)
├── requirements.txt   # Python-зависимости
└── .env               # Переменные окружения (создать вручную)
```

## Требования к инфраструктуре

- **Python 3.8+**
- **Redis** — брокер сообщений для Celery
- **PostgreSQL** — база данных с таблицей `jobs_alert`
- **ModemManager** — установлен и настроен, сотовый модем подключён
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
DB_PASSWORD=123456

RECEIVER=+998909192558
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

- **batch_size**: 5 алертов за один запуск
- **sleep_seconds**: 1 секунда задержки между отправками SMS
- **modem_id**: `"1"` — идентификатор модема в ModemManager
- **Расписание**: каждую 1 минуту
- **Часовой пояс**: `Asia/Tashkent`
