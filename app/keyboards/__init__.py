from typing import List, Dict, Optional
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.types import InlineKeyboardButton
from app.schemas import KitchenCategory, WardrobeFrame

# --- Главное меню ---
def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🍳 Кухня", callback_data="furniture_kitchen")
    builder.button(text="🚪 Шкаф", callback_data="furniture_wardrobe")
    builder.adjust(1)
    return builder.as_markup()

# --- Выбор категории на кухне (верх/низ/пеналы) ---
def kitchen_category_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Верхние модули", callback_data="kitchen_upper")
    builder.button(text="📦 Нижние модули", callback_data="kitchen_lower")
    builder.button(text="🗄️ Пеналы", callback_data="kitchen_pantry")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# --- Выбор каркаса шкафа ---
def wardrobe_frame_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📐 Компактный", callback_data="frame_compact")
    builder.button(text="📐 Стандартный", callback_data="frame_standard")
    builder.button(text="📐 Увеличенный", callback_data="frame_extended")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# --- Дополнительные услуги ---
def extras_kb(selected: List[str] = None) -> InlineKeyboardMarkup:
    selected = selected or []
    services = {
        "lighting": "💡 Подсветка",
        "extra_1": "🔧 Доп 1",
        "extra_2": "🔧 Доп 2",
        "extra_3": "🔧 Доп 3",
        "extra_4": "🔧 Доп 4",
        "extra_5": "🔧 Доп 5"
    }
    builder = InlineKeyboardBuilder()
    for key, label in services.items():
        if key in selected:
            label = f"✅ {label}"
        builder.button(text=label, callback_data=f"extras_{key}")
    gola_selected = "gola" in selected
    gola_label = "✅ Гола (Да)" if gola_selected else "🔘 Гола (Нет)"
    builder.button(text=gola_label, callback_data="extras_gola_toggle")
    builder.button(text="✅ Рассчитать", callback_data="calculate_final")
    builder.button(text="🔙 Назад", callback_data="back_to_prev")
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура после расчета ---
def after_calculation_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить", callback_data="add_details")
    builder.button(text="📞 Оставить контакт", callback_data="leave_contact")
    builder.button(text="✉️ Написать в Telegram", callback_data="write_to_admin")
    builder.button(text="🔄 Новый расчет", callback_data="new_calculation")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура после отправки сообщения ---
def after_message_sent_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Новый расчет", callback_data="new_calculation")
    builder.adjust(1)
    return builder.as_markup()