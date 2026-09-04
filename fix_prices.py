# fix_prices.py
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.models import Price


async def fix_prices():
    async with AsyncSessionLocal() as session:
        # Удаляем старые цены для верхних ящиков (если есть)
        await session.execute(
            text("DELETE FROM prices WHERE category = 'kitchen' AND key LIKE 'upper_upper_%'")
        )

        # Добавляем новые цены для всех верхних ящиков
        prices = []
        for i in range(1, 7):
            key = f"upper_upper_{i}"
            value = 40 + (i - 1) * 5  # 40, 45, 50, 55, 60, 65
            prices.append(f"('kitchen', '{key}', {value})")
            print(f"✅ Добавлено: {key} = {value} руб")

        # Вставляем все цены одной командой
        await session.execute(
            text(f"""
                INSERT INTO prices (category, key, value) 
                VALUES {', '.join(prices)}
            """)
        )

        await session.commit()
        print("\n✅ Все цены добавлены!")


async def show_prices():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT key, value FROM prices WHERE category = 'kitchen' ORDER BY key")
        )
        rows = result.fetchall()
        print("\n📋 Текущие цены для кухни:")
        for row in rows:
            print(f"  {row[0]}: {row[1]} руб")


if __name__ == "__main__":
    asyncio.run(fix_prices())
    asyncio.run(show_prices())