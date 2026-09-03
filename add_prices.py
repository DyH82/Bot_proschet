# add_prices.py
import asyncio
import os
from sqlalchemy import text
from app.database import engine, AsyncSessionLocal
from app.models import Price
from app.config import settings  # ← ДОБАВЛЯЕМ, чтобы прогрузить конфиг


async def add_prices():
    async with AsyncSessionLocal() as session:
        # Очищаем таблицу
        await session.execute(text("DELETE FROM prices"))

        prices_data = [
            # Кухня - Верхние (6 шт)
            {"category": "kitchen", "key": "upper_upper_1", "value": 40},
            {"category": "kitchen", "key": "upper_upper_2", "value": 45},
            {"category": "kitchen", "key": "upper_upper_3", "value": 50},
            {"category": "kitchen", "key": "upper_upper_4", "value": 55},
            {"category": "kitchen", "key": "upper_upper_5", "value": 60},
            {"category": "kitchen", "key": "upper_upper_6", "value": 65},

            # Кухня - Нижние (8 шт)
            {"category": "kitchen", "key": "lower_lower_1", "value": 40},
            {"category": "kitchen", "key": "lower_lower_2", "value": 50},
            {"category": "kitchen", "key": "lower_lower_3", "value": 55},
            {"category": "kitchen", "key": "lower_lower_4", "value": 60},
            {"category": "kitchen", "key": "lower_lower_5", "value": 65},
            {"category": "kitchen", "key": "lower_lower_6", "value": 70},
            {"category": "kitchen", "key": "lower_lower_7", "value": 80},
            {"category": "kitchen", "key": "lower_lower_8", "value": 85},

            # Кухня - Пеналы (3 шт)
            {"category": "kitchen", "key": "pantry_pantry_1", "value": 85},
            {"category": "kitchen", "key": "pantry_pantry_2", "value": 87},
            {"category": "kitchen", "key": "pantry_pantry_3", "value": 95},

            # Шкаф - каркасы
            {"category": "wardrobe", "key": "frame_standard", "value": 40},
            {"category": "wardrobe", "key": "frame_compact", "value": 60},
            {"category": "wardrobe", "key": "frame_extended", "value": 80},
            {"category": "wardrobe", "key": "shelf", "value": 7},
            {"category": "wardrobe", "key": "drawer", "value": 12},

            # Дополнительные услуги
            {"category": "additional", "key": "lighting", "value": 5},
            {"category": "additional", "key": "extra_1", "value": 10},
            {"category": "additional", "key": "extra_2", "value": 20},
            {"category": "additional", "key": "extra_3", "value": 30},
            {"category": "additional", "key": "extra_4", "value": 40},
            {"category": "additional", "key": "extra_5", "value": 50},
            {"category": "additional", "key": "gola_price", "value": 5},
        ]

        for p in prices_data:
            session.add(Price(**p))

        await session.commit()
        print(f"✅ Добавлено {len(prices_data)} записей с ценами")

        # Показываем, что добавили
        result = await session.execute(text("SELECT category, key, value FROM prices ORDER BY category, key"))
        rows = result.fetchall()
        print("\n📋 Текущие цены:")
        for row in rows:
            print(f"  {row[0]}/{row[1]}: {row[2]} руб")


async def main():
    # Проверяем, что конфиг загружен
    print(f"🔍 Подключение к БД: {settings.db_url}")

    async with engine.begin() as conn:
        from app.database import Base
        await conn.run_sync(Base.metadata.create_all)

    await add_prices()


if __name__ == "__main__":
    asyncio.run(main())