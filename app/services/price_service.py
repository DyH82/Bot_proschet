from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Price
from typing import Dict, Optional


class PriceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_price(self, category: str, key: str) -> Optional[float]:
        query = select(Price).where(
            Price.category == category,
            Price.key == key
        )
        result = await self.session.execute(query)
        price = result.scalar_one_or_none()
        return price.value if price else None

    async def get_all_prices(self) -> Dict[str, Dict[str, float]]:
        query = select(Price)
        result = await self.session.execute(query)
        prices = result.scalars().all()

        data = {}
        for p in prices:
            if p.category not in data:
                data[p.category] = {}
            data[p.category][p.key] = p.value

        return data

    async def get_additional_prices(self) -> Dict[str, float]:
        query = select(Price).where(Price.category == "additional")
        result = await self.session.execute(query)
        prices = result.scalars().all()
        return {p.key: p.value for p in prices}
