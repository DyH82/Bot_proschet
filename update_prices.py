import asyncio
from app.database import AsyncSessionLocal
from app.models import Price
from sqlalchemy import update

async def update_price(category: str, key: str, new_value: float):
    async with AsyncSessionLocal() as session:
        stmt = update(Price).where(
            Price.category == category,
            Price.key == key
        ).values(value=new_value)
        await session.execute(stmt)
        await session.commit()
        print(f"✅ Цена обновлена: {category}/{key} = {new_value}")

async def main():
    # Примеры обновления цен для кухни
    await update_price("kitchen", "upper_upper_1", 15000)  # Верхний складной
    await update_price("kitchen", "upper_upper_4", 12000)  # Верхний угловой
    await update_price("kitchen", "lower_lower_6", 18000)  # Нижний угловой
    await update_price("kitchen", "lower_lower_2", 20000)  # Нижний выдвижной 2 ящ
    await update_price("kitchen", "pantry_pantry_3", 8700)  # Пенал Духовка/микров-ка

if __name__ == "__main__":
    asyncio.run(main())