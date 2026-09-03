#!/usr/bin/env python3
import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, \
    InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.config import settings
from app.handlers import start, kitchen, wardrobe
from app.handlers.common import UPPER_TYPES, LOWER_TYPES, PANTRY_TYPES
from app.database import engine, Base, AsyncSessionLocal
from app.states import CalcState
from app.keyboards import main_menu_kb, kitchen_category_kb, after_message_sent_kb, after_calculation_kb, \
    item_list_kb_with_controls
from app.services.price_service import PriceService
from app.services.calculator import FurnitureCalculator
from app.schemas import WardrobeFrame, KitchenCategory, AdditionalService

ADMIN_ID = 1101615132  # ← ТВОЙ ID


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
    extras_names = {
        "lighting": "💡 Подсветка",
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
                "standard": "Стандартный (600×2000)",
                "compact": "Компактный (500×1800)",
                "extended": "Ширина до 2500мм"
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
            all_text += f"  • Каркас: {frame_names.get(frame_type, frame_type)}\n"
            all_text += f"  • Полки: {shelves} шт\n"
            all_text += f"  • Ящики: {drawers} шт\n"
            if extras:
                all_text += f"  • Допы: {', '.join([extras_names.get(e, e) for e in extras])}\n"
            all_text += f"  • **Стоимость: {item_total:,.0f} руб**\n\n"

    # ========== КУХНИ ==========
    if kitchen_items:
        all_text += "🍳 **КУХНИ**\n\n"
        for idx, item in enumerate(kitchen_items, 1):
            category = item.get("category")
            items = item.get("items", [])
            extras = item.get("extras", [])
            gola = item.get("gola", False)

            kitchen_total = 0
            kitchen_prices = prices.get("kitchen", {})

            all_text += f"🍳 **Кухня №{idx}**\n"
            all_text += f"  • Категория: {category}\n"
            all_text += "  • Ящики:\n"

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
                all_text += f"      - {sub_item['name']} — {count} шт\n"

            # Допы для кухни
            extras_cost = 0
            if extras:
                for extra in extras:
                    if extra == "gola":
                        continue
                    price = prices.get("additional", {}).get(extra, 0)
                    extras_cost += price

            if gola:
                gola_price = prices.get("additional", {}).get("gola_price", 0)
                extras_cost += gola_price

            kitchen_total += extras_cost
            total_price += kitchen_total

            if extras:
                all_text += f"  • Допы: {', '.join([extras_names.get(e, e) for e in extras if e != 'gola'])}\n"
            if gola:
                all_text += f"  • Гола: Да\n"

            all_text += f"  • **Стоимость: {kitchen_total:,.0f} руб**\n\n"

    if not all_text:
        return "❌ Нет выбранных позиций"

    # ========== ОБЩИЙ ИТОГ ==========
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

    # ========== КНОПКА "ДОБАВИТЬ ДЕТАЛИ" ==========
    @dp.callback_query(F.data == "add_details")
    async def add_details(callback: CallbackQuery, state: FSMContext):
        """Предлагает пользователю выбрать, что добавить."""

        data = await state.get_data()
        kitchen_items = data.get("kitchen_items", [])
        wardrobe_items = data.get("wardrobe_items", [])

        await callback.message.delete()

        buttons = []

        # ===== КУХНЯ =====
        # Всегда можно начать новую кухню
        buttons.append([InlineKeyboardButton(
            text="🍳 Новая кухня",
            callback_data="add_new_kitchen"
        )])

        # Если есть сохранённые кухни — предложить добавить к ним
        if kitchen_items:
            for idx in range(len(kitchen_items)):
                buttons.append([InlineKeyboardButton(
                    text=f"📦 Добавить к кухне №{idx + 1}",
                    callback_data=f"add_to_kitchen_{idx}"
                )])

        # ===== ШКАФ =====
        # Всегда можно начать новый шкаф
        buttons.append([InlineKeyboardButton(
            text="🚪 Новый шкаф",
            callback_data="add_new_wardrobe"
        )])

        # Если есть сохранённые шкафы — предложить добавить к ним
        if wardrobe_items:
            for idx in range(len(wardrobe_items)):
                buttons.append([InlineKeyboardButton(
                    text=f"📦 Добавить к шкафу №{idx + 1}",
                    callback_data=f"add_to_wardrobe_{idx}"
                )])

        # Кнопка "Назад к результату"
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

        # Загружаем выбранную кухню в текущий расчет
        selected_kitchen = kitchen_items[idx]
        await state.update_data(
            kitchen_category=selected_kitchen.get("category"),
            current_kitchen_items=selected_kitchen.get("items", []),
            current_kitchen_extras=selected_kitchen.get("extras", []),
            current_kitchen_gola=selected_kitchen.get("gola", False)
        )

        # Удаляем эту кухню из сохранённых (она будет пересохранена)
        kitchen_items.pop(idx)
        await state.update_data(kitchen_items=kitchen_items)

        await callback.message.delete()
        await state.set_state(CalcState.KITCHEN_TYPE_SELECT)

        category = selected_kitchen.get("category")
        if category == "upper":
            items = UPPER_TYPES
            title = "Верхние ящики"
        elif category == "lower":
            items = LOWER_TYPES
            title = "Нижние ящики"
        else:
            items = PANTRY_TYPES
            title = "Пеналы"

        text = (
            f"📋 **{title}**\n\n"
            "Выберите тип ящика. После выбора введите количество.\n"
            "Можно выбрать несколько типов.\n\n"
            "✅ **Уже выбрано:**\n"
        )

        selected = data.get("current_kitchen_items", [])
        if selected:
            for item in selected:
                text += f"  • {item['name']} — {item['count']} шт\n"
        else:
            text += "  (пока ничего не выбрано)"

        text += "\n\n👇 **Выберите тип:**"

        await callback.message.answer(text, reply_markup=item_list_kb_with_controls(items, "kitchen_item"))
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

        # Загружаем выбранный шкаф в текущий расчет
        selected_wardrobe = wardrobe_items[idx]
        await state.update_data(
            current_frame_type=selected_wardrobe.get("frame_type"),
            current_shelves=selected_wardrobe.get("shelves", 0),
            current_drawers=selected_wardrobe.get("drawers", 0),
            current_wardrobe_extras=selected_wardrobe.get("extras", [])
        )

        # Удаляем этот шкаф из сохранённых (он будет пересохранён)
        wardrobe_items.pop(idx)
        await state.update_data(wardrobe_items=wardrobe_items)

        await callback.message.delete()
        await state.set_state(CalcState.WARDROBE_SHELVES)

        frame_names = {
            "standard": "Ширина до 800мм",
            "compact": "Ширина до 1500мм",
            "extended": "Ширина до 2500мм"
        }
        frame_name = frame_names.get(selected_wardrobe.get("frame_type"), "неизвестный")

        text = (
            f"✅ **Текущий шкаф:** {frame_name}\n"
            f"📚 Полок уже добавлено: {selected_wardrobe.get('shelves', 0)}\n"
            f"📦 Ящиков уже добавлено: {selected_wardrobe.get('drawers', 0)}\n\n"
            "📚 **Введите количество дополнительных полок**\n"
            "(введите число, 0 — чтобы пропустить)"
        )

        await callback.message.answer(text)
        await callback.answer()

    # ========== ОБРАБОТЧИКИ ДЛЯ ДОБАВЛЕНИЯ ДЕТАЛЕЙ В ШКАФ ==========

    @dp.callback_query(F.data == "add_shelves")
    async def add_shelves(callback: CallbackQuery, state: FSMContext):
        """Пользователь хочет добавить полки."""
        await state.set_state(CalcState.WARDROBE_SHELVES)
        await callback.message.delete()

        text = (
            "📚 **Добавьте еще полки**\n"
            "(введите число, 0 — чтобы пропустить)\n\n"
            "💡 Все ранее выбранные позиции будут сохранены."
        )

        await callback.message.answer(text)
        await callback.answer()

    @dp.callback_query(F.data == "add_drawers")
    async def add_drawers(callback: CallbackQuery, state: FSMContext):
        """Пользователь хочет добавить ящики."""
        await state.set_state(CalcState.WARDROBE_DRAWERS)
        await callback.message.delete()

        text = (
            "📦 **Добавьте еще выдвижные ящики**\n"
            "(введите число, 0 — чтобы пропустить)\n\n"
            "💡 Все ранее выбранные позиции будут сохранены."
        )

        await callback.message.answer(text)
        await callback.answer()

    @dp.callback_query(F.data == "back_to_result")
    async def back_to_result(callback: CallbackQuery, state: FSMContext):
        """Возвращает к последнему результату расчета."""

        data = await state.get_data()

        # Проверяем, есть ли сохраненные расчеты
        kitchen_items = data.get("kitchen_items", [])
        wardrobe_items = data.get("wardrobe_items", [])

        if kitchen_items or wardrobe_items:
            # Показываем общую смету
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

    # ========== ОБРАБОТЧИКИ ДЛЯ НОВЫХ КУХОНЬ И ШКАФОВ ==========

    @dp.callback_query(F.data == "add_new_kitchen")
    async def add_new_kitchen(callback: CallbackQuery, state: FSMContext):
        """Начинаем новую кухню."""
        await callback.message.delete()
        await state.set_state(CalcState.KITCHEN_CATEGORY)
        await state.update_data(current_kitchen_items=[])
        await state.update_data(current_kitchen_extras=[])
        await state.update_data(current_kitchen_gola=False)

        await callback.message.answer(
            "🍳 **Новая кухня**\n\nВыберите категорию:",
            reply_markup=kitchen_category_kb()
        )
        await callback.answer()

    @dp.callback_query(F.data == "add_new_wardrobe")
    async def add_new_wardrobe(callback: CallbackQuery, state: FSMContext):
        """Начинаем новый шкаф."""
        from app.handlers.wardrobe import wardrobe_start
        await callback.message.delete()
        await wardrobe_start(callback, state)

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