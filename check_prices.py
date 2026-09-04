# check_prices.py
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

async def check_prices():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT key, value FROM prices WHERE category = 'kitchen' ORDER BY key")
        )
        rows = result.fetchall()
        print("\n📋 Цены для кухни:")
        for row in rows:
            print(f"  {row[0]}: {row[1]} руб")

if __name__ == "__main__":
    asyncio.run(check_prices())