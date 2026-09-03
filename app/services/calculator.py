from typing import List, Dict
from app.schemas import (
    FurnitureType, KitchenCategory, WardrobeFrame, AdditionalService, CalculationResult
)

class FurnitureCalculator:
    def __init__(self, prices: Dict[str, Dict[str, float]]):
        self.prices = prices
        self.kitchen_prices = prices.get("kitchen", {})
        self.wardrobe_prices = prices.get("wardrobe", {})
        self.additional_prices = prices.get("additional", {})

    # -------- КУХНЯ --------
    def calculate_kitchen(
        self,
        category: KitchenCategory,
        item_type: str,
        count: int,
        extras: List[AdditionalService],
        gola: bool
    ) -> CalculationResult:
        price_key = f"{category.value}_{item_type}"
        base_price_per_unit = self.kitchen_prices.get(price_key, 0)
        base_total = base_price_per_unit * count

        # Стоимость допов (подсветка + доп1-5)
        extras_cost = 0
        for service in extras:
            extras_cost += self.additional_prices.get(service.value, 0)

        # Гола (если Да)
        if gola:
            extras_cost += self.additional_prices.get("gola_price", 0)

        total = base_total + extras_cost

        breakdown = {
            f"Ящик ({category.value}) x{count} шт": base_total
        }
        if extras_cost > 0:
            breakdown["Доп. услуги"] = extras_cost
        if gola:
            breakdown["Гола (Да)"] = self.additional_prices.get("gola_price", 0)

        return CalculationResult(
            base_price=base_total,
            total_price=total,
            breakdown=breakdown,
            details=f"Кухня: {category.value}, Тип: {item_type}, Кол-во: {count}"
        )

    # -------- ШКАФ --------
    def calculate_wardrobe(
        self,
        frame_type: WardrobeFrame,
        shelves_count: int,
        drawers_count: int,
        extras: List[AdditionalService]
    ) -> CalculationResult:
        frame_cost = self.wardrobe_prices.get(f"frame_{frame_type.value}", 0)
        shelf_price = self.wardrobe_prices.get("shelf", 0)
        drawer_price = self.wardrobe_prices.get("drawer", 0)

        shelves_cost = shelves_count * shelf_price
        drawers_cost = drawers_count * drawer_price

        base = frame_cost + shelves_cost + drawers_cost
        extras_cost = sum(self.additional_prices.get(s.value, 0) for s in extras)
        total = base + extras_cost

        frame_names = {
            "standard": "Стандартный",
            "compact": "Компактный",
            "extended": "Увеличенный"
        }

        breakdown = {
            f"Каркас ({frame_names[frame_type.value]})": frame_cost,
            f"Полки ({shelves_count} шт)": shelves_cost,
            f"Ящики ({drawers_count} шт)": drawers_cost,
        }
        if extras_cost > 0:
            breakdown["Доп. услуги"] = extras_cost

        return CalculationResult(
            base_price=base,
            total_price=total,
            breakdown=breakdown,
            details=f"Шкаф: {frame_type.value}, Полок: {shelves_count}, Ящиков: {drawers_count}"
        )