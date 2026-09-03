# 🤖 Бот для расчета мебели

Telegram-бот для расчета стоимости проектирования кухонь и шкафов.

## 📌 Возможности

- 🍳 **Кухня** — выбор верхних/нижних ящиков и пеналов с картинками
- 🚪 **Шкаф** — выбор каркаса (стандартный/компактный/увеличенный)
- 📊 **Общая смета** — суммирует расчеты по кухне и шкафу
- 📞 **Оставить контакт** — уведомление менеджеру с полной сметой
- ✉️ **Написать в Telegram** — быстрая связь с менеджером
- ➕ **Добавить детали** — можно добавить несколько кухонь и шкафов

## 🛠️ Технологии

- Python 3.12
- aiogram 3.x
- SQLAlchemy 2.0
- SQLite / PostgreSQL
- Docker / docker-compose

## 🚀 Быстрый старт

### Локально
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main

Bot_proschet/
├── app/
│   ├── handlers/          # Обработчики команд
│   ├── keyboards/         # Клавиатуры
│   ├── services/          # Бизнес-логика
│   ├── images/            # Картинки для бота
│   ├── models.py          # Модели БД
│   ├── schemas.py         # Pydantic схемы
│   ├── states.py          # FSM состояния
│   ├── database.py        # Подключение к БД
│   ├── config.py          # Настройки
│   └── main.py            # Точка входа
├── migrations/            # Миграции БД
├── .env                   # Переменные окружения
├── requirements.txt       # Зависимости
└── docker-compose.yml     # Docker