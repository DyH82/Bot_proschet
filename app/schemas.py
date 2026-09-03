from pydantic import BaseModel
from typing import List, Dict, Optional
from enum import Enum

# --- Типы мебели (корневые) ---
class FurnitureType(str, Enum):
    KITCHEN = "kitchen"
    WARDROBE = "wardrobe"

# --- Типы для кухни (категории) ---
class KitchenCategory(str, Enum):
    UPPER = "upper"
    LOWER = "lower"
    PANTRY = "pantry"

# --- Типы каркасов для шкафа ---
class WardrobeFrame(str, Enum):
    STANDARD = "standard"
    COMPACT = "compact"
    EXTENDED = "extended"

# --- Дополнительные услуги (ТОЛЬКО ТАК) ---
class AdditionalService(str, Enum):
    LIGHTING = "lighting"   # Подсветка (общая)
    EXTRA_1 = "extra_1"     # Доп 1
    EXTRA_2 = "extra_2"     # Доп 2
    EXTRA_3 = "extra_3"     # Доп 3
    EXTRA_4 = "extra_4"     # Доп 4
    EXTRA_5 = "extra_5"     # Доп 5

# --- Схема для вывода результата ---
class CalculationResult(BaseModel):
    total_price: float
    breakdown: Dict[str, float]
    details: str
    base_price: float