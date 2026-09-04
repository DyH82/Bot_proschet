#!/usr/bin/env python3
import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.config import settings
from app.handlers import start, kitchen, wardrobe
from app.handlers.common import UPPER_TYPES, LOWER_TYPES, PANTRY_TYPES
from app.database import engine, Base, AsyncSessionLocal
from app.states import CalcState
from app.keyboards import main_menu_kb, kitchen_category_kb, after_message_sent_kb, after_calculation_kb, extras_kb
from app.services.price_service import PriceService
from app.services.calculator import FurnitureCalculator
from app.schemas import WardrobeFrame, KitchenCategory, AdditionalService
from app.handlers.kitchen import render_kitchen_selection, show_total_calculation
from app.handlers.wardrobe import show_shelf_selection, show_drawer_selection, wardrobe_start

ADMIN_ID = 1101615132  # ← ТВОЙ ID

# ==================== НАЗВАНИЯ ДОПОВ ====================
extras_names = {
    "lighting": "💡 Подсветка",
    "gola": "🔘 Гола",
    "extra_1": "🔧 Доп 1",
    "extra_2": "🔧 Доп 2",
    "extra_3": "🔧 Доп 3",
    "extra_4": "🔧 Доп 4",
    "extra_5": "🔧 Доп 5"
}


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def format_calculation_with_prices(data: dict) -> str:
    """Форматирует расчет пользователя с полной сметой для отправки менеджеру."""

    kitchen_items = data.get("kitchen_items", [])
    wardrobe_items = data.get("wardrobe_items", [])

    async with AsyncSessionLocal() as session:
        price_service = PriceService(session)
        prices = await price_service.get_all_prices()

    total_price = 0
    all_text = ""
    extras_names_local = {
        "lighting": "💡 Подсветка",
        "gola": "🔘 Гола",
        "extra_1": "🔧 Доп 1",
        "extra_2": "🔧 Доп 2",
        "extra_3": "🔧 Доп 3",
        "extra_4": "🔧 Доп 4",
        "extra_5": "🔧 Доп 5"
    }

    # ========== ШКАФЫ ==========
    if wardrobe_items:
        all_text += "🚪 **ШКАФЫ**\n\n"
        for idx, item in enumerate(wardrobe_items, 1):
            frame_type = item.get("frame_type")
            shelves = item.get("shelves", 0)
            drawers = item.get("drawers", 0)
            extras = item.get("extras", [])

            frame_names = {
                "standard": "150-800мм",
                "compact": "801-1500мм",
                "extended": "1501-2500мм"
            }

            wardrobe_prices = prices.get("wardrobe", {})
            additional_prices = prices.get("additional", {})

            frame_price = wardrobe_prices.get(f"frame_{frame_type}", 0)
            shelf_price = wardrobe_prices.get("shelf", 0)
            drawer_price = wardrobe_prices.get("drawer", 0)

            shelves_cost = shelves * shelf_price
            drawers_cost = drawers * drawer_price

            item_total = frame_price + shelves_cost + drawers_cost

            extras_cost = 0
            if extras:
                for extra in extras:
                    price = additional_prices.get(extra, 0)
                    extras_cost += price

            item_total += extras_cost
            total_price += item_total

            all_text += f"📦 **Шкаф №{idx}**\n"
            all_text += f"  • Каркас: {frame_names.get(frame_type, frame_type)}: {frame_price:,.0f} руб\n"
            all_text += f"  • Полки: {shelves} шт x {shelf_price:,.0f} руб = {shelves_cost:,.0f} руб\n"
            all_text += f"  • Ящики: {drawers} шт x {drawer_price:,.0f} руб = {drawers_cost:,.0f} руб\n"
            if extras:
                all_text += f"  • Допы: {', '.join([extras_names_local.get(e, e) for e in extras])}\n"
            all_text += f"  • **Стоимость: {item_total:,.0f} руб**\n\n"

    # ========== КУХНИ ==========
    if kitchen_items:
        all_text += "🍳 **КУХНИ**\n\n"
        for idx, item in enumerate(kitchen_items, 1):
            category = item.get("category")
            items = item.get("items", [])
            extras = item.get("extras", {})
            gola = item.get("gola", False)

            # ✅ ОБРАТНАЯ СОВМЕСТИМОСТЬ: если extras — список, конвертируем в словарь
            if isinstance(extras, list):
                extras_dict = {}
                for extra in extras:
                    if extra == "gola":
                        extras_dict["gola"] = 1
                    elif extra in ["lighting", "extra_1", "extra_2", "extra_3", "extra_4", "extra_5"]:
                        extras_dict[extra] = 1
                extras = extras_dict

            kitchen_total = 0
            kitchen_prices = prices.get("kitchen", {})

            all_text += f"🍳 **Кухня №{idx}**\n"
            all_text += "  • Модули:\n"

            for sub_item in items:
                item_id = sub_item["id"]
                count = sub_item["count"]
                sub_category = sub_item.get("category", category)

                price_key = f"{sub_category}_{item_id}"
                price_per_unit = kitchen_prices.get(price_key, 0)

                if price_per_unit == 0:
                    price_per_unit = kitchen_prices.get(item_id, 0)

                item_total = price_per_unit * count
                kitchen_total += item_total
                all_text += f"      - {sub_item['name']} — {count} шт: {item_total:,.0f} руб\n"

            extras_cost = 0
            if extras:
                all_text += "  • Допы:\n"
                for extra, count in extras.items():
                    price_key = extra
                    if extra == "gola":
                        price_key = "gola_price"
                    price = prices.get("additional", {}).get(price_key, 0)
                    item_total = price * count
                    extras_cost += item_total
                    extra_name = extras_names_local.get(extra, extra)
                    unit = "м" if extra in ["lighting", "gola"] else "шт"
                    all_text += f"      - {extra_name}: {count} {unit} x {price:,.0f} руб = {item_total:,.0f} руб\n"

            kitchen_total += extras_cost
            total_price += kitchen_total
            all_text += f"  • **Стоимость: {kitchen_total:,.0f} руб**\n\n"

    if not all_text:
        return "❌ Нет выбранных позиций"

    all_text += f"💰 **ОБЩАЯ СМЕТА: {total_price:,.0f} руб**"

    return all_text


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    await create_tables()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(kitchen.router)
    dp.include_router(wardrobe.router)

    # ========== ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ДЛЯ КНОПКИ "ОСТАВИТЬ КОНТАКТ" ==========
    @dp.callback_query(F.data == "leave_contact")
    async def global_leave_contact(callback: CallbackQuery, state: FSMContext):
        print("🔔 Обработчик leave_contact сработал!")

        reply_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📱 Отправить контакт", request_contact=True)]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await callback.message.answer(
            "📞 **Чтобы мы могли с вами связаться:**\n\n"
            "Нажмите кнопку **«Отправить контакт»** ниже.\n"
            "Или просто напишите свой номер телефона вручную.",
            reply_markup=reply_keyboard
        )
        await state.set_state(CalcState.CONTACT_WAITING)
        await callback.answer()

    @dp.message(StateFilter(CalcState.CONTACT_WAITING), F.contact)
    async def global_receive_contact(message: Message, state: FSMContext):
        print("📩 Получен контакт (кнопка)!")

        user_id = message.from_user.id
        username = message.from_user.username or "нет username"
        first_name = message.from_user.first_name or "нет имени"

        contact = message.contact
        phone_number = contact.phone_number
        contact_first_name = contact.first_name or "нет имени"
        contact_last_name = contact.last_name or ""

        data = await state.get_data()
        calculation_text = await format_calculation_with_prices(data)

        admin_message = (
            f"📩 **НОВЫЙ КОНТАКТ!**\n\n"
            f"👤 **Пользователь:** {first_name} (@{username})\n"
            f"🆔 **ID:** `{user_id}`\n\n"
            f"📱 **Телефон:** {phone_number}\n"
            f"👤 **Имя:** {contact_first_name} {contact_last_name}\n\n"
            f"📅 **Время:** {message.date}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 **ДЕТАЛИ РАСЧЕТА:**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{calculation_text}"
        )

        try:
            await message.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode=None
            )
            await message.answer(
                "✅ Спасибо! Ваш контакт отправлен.\n\n"
                "Наш менеджер свяжется с вами в ближайшее время.",
                reply_markup=main_menu_kb()
            )
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await message.answer(
                f"⚠️ Ошибка: {e}",
                reply_markup=main_menu_kb()
            )

        await state.clear()

    @dp.message(StateFilter(CalcState.CONTACT_WAITING), F.text)
    async def global_handle_phone_text(message: Message, state: FSMContext):
        print("📩 Получен текст (ручной ввод):", message.text)

        phone = re.sub(r'[\s\-\(\)]', '', message.text)

        if not re.match(r'^[\+\d]{7,15}$', phone):
            await message.answer(
                "❌ Пожалуйста, введите корректный номер телефона.\n"
                "Например: +375 29 1234567"
            )
            return

        user_id = message.from_user.id
        username = message.from_user.username or "нет username"
        first_name = message.from_user.first_name or "нет имени"

        data = await state.get_data()
        calculation_text = await format_calculation_with_prices(data)

        admin_message = (
            f"📩 **НОВЫЙ КОНТАКТ (ручной ввод)!**\n\n"
            f"👤 **Пользователь:** {first_name} (@{username})\n"
            f"🆔 **ID:** `{user_id}`\n\n"
            f"📱 **Телефон:** {message.text}\n\n"
            f"📅 **Время:** {message.date}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 **ДЕТАЛИ РАСЧЕТА:**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{calculation_text}"
        )

        try:
            await message.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode=None
            )
            await message.answer(
                "✅ Спасибо! Ваш контакт отправлен.\n\n"
                "Наш менеджер свяжется с вами в ближайшее время.",
                reply_markup=main_menu_kb()
            )
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            await message.answer(
                f"⚠️ Ошибка: {e}",
                reply_markup=main_menu_kb()
            )

        await state.clear()

    @dp.callback_query(F.data == "write_to_admin")
    async def write_to_admin(callback: CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        username = callback.from_user.username or "нет username"
        first_name = callback.from_user.first_name or "нет имени"

        data = await state.get_data()
        calculation_text = await format_calculation_with_prices(data)

        admin_message = (
            f"✉️ **ПОЛЬЗОВАТЕЛЬ ХОЧЕТ СВЯЗАТЬСЯ!**\n\n"
            f"👤 **Имя:** {first_name}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📱 **Username:** @{username}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 **ДЕТАЛИ РАСЧЕТА:**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{calculation_text}\n\n"
            f"👉 Напиши ему первым в Telegram, используя этот ID."
        )

        try:
            await callback.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode=None
            )
            await callback.message.answer(
                "✅ Сообщение отправлено!\n\n"
                "Наш менеджер свяжется с вами в ближайшее время.",
                reply_markup=after_message_sent_kb()
            )
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления: {e}")
            await callback.message.answer(
                f"⚠️ Ошибка: {e}",
                reply_markup=main_menu_kb()
            )

        await callback.answer()

    # ===================================================================
    # ========== ОБРАБОТЧИКИ ДЛЯ КНОПКИ "ДОБАВИТЬ" ==========
    # ===================================================================

    # ========== КНОПКА "ДОБАВИТЬ" ==========

    @dp.callback_query(F.data == "add_details")
    async def add_details(callback: CallbackQuery, state: FSMContext):
        """Предлагает пользователю выбрать, что добавить."""

        data = await state.get_data()
        kitchen_items = data.get("kitchen_items", [])
        wardrobe_items = data.get("wardrobe_items", [])

        await callback.message.delete()

        buttons = []

        # ===== КУХНЯ =====
        buttons.append([InlineKeyboardButton(
            text="🍳 Новая кухня",
            callback_data="add_new_kitchen"
        )])

        if kitchen_items:
            for idx in range(len(kitchen_items)):
                buttons.append([InlineKeyboardButton(
                    text=f"📦 Добавить модули к кухне №{idx + 1}",
                    callback_data=f"add_to_kitchen_{idx}"
                )])
                # ✅ ДОБАВЛЯЕМ КНОПКУ "ДОБАВИТЬ ДОПЫ" ДЛЯ КАЖДОЙ КУХНИ
                buttons.append([InlineKeyboardButton(
                    text=f"🔧 Добавить допы к кухне №{idx + 1}",
                    callback_data=f"add_extras_to_kitchen_{idx}"
                )])

        # ===== ШКАФ =====
        buttons.append([InlineKeyboardButton(
            text="🚪 Новый шкаф",
            callback_data="add_new_wardrobe"
        )])

        if wardrobe_items:
            for idx in range(len(wardrobe_items)):
                buttons.append([InlineKeyboardButton(
                    text=f"📦 Добавить детали к шкафу №{idx + 1}",
                    callback_data=f"add_to_wardrobe_{idx}"
                )])
                # ✅ ДОБАВЛЯЕМ КНОПКУ "ДОБАВИТЬ ДОПЫ" ДЛЯ КАЖДОГО ШКАФА
                buttons.append([InlineKeyboardButton(
                    text=f"🔧 Добавить допы к шкафу №{idx + 1}",
                    callback_data=f"add_extras_to_wardrobe_{idx}"
                )])

        # ===== ДОБАВИТЬ К ТЕКУЩЕМУ =====
        if data.get("current_frame_type"):
            buttons.append([InlineKeyboardButton(
                text="📦 Добавить к текущему шкафу",
                callback_data="add_to_current_wardrobe"
            )])

        if data.get("current_kitchen_items"):
            buttons.append([InlineKeyboardButton(
                text="📦 Добавить к текущей кухне",
                callback_data="add_to_current_kitchen"
            )])

        buttons.append([InlineKeyboardButton(
            text="🔙 Назад к результату",
            callback_data="back_to_result"
        )])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        text = (
            "➕ **Что вы хотите добавить?**\n\n"
            f"📊 Текущие расчеты:\n"
            f"  • Кухонь сохранено: {len(kitchen_items)}\n"
            f"  • Шкафов сохранено: {len(wardrobe_items)}\n\n"
            "Выберите действие:"
        )

        await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()

    # ========== НОВАЯ КУХНЯ ==========

    @dp.callback_query(F.data == "add_new_kitchen")
    async def add_new_kitchen(callback: CallbackQuery, state: FSMContext):
        """Начинаем новую кухню."""
        await callback.message.delete()

        await state.update_data(
            kitchen_category=None,
            current_kitchen_items=[],
            current_kitchen_extras=[],
            current_extras_counts={},
            selected_kitchen_items={}
        )

        await state.set_state(CalcState.KITCHEN_CATEGORY)

        await callback.message.answer(
            "🍳 **Новая кухня**\n\nВыберите категорию:",
            reply_markup=kitchen_category_kb()
        )
        await callback.answer()

    # ========== НОВЫЙ ШКАФ ==========

    @dp.callback_query(F.data == "add_new_wardrobe")
    async def add_new_wardrobe(callback: CallbackQuery, state: FSMContext):
        """Начинаем новый шкаф."""
        await callback.message.delete()

        await state.update_data(
            current_frame_type=None,
            current_shelves=0,
            current_drawers=0,
            current_wardrobe_extras=[],
            selected_shelves={},
            selected_drawers={}
        )

        from app.handlers.wardrobe import wardrobe_start
        await wardrobe_start(callback, state)

    # ========== ДОБАВИТЬ К СОХРАНЁННОЙ КУХНЕ ==========

    @dp.callback_query(F.data.startswith("add_to_kitchen_"))
    async def add_to_saved_kitchen(callback: CallbackQuery, state: FSMContext):
        """Добавляем ящики к сохранённой кухне."""
        idx = int(callback.data.replace("add_to_kitchen_", ""))

        data = await state.get_data()
        kitchen_items = data.get("kitchen_items", [])

        if idx >= len(kitchen_items):
            await callback.answer("❌ Кухня не найдена!")
            return

        selected_kitchen = kitchen_items[idx]
        await state.update_data(
            editing_kitchen_index=idx,
            kitchen_category=selected_kitchen.get("category"),
            current_kitchen_items=selected_kitchen.get("items", []),
            current_kitchen_extras=selected_kitchen.get("extras", {}),
            selected_kitchen_items={}
        )

        await callback.message.delete()
        await state.set_state(CalcState.KITCHEN_CATEGORY)

        await callback.message.answer(
            "🍳 **Добавьте ящики к кухне**\n\n"
            "Выберите категорию:",
            reply_markup=kitchen_category_kb()
        )
        await callback.answer()

    # ========== ДОБАВИТЬ К СОХРАНЁННОМУ ШКАФУ ==========

    @dp.callback_query(F.data.startswith("add_to_wardrobe_"))
    async def add_to_saved_wardrobe(callback: CallbackQuery, state: FSMContext):
        """Добавляем детали к сохранённому шкафу."""
        idx = int(callback.data.replace("add_to_wardrobe_", ""))

        data = await state.get_data()
        wardrobe_items = data.get("wardrobe_items", [])

        if idx >= len(wardrobe_items):
            await callback.answer("❌ Шкаф не найден!")
            return

        selected_wardrobe = wardrobe_items[idx]
        await state.update_data(
            editing_wardrobe_index=idx,
            current_frame_type=selected_wardrobe.get("frame_type"),
            current_shelves=selected_wardrobe.get("shelves", 0),
            current_drawers=selected_wardrobe.get("drawers", 0),
            current_wardrobe_extras=selected_wardrobe.get("extras", [])
        )

        await callback.message.delete()
        await state.set_state(CalcState.WARDROBE_SHELVES)

        from app.handlers.wardrobe import show_shelf_selection
        await show_shelf_selection(callback, state)

    # ========== ДОБАВИТЬ К ТЕКУЩЕЙ КУХНЕ ==========

    @dp.callback_query(F.data == "add_to_current_kitchen")
    async def add_to_current_kitchen(callback: CallbackQuery, state: FSMContext):
        """Добавляем ящики к текущей кухне — показываем выбор категории."""

        await callback.message.delete()
        await state.update_data(
            kitchen_category=None,
            selected_kitchen_items={}
        )
        await state.set_state(CalcState.KITCHEN_CATEGORY)

        await callback.message.answer(
            "🍳 **Добавьте ящики к текущей кухне**\n\n"
            "Выберите категорию:",
            reply_markup=kitchen_category_kb()
        )
        await callback.answer()

    # ========== ДОБАВИТЬ К ТЕКУЩЕМУ ШКАФУ ==========

    @dp.callback_query(F.data == "add_to_current_wardrobe")
    async def add_to_current_wardrobe(callback: CallbackQuery, state: FSMContext):
        """Добавляем детали к текущему шкафу — показываем выбор: полки или ящики."""

        data = await state.get_data()
        frame_type = data.get("current_frame_type")

        if not frame_type:
            await callback.message.delete()
            from app.handlers.wardrobe import wardrobe_start
            await wardrobe_start(callback, state)
            await callback.answer()
            return

        await callback.message.delete()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📚 Добавить полки", callback_data="add_shelves_to_current")],
                [InlineKeyboardButton(text="📦 Добавить ящики", callback_data="add_drawers_to_current")],
                [InlineKeyboardButton(text="🔙 Назад к результату", callback_data="back_to_result")]
            ]
        )

        frame_names = {
            "standard": "150-800мм",
            "compact": "801-1500мм",
            "extended": "1501-2500мм"
        }
        frame_name = frame_names.get(frame_type, frame_type)

        current_shelves = data.get("current_shelves", 0)
        current_drawers = data.get("current_drawers", 0)

        text = (
            f"✅ **Текущий шкаф:** {frame_name}\n"
            f"📚 Полок: {current_shelves} шт\n"
            f"📦 Ящиков: {current_drawers} шт\n\n"
            "Что вы хотите добавить?"
        )

        await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()

    # ========== ДОБАВИТЬ ПОЛКИ К ТЕКУЩЕМУ ШКАФУ ==========

    @dp.callback_query(F.data == "add_shelves_to_current")
    async def add_shelves_to_current(callback: CallbackQuery, state: FSMContext):
        """Добавляем полки к текущему шкафу."""
        await state.set_state(CalcState.WARDROBE_SHELVES)
        await callback.message.delete()

        from app.handlers.wardrobe import show_shelf_selection
        await show_shelf_selection(callback, state)

    # ========== ДОБАВИТЬ ЯЩИКИ К ТЕКУЩЕМУ ШКАФУ ==========

    @dp.callback_query(F.data == "add_drawers_to_current")
    async def add_drawers_to_current(callback: CallbackQuery, state: FSMContext):
        """Добавляем ящики к текущему шкафу."""
        await state.set_state(CalcState.WARDROBE_DRAWERS)
        await callback.message.delete()

        from app.handlers.wardrobe import show_drawer_selection
        await show_drawer_selection(callback, state)

    # ========== ДОБАВИТЬ ДОПЫ К СОХРАНЁННОЙ КУХНЕ ==========

    @dp.callback_query(F.data.startswith("add_extras_to_kitchen_"))
    async def add_extras_to_saved_kitchen(callback: CallbackQuery, state: FSMContext):
        """Добавляем допы к сохранённой кухне."""
        idx = int(callback.data.replace("add_extras_to_kitchen_", ""))

        data = await state.get_data()
        kitchen_items = data.get("kitchen_items", [])

        if idx >= len(kitchen_items):
            await callback.answer("❌ Кухня не найдена!")
            return

        selected_kitchen = kitchen_items[idx]

        # Загружаем кухню для добавления допов
        await state.update_data(
            editing_kitchen_index=idx,
            current_kitchen_items=selected_kitchen.get("items", []),
            current_extras_counts=selected_kitchen.get("extras", {}),
            current_kitchen_extras=list(selected_kitchen.get("extras", {}).keys()),
            kitchen_category=selected_kitchen.get("category")
        )

        await callback.message.delete()
        await state.set_state(CalcState.KITCHEN_EXTRAS)

        # Показываем меню допов
        text = "🔧 **Добавьте дополнительные услуги к кухне**\n\n"
        text += "Выберите нужные опции:"

        await callback.message.answer(text, reply_markup=extras_kb())
        await callback.answer()

    # ========== ДОБАВИТЬ ДОПЫ К СОХРАНЁННОМУ ШКАФУ ==========

    @dp.callback_query(F.data.startswith("add_extras_to_wardrobe_"))
    async def add_extras_to_saved_wardrobe(callback: CallbackQuery, state: FSMContext):
        """Добавляем допы к сохранённому шкафу."""
        idx = int(callback.data.replace("add_extras_to_wardrobe_", ""))

        data = await state.get_data()
        wardrobe_items = data.get("wardrobe_items", [])

        if idx >= len(wardrobe_items):
            await callback.answer("❌ Шкаф не найден!")
            return

        selected_wardrobe = wardrobe_items[idx]

        # Загружаем шкаф для добавления допов
        await state.update_data(
            editing_wardrobe_index=idx,
            current_frame_type=selected_wardrobe.get("frame_type"),
            current_shelves=selected_wardrobe.get("shelves", 0),
            current_drawers=selected_wardrobe.get("drawers", 0),
            current_wardrobe_extras=selected_wardrobe.get("extras", [])
        )

        await callback.message.delete()
        await state.set_state(CalcState.WARDROBE_EXTRAS)

        # Показываем меню допов
        data = await state.get_data()

        async with AsyncSessionLocal() as session:
            price_service = PriceService(session)
            add_prices = await price_service.get_additional_prices()

            services_text = "\n".join([
                f"• {name}: {add_prices.get(key, 0):,.0f} руб"
                for key, name in [
                    ("lighting", "💡 Подсветка"),
                    ("gola", "🔘 Гола"),
                    ("extra_1", "🔧 Доп 1"),
                    ("extra_2", "🔧 Доп 2"),
                    ("extra_3", "🔧 Доп 3"),
                    ("extra_4", "🔧 Доп 4"),
                    ("extra_5", "🔧 Доп 5")
                ]
            ])

        frame_names = {
            "standard": "150-800мм",
            "compact": "801-1500мм",
            "extended": "1501-2500мм"
        }

        text = (
            f"✅ **Шкаф №{idx + 1}**\n"
            f"📐 Каркас: {frame_names.get(data.get('current_frame_type'), data.get('current_frame_type'))}\n"
            f"📚 Полки: {data.get('current_shelves')} шт\n"
            f"📦 Ящики: {data.get('current_drawers')} шт\n\n"
            "**Дополнительные услуги:**\n"
            f"{services_text}\n\n"
            "Нажмите на услугу, чтобы добавить/убрать.\n"
            "Когда закончите — нажмите «Рассчитать стоимость»."
        )

        await callback.message.answer(text, reply_markup=extras_kb())
        await callback.answer()

    # ========== НАЗАД К РЕЗУЛЬТАТУ ==========

    @dp.callback_query(F.data == "back_to_result")
    async def back_to_result(callback: CallbackQuery, state: FSMContext):
        """Возвращает к последнему результату расчета."""

        data = await state.get_data()

        kitchen_items = data.get("kitchen_items", [])
        wardrobe_items = data.get("wardrobe_items", [])

        if kitchen_items or wardrobe_items:
            from app.handlers.kitchen import show_total_calculation
            await show_total_calculation(callback, state)
        else:
            await state.clear()
            await callback.message.delete()
            await callback.message.answer(
                "🏠 **Главное меню**\n\nВыберите тип мебели:",
                reply_markup=main_menu_kb()
            )

        await callback.answer()

    # ========== НАЗАД К МЕНЮ "ДОБАВИТЬ" ==========

    @dp.callback_query(F.data == "back_to_add_menu")
    async def back_to_add_menu(callback: CallbackQuery, state: FSMContext):
        """Возврат к меню добавления."""

        data = await state.get_data()
        kitchen_items = data.get("kitchen_items", [])
        wardrobe_items = data.get("wardrobe_items", [])

        await callback.message.delete()

        buttons = []

        buttons.append([InlineKeyboardButton(
            text="🍳 Новая кухня",
            callback_data="add_new_kitchen"
        )])

        if kitchen_items:
            for idx in range(len(kitchen_items)):
                buttons.append([InlineKeyboardButton(
                    text=f"📦 Добавить к кухне №{idx + 1}",
                    callback_data=f"add_to_kitchen_{idx}"
                )])

        buttons.append([InlineKeyboardButton(
            text="🚪 Новый шкаф",
            callback_data="add_new_wardrobe"
        )])

        if wardrobe_items:
            for idx in range(len(wardrobe_items)):
                buttons.append([InlineKeyboardButton(
                    text=f"📦 Добавить к шкафу №{idx + 1}",
                    callback_data=f"add_to_wardrobe_{idx}"
                )])

        if data.get("current_frame_type"):
            buttons.append([InlineKeyboardButton(
                text="📦 Добавить к текущему шкафу",
                callback_data="add_to_current_wardrobe"
            )])

        buttons.append([InlineKeyboardButton(
            text="🔙 Назад к результату",
            callback_data="back_to_result"
        )])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        text = (
            "➕ **Что вы хотите добавить?**\n\n"
            f"📊 Текущие расчеты:\n"
            f"  • Кухонь сохранено: {len(kitchen_items)}\n"
            f"  • Шкафов сохранено: {len(wardrobe_items)}\n\n"
            "Выберите действие:"
        )

        await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()

    # ========== УНИВЕРСАЛЬНАЯ КНОПКА "ПРОДОЛЖИТЬ ВЫБОР" ==========

    @dp.callback_query(F.data == "continue_selection")
    async def continue_selection(callback: CallbackQuery, state: FSMContext):
        """Возвращает пользователя в главное меню выбора мебели без сброса данных."""

        await callback.message.delete()
        await state.set_state(CalcState.CHOOSING_TYPE)

        await callback.message.answer(
            "🏠 **Главное меню**\n\n"
            "Выберите тип мебели для продолжения.\n"
            "Все ранее выбранные позиции будут сохранены.",
            reply_markup=main_menu_kb()
        )

        await callback.answer()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())