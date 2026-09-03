from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.states import CalcState
from app.keyboards import kitchen_category_kb, item_list_kb_with_controls, extras_kb, after_calculation_kb, main_menu_kb
from app.handlers.common import UPPER_TYPES, LOWER_TYPES, PANTRY_TYPES
from app.schemas import KitchenCategory, AdditionalService
from app.services.price_service import PriceService
from app.services.calculator import FurnitureCalculator
from app.database import AsyncSessionLocal

router = Router()


@router.callback_query(StateFilter(CalcState.KITCHEN_CATEGORY), F.data.startswith("kitchen_"))
async def kitchen_category_chosen(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("kitchen_", "")
    await state.update_data(kitchen_category=category)
    await state.set_state(CalcState.KITCHEN_TYPE_SELECT)

    data = await state.get_data()
    if "current_kitchen_items" not in data:
        await state.update_data(current_kitchen_items=[])

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

    await callback.message.edit_text(text, reply_markup=item_list_kb_with_controls(items, "kitchen_item"))
    await callback.answer()


@router.callback_query(StateFilter(CalcState.KITCHEN_TYPE_SELECT), F.data.startswith("kitchen_item_"))
async def kitchen_item_chosen(callback: CallbackQuery, state: FSMContext):
    item_id = callback.data.replace("kitchen_item_", "")
    await state.update_data(current_item_id=item_id)
    await state.set_state(CalcState.KITCHEN_ITEM_COUNT)

    data = await state.get_data()
    category = data.get("kitchen_category")

    if category == "upper":
        items = UPPER_TYPES
    elif category == "lower":
        items = LOWER_TYPES
    else:
        items = PANTRY_TYPES

    selected_item = next((item for item in items if item["id"] == item_id), None)
    if not selected_item:
        await callback.answer("❌ Тип не найден!")
        return

    item_name = selected_item["text"]

    text = (
        f"✏️ **Введите количество для:**\n"
        f"📦 {item_name}\n\n"
        "Введите число (0 — чтобы пропустить этот тип)"
    )

    await callback.message.answer(text)
    await callback.answer()


@router.message(StateFilter(CalcState.KITCHEN_ITEM_COUNT))
async def kitchen_count_entered(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите целое число (0 или больше)")
        return

    data = await state.get_data()
    category = data.get("kitchen_category")
    item_id = data.get("current_item_id")
    kitchen_items = data.get("current_kitchen_items", [])

    if category == "upper":
        items = UPPER_TYPES
    elif category == "lower":
        items = LOWER_TYPES
    else:
        items = PANTRY_TYPES

    item_name = next((item["text"] for item in items if item["id"] == item_id), item_id)

    if count > 0:
        existing = next((i for i in kitchen_items if i["id"] == item_id), None)
        if existing:
            existing["count"] = count
            existing["category"] = category
        else:
            kitchen_items.append({
                "id": item_id,
                "name": item_name,
                "count": count,
                "category": category
            })
        await state.update_data(current_kitchen_items=kitchen_items)
        await message.answer(f"✅ Добавлено: {item_name} — {count} шт")
    else:
        kitchen_items = [i for i in kitchen_items if i["id"] != item_id]
        await state.update_data(current_kitchen_items=kitchen_items)
        await message.answer(f"❌ Убран: {item_name}")

    await state.set_state(CalcState.KITCHEN_TYPE_SELECT)

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

    selected = await state.get_data()
    selected_list = selected.get("current_kitchen_items", [])
    if selected_list:
        for item in selected_list:
            text += f"  • {item['name']} — {item['count']} шт\n"
    else:
        text += "  (пока ничего не выбрано)"

    text += "\n\n👇 **Выберите тип:**"

    await message.answer(text, reply_markup=item_list_kb_with_controls(items, "kitchen_item"))


@router.callback_query(StateFilter(CalcState.KITCHEN_TYPE_SELECT), F.data == "finish_selection")
async def finish_kitchen_selection(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    kitchen_items = data.get("current_kitchen_items", [])

    if not kitchen_items:
        await callback.answer("⚠️ Вы не выбрали ни одного ящика!", show_alert=True)
        return

    await state.set_state(CalcState.KITCHEN_EXTRAS)

    text = "✅ **Вы выбрали:**\n"
    for item in kitchen_items:
        text += f"  • {item['name']} — {item['count']} шт\n"

    text += "\n\n**Дополнительные услуги:**\n"
    text += "Выберите нужные опции:"

    await callback.message.edit_text(text, reply_markup=extras_kb())
    await callback.answer()


@router.callback_query(StateFilter(CalcState.KITCHEN_EXTRAS))
async def kitchen_extras_handlers(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    kitchen_extras = data.get("current_kitchen_extras", [])
    gola_state = data.get("current_kitchen_gola", False)

    if callback.data == "calculate_final":
        await save_kitchen_and_show_result(callback, state)
        return

    if callback.data == "back_to_prev":
        await state.set_state(CalcState.KITCHEN_CATEGORY)
        await callback.message.edit_text(
            "🍳 **Расчет кухни**\n\nВыберите категорию:",
            reply_markup=kitchen_category_kb()
        )
        await callback.answer()
        return

    if callback.data == "extras_gola_toggle":
        if "gola" in kitchen_extras:
            kitchen_extras.remove("gola")
            gola_state = False
        else:
            kitchen_extras.append("gola")
            gola_state = True
        await state.update_data(current_kitchen_extras=kitchen_extras, current_kitchen_gola=gola_state)
        await callback.answer(f"🔘 Гола: {'Да' if gola_state else 'Нет'}")
        await callback.message.edit_reply_markup(reply_markup=extras_kb(kitchen_extras))
        return

    if callback.data.startswith("extras_"):
        service = callback.data.replace("extras_", "")
        if service in kitchen_extras:
            kitchen_extras.remove(service)
        else:
            kitchen_extras.append(service)
        await state.update_data(current_kitchen_extras=kitchen_extras)
        await callback.message.edit_reply_markup(reply_markup=extras_kb(kitchen_extras))
        await callback.answer()


async def save_kitchen_and_show_result(callback: CallbackQuery, state: FSMContext):
    """Сохраняем текущую кухню в список и показываем общую смету."""

    data = await state.get_data()

    # Собираем данные текущей кухни
    kitchen_item = {
        "index": len(data.get("kitchen_items", [])) + 1,
        "category": data.get("kitchen_category"),
        "items": data.get("current_kitchen_items", []),
        "extras": data.get("current_kitchen_extras", []),
        "gola": data.get("current_kitchen_gola", False)
    }

    # Сохраняем в общий список
    kitchen_items = data.get("kitchen_items", [])
    kitchen_items.append(kitchen_item)
    await state.update_data(kitchen_items=kitchen_items)

    # Очищаем временные данные
    await state.update_data(current_kitchen_items=[])
    await state.update_data(current_kitchen_extras=[])
    await state.update_data(current_kitchen_gola=False)

    # Показываем общую смету
    await show_total_calculation(callback, state)


async def show_total_calculation(callback: CallbackQuery, state: FSMContext):
    """Показывает общую смету по всем сохранённым позициям."""

    data = await state.get_data()

    kitchen_items = data.get("kitchen_items", [])
    wardrobe_items = data.get("wardrobe_items", [])

    if not kitchen_items and not wardrobe_items:
        await callback.answer("❌ Нет сохранённых расчетов!")
        return

    async with AsyncSessionLocal() as session:
        price_service = PriceService(session)
        prices = await price_service.get_all_prices()

    total_price = 0
    all_details = ""
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
        all_details += "🚪 **ШКАФЫ**\n\n"
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

            all_details += f"📦 **Шкаф №{idx}**\n"
            all_details += f"  • Каркас: {frame_names.get(frame_type, frame_type)}\n"
            all_details += f"  • Полки: {shelves} шт\n"
            all_details += f"  • Ящики: {drawers} шт\n"
            if extras:
                all_details += f"  • Допы: {', '.join([extras_names.get(e, e) for e in extras])}\n"
            all_details += f"  • **Стоимость: {item_total:,.0f} руб**\n\n"

    # ========== КУХНИ ==========
    if kitchen_items:
        all_details += "🍳 **КУХНИ**\n\n"
        for idx, item in enumerate(kitchen_items, 1):
            category = item.get("category")
            items = item.get("items", [])
            extras = item.get("extras", [])
            gola = item.get("gola", False)

            kitchen_total = 0
            kitchen_prices = prices.get("kitchen", {})

            all_details += f"🍳 **Кухня №{idx}**\n"
            all_details += f"  • Категория: {category}\n"
            all_details += "  • Ящики:\n"

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
                all_details += f"      - {sub_item['name']} — {count} шт\n"

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
                all_details += f"  • Допы: {', '.join([extras_names.get(e, e) for e in extras if e != 'gola'])}\n"
            if gola:
                all_details += f"  • Гола: Да\n"

            all_details += f"  • **Стоимость: {kitchen_total:,.0f} руб**\n\n"

    if not all_details:
        await callback.answer("❌ Нет сохранённых расчетов!")
        return

    text = (
        "🧮 **ОБЩАЯ СМЕТА**\n\n"
        f"{all_details}"
        f"💰 **ОБЩИЙ ИТОГ: {total_price:,.0f} руб**\n\n"
        "📌 **Чтобы добавить еще один шкаф** — нажмите «Продолжить выбор» и выберите «Шкаф».\n"
        "📌 **Чтобы добавить кухню** — нажмите «Продолжить выбор» и выберите «Кухня»."
    )

    await callback.message.edit_text(text, reply_markup=after_calculation_kb())
    await callback.answer("✅ Расчет сохранен!")


# ==================== ВОЗВРАТ К ВЫБОРУ КАТЕГОРИИ КУХНИ ====================

@router.callback_query(F.data == "back_to_kitchen_categories")
async def back_to_kitchen_categories(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору категории кухни (Верхние/Нижние/Пеналы)."""

    await state.set_state(CalcState.KITCHEN_CATEGORY)
    await callback.message.delete()
    await callback.message.answer(
        "🍳 **Расчет кухни**\n\nВыберите категорию:",
        reply_markup=kitchen_category_kb()
    )
    await callback.answer()