from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.states import CalcState
from app.keyboards import kitchen_category_kb, extras_kb, after_calculation_kb, main_menu_kb
from app.handlers.common import UPPER_TYPES, LOWER_TYPES, PANTRY_TYPES
from app.schemas import KitchenCategory, AdditionalService
from app.services.price_service import PriceService
from app.services.calculator import FurnitureCalculator
from app.database import AsyncSessionLocal

router = Router()

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


# ==================== ОТОБРАЖЕНИЕ ВЫБОРА ЯЩИКОВ ====================

async def render_kitchen_selection(callback: CallbackQuery, state: FSMContext):
    """Отрисовывает экран выбора ящиков с картинками и кнопками + и -"""

    data = await state.get_data()
    category = data.get("kitchen_category", "upper")

    if "selected_kitchen_items" not in data:
        await state.update_data(selected_kitchen_items={})

    if category == "upper":
        items = UPPER_TYPES
        title = "Верхние модули"
    elif category == "lower":
        items = LOWER_TYPES
        title = "Нижние модули"
    else:
        items = PANTRY_TYPES
        title = "Пеналы"

    selected = data.get("selected_kitchen_items", {})

    for item in items:
        item_id = item["id"]
        current_count = selected.get(item_id, 0)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➖",
                        callback_data=f"kitchen_decr_{item_id}"
                    ),
                    InlineKeyboardButton(
                        text=f"{current_count}",
                        callback_data=f"kitchen_count_{item_id}"
                    ),
                    InlineKeyboardButton(
                        text="➕",
                        callback_data=f"kitchen_incr_{item_id}"
                    )
                ]
            ]
        )

        try:
            photo = FSInputFile(item["image"])
            await callback.message.answer_photo(
                photo=photo,
                caption=f"📦 **{item['text']}**",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Ошибка загрузки картинки {item['image']}: {e}")
            await callback.message.answer(
                f"📦 **{item['text']}**\n(картинка не найдена)",
                reply_markup=keyboard
            )

    control_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Закончить выбор", callback_data="finish_selection")],
            [InlineKeyboardButton(text="📋 Другая категория", callback_data="back_to_kitchen_categories")]
        ]
    )

    await callback.message.answer(
        "👇 Когда выберете все нужные ящики, нажмите «Закончить выбор».",
        reply_markup=control_keyboard
    )


# ==================== ВЫБОР КАТЕГОРИИ ====================

@router.callback_query(StateFilter(CalcState.KITCHEN_CATEGORY), F.data.startswith("kitchen_"))
async def kitchen_category_chosen(callback: CallbackQuery, state: FSMContext):
    """Выбрана категория → показываем карточки ящиков с + и -"""

    category = callback.data.replace("kitchen_", "")
    await state.update_data(kitchen_category=category)
    await state.set_state(CalcState.KITCHEN_TYPE_SELECT)

    await render_kitchen_selection(callback, state)


# ==================== КНОПКИ + И - ====================

@router.callback_query(F.data.startswith("kitchen_incr_"))
async def kitchen_increment(callback: CallbackQuery, state: FSMContext):
    """Увеличиваем количество ящика на 1"""
    item_id = callback.data.replace("kitchen_incr_", "")
    data = await state.get_data()
    selected = data.get("selected_kitchen_items", {})
    selected[item_id] = selected.get(item_id, 0) + 1
    await state.update_data(selected_kitchen_items=selected)
    await update_kitchen_count(callback, state, item_id)


@router.callback_query(F.data.startswith("kitchen_decr_"))
async def kitchen_decrement(callback: CallbackQuery, state: FSMContext):
    """Уменьшаем количество ящика на 1 (минимум 0)"""
    item_id = callback.data.replace("kitchen_decr_", "")
    data = await state.get_data()
    selected = data.get("selected_kitchen_items", {})
    current = selected.get(item_id, 0)
    if current > 0:
        selected[item_id] = current - 1
    else:
        selected[item_id] = 0
    await state.update_data(selected_kitchen_items=selected)
    await update_kitchen_count(callback, state, item_id)


async def update_kitchen_count(callback: CallbackQuery, state: FSMContext, item_id: str):
    """Обновляет кнопку с количеством у конкретного ящика"""
    data = await state.get_data()
    selected = data.get("selected_kitchen_items", {})
    current_count = selected.get(item_id, 0)

    category = data.get("kitchen_category")
    if category == "upper":
        items = UPPER_TYPES
    elif category == "lower":
        items = LOWER_TYPES
    else:
        items = PANTRY_TYPES

    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        await callback.answer("❌ Тип не найден!")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➖",
                    callback_data=f"kitchen_decr_{item_id}"
                ),
                InlineKeyboardButton(
                    text=f"{current_count}",
                    callback_data=f"kitchen_count_{item_id}"
                ),
                InlineKeyboardButton(
                    text="➕",
                    callback_data=f"kitchen_incr_{item_id}"
                )
            ]
        ]
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

    await callback.answer(f"Количество: {current_count}")


# ==================== ЗАВЕРШЕНИЕ ВЫБОРА ====================

@router.callback_query(StateFilter(CalcState.KITCHEN_TYPE_SELECT), F.data == "finish_selection")
async def finish_kitchen_selection(callback: CallbackQuery, state: FSMContext):
    """Завершаем выбор ящиков и переходим к доп. услугам"""

    data = await state.get_data()
    selected = data.get("selected_kitchen_items", {})
    category = data.get("kitchen_category")

    if category == "upper":
        items_list = UPPER_TYPES
    elif category == "lower":
        items_list = LOWER_TYPES
    else:
        items_list = PANTRY_TYPES

    items = []
    for item_id, count in selected.items():
        if count > 0:
            item_name = next((i["text"] for i in items_list if i["id"] == item_id), item_id)
            items.append({
                "id": item_id,
                "name": item_name,
                "count": count,
                "category": category
            })

    if not items:
        await callback.answer("⚠️ Вы не выбрали ни одного ящика!", show_alert=True)
        return

    existing_items = data.get("current_kitchen_items", [])

    merged_items = existing_items.copy()
    for new_item in items:
        existing = next((i for i in merged_items if i["id"] == new_item["id"]), None)
        if existing:
            existing["count"] = new_item["count"]
            existing["category"] = category
        else:
            merged_items.append(new_item)

    merged_items = [i for i in merged_items if i["count"] > 0]

    if not merged_items:
        await callback.answer("⚠️ Вы не выбрали ни одного ящика!", show_alert=True)
        return

    await state.update_data(current_kitchen_items=merged_items)
    await state.set_state(CalcState.KITCHEN_EXTRAS)

    text = "✅ **Вы выбрали:**\n"
    for item in merged_items:
        text += f"  • {item['name']} — {item['count']} шт\n"

    text += "\n\n**Дополнительные услуги:**\n"
    text += "Выберите нужные опции:"

    await callback.message.edit_text(text, reply_markup=extras_kb(), parse_mode=None)
    await callback.answer()


# ==================== ДОП. УСЛУГИ ====================

@router.callback_query(StateFilter(CalcState.KITCHEN_EXTRAS))
async def kitchen_extras_handlers(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    kitchen_extras = data.get("current_kitchen_extras", [])

    if callback.data == "calculate_final":
        await save_kitchen_and_show_result(callback, state)
        return

    if callback.data == "back_to_prev":
        await state.set_state(CalcState.KITCHEN_CATEGORY)
        await callback.message.edit_text(
            "🍳 **Расчет кухни**\n\nВыберите категорию:",
            reply_markup=kitchen_category_kb(),
            parse_mode=None
        )
        await callback.answer()
        return

    if callback.data.startswith("extras_"):
        service = callback.data.replace("extras_", "")
        await state.update_data(current_extra_service=service)
        await state.set_state(CalcState.KITCHEN_EXTRAS_COUNT)

        # Определяем единицу измерения
        if service in ["lighting", "gola"]:
            unit = "метров (погонных)"
        else:
            unit = "штук"

        await callback.message.answer(
            f"✏️ Введите количество {unit} для **{extras_names.get(service, service)}**:\n"
            "Введите число (0 — чтобы убрать)"
        )
        await callback.answer()


# ==================== ВВОД КОЛИЧЕСТВА ДЛЯ ДОПОВ ====================

@router.message(StateFilter(CalcState.KITCHEN_EXTRAS_COUNT))
async def kitchen_extras_count_entered(message: Message, state: FSMContext):
    try:
        count = float(message.text.replace(",", "."))
        if count < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число (например: 2.5 или 3)")
        return

    data = await state.get_data()
    service = data.get("current_extra_service")
    kitchen_extras = data.get("current_kitchen_extras", [])  # ← СПИСОК
    extras_counts = data.get("current_extras_counts", {})  # ← СЛОВАРЬ

    if count > 0:
        if service not in kitchen_extras:
            kitchen_extras.append(service)  # ← РАБОТАЕТ, Т.К. ЭТО СПИСОК
        extras_counts[service] = count
        unit = "м" if service in ["lighting", "gola"] else "шт"
        await message.answer(f"✅ Добавлено: {extras_names.get(service, service)} — {count} {unit}")
    else:
        if service in kitchen_extras:
            kitchen_extras.remove(service)
        if service in extras_counts:
            del extras_counts[service]
        await message.answer(f"❌ Убран: {extras_names.get(service, service)}")

    await state.update_data(current_kitchen_extras=kitchen_extras)
    await state.update_data(current_extras_counts=extras_counts)
    await state.set_state(CalcState.KITCHEN_EXTRAS)

    await show_extras_summary(message, state)


async def show_extras_summary(message: Message, state: FSMContext):
    """Показывает текущий список выбранных допов с количеством"""
    data = await state.get_data()
    kitchen_extras = data.get("current_kitchen_extras", [])
    extras_counts = data.get("current_extras_counts", {})

    if not kitchen_extras:
        await message.answer("📋 Вы не выбрали ни одного допа")
        return

    text = "📋 **Выбранные допы:**\n"
    for extra in kitchen_extras:
        count = extras_counts.get(extra, 1)
        unit = "м" if extra in ["lighting", "gola"] else "шт"
        text += f"  • {extras_names.get(extra, extra)} — {count} {unit}\n"

    await message.answer(text, reply_markup=extras_kb(kitchen_extras))


# ==================== ОБЩАЯ СМЕТА ====================

async def show_total_calculation(callback: CallbackQuery, state: FSMContext):
    """Показывает общую смету по всем сохранённым позициям."""

    data = await state.get_data()

    kitchen_items = data.get("kitchen_items", [])
    wardrobe_items = data.get("wardrobe_items", [])

    # Удаляем пустые кухни и шкафы
    kitchen_items = [k for k in kitchen_items if k.get("items") and len(k.get("items", [])) > 0]
    wardrobe_items = [w for w in wardrobe_items if w.get("shelves", 0) > 0 or w.get("drawers", 0) > 0]

    await state.update_data(kitchen_items=kitchen_items)
    await state.update_data(wardrobe_items=wardrobe_items)

    if not kitchen_items and not wardrobe_items:
        await callback.answer("❌ Нет сохранённых расчетов!")
        return

    async with AsyncSessionLocal() as session:
        price_service = PriceService(session)
        prices = await price_service.get_all_prices()

    total_price = 0
    all_details = ""
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
        all_details += "🚪 **ШКАФЫ**\n\n"
        for idx, item in enumerate(wardrobe_items, 1):
            frame_type = item.get("frame_type")
            shelves = item.get("shelves", 0)
            drawers = item.get("drawers", 0)
            extras = item.get("extras", {})  # ← ТЕПЕРЬ СЛОВАРЬ

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

            # ✅ РАСЧЁТ ДОПОВ С КОЛИЧЕСТВОМ
            extras_cost = 0
            if extras:
                all_details += f"  • Допы:\n"
                for extra, count in extras.items():
                    price = additional_prices.get(extra, 0)
                    item_total_extra = price * count
                    extras_cost += item_total_extra
                    extra_name = extras_names_local.get(extra, extra)
                    unit = "м" if extra == "lighting" else "шт"
                    all_details += f"      - {extra_name}: {count} {unit} x {price:,.0f} руб = {item_total_extra:,.0f} руб\n"

            item_total += extras_cost
            total_price += item_total

            all_details += f"📦 **Шкаф №{idx}**\n"
            all_details += f"  • Каркас: {frame_names.get(frame_type, frame_type)}: {frame_price:,.0f} руб\n"
            all_details += f"  • Полки: {shelves} шт x {shelf_price:,.0f} руб = {shelves_cost:,.0f} руб\n"
            all_details += f"  • Ящики: {drawers} шт x {drawer_price:,.0f} руб = {drawers_cost:,.0f} руб\n"
            all_details += f"  • **Стоимость: {item_total:,.0f} руб**\n\n"


    # ========== КУХНИ ==========
    if kitchen_items:
        all_details += "🍳 **КУХНИ**\n\n"
        for idx, item in enumerate(kitchen_items, 1):
            category = item.get("category")
            items = item.get("items", [])
            extras = item.get("extras", {})

            if isinstance(extras, list):
                extras_dict = {}
                for extra in extras:
                    if extra in ["lighting", "gola", "extra_1", "extra_2", "extra_3", "extra_4", "extra_5"]:
                        extras_dict[extra] = 1
                extras = extras_dict

            kitchen_total = 0
            kitchen_prices = prices.get("kitchen", {})

            all_details += f"🍳 **Кухня №{idx}**\n"
            all_details += "  • Модули:\n"

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
                all_details += f"      - {sub_item['name']} — {count} шт: {item_total:,.0f} руб\n"

            extras_cost = 0
            if extras:
                all_details += "  • Допы:\n"
                for extra, count in extras.items():
                    # ✅ ПРАВИЛЬНЫЙ КЛЮЧ ДЛЯ ГОЛЫ
                    price_key = extra
                    if extra == "gola":
                        price_key = "gola_price"
                    price = prices.get("additional", {}).get(price_key, 0)
                    item_total = price * count
                    extras_cost += item_total
                    extra_name = extras_names_local.get(extra, extra)
                    unit = "м" if extra in ["lighting", "gola"] else "шт"
                    all_details += f"      - {extra_name}: {count} {unit} x {price:,.0f} руб = {item_total:,.0f} руб\n"

            kitchen_total += extras_cost
            total_price += kitchen_total
            all_details += f"  • **Стоимость: {kitchen_total:,.0f} руб**\n\n"

    if not all_details:
        await callback.answer("❌ Нет сохранённых расчетов!")
        return

    text = (
        "🧮 **ОБЩАЯ СМЕТА**\n\n"
        f"{all_details}"
        f"💰 **ОБЩИЙ ИТОГ: {total_price:,.0f} руб**\n\n"
        "📌 **Если что-то забыли** — нажмите «Добавить» и сделайте выбор.\n"
    )

    await callback.message.edit_text(text, reply_markup=after_calculation_kb(), parse_mode=None)
    await callback.answer("✅ Расчет сохранен!")


# ==================== СОХРАНЕНИЕ И СМЕТА ====================

async def save_kitchen_and_show_result(callback: CallbackQuery, state: FSMContext):
    """Сохраняем текущую кухню и показываем общую смету"""

    data = await state.get_data()

    editing_index = data.get("editing_kitchen_index")
    current_items = data.get("current_kitchen_items", [])
    kitchen_items = data.get("kitchen_items", [])
    extras_counts = data.get("current_extras_counts", {})
    kitchen_extras = data.get("current_kitchen_extras", [])

    # Если нет ящиков и не редактируем — не сохраняем
    if not current_items and editing_index is None:
        await callback.answer("⚠️ Нет ящиков для сохранения!", show_alert=True)
        await show_total_calculation(callback, state)
        return

    if editing_index is not None and editing_index < len(kitchen_items):
        old_kitchen = kitchen_items[editing_index]
        old_items = old_kitchen.get("items", [])

        merged_items = old_items.copy()
        for new_item in current_items:
            existing = next((i for i in merged_items if i["id"] == new_item["id"]), None)
            if existing:
                existing["count"] = new_item["count"]
            else:
                merged_items.append(new_item)

        merged_items = [i for i in merged_items if i["count"] > 0]

        if not merged_items:
            kitchen_items.pop(editing_index)
            await state.update_data(kitchen_items=kitchen_items)
            await state.update_data(editing_kitchen_index=None)
            await show_total_calculation(callback, state)
            return

        # Сохраняем с extras_counts (словарь)
        kitchen_items[editing_index] = {
            "category": data.get("kitchen_category"),
            "items": merged_items,
            "extras": extras_counts,
            "gola": "gola" in extras_counts
        }
        await state.update_data(kitchen_items=kitchen_items)
        await state.update_data(editing_kitchen_index=None)

    else:
        kitchen_item = {
            "category": data.get("kitchen_category"),
            "items": current_items,
            "extras": extras_counts,
            "gola": "gola" in extras_counts
        }
        kitchen_items.append(kitchen_item)
        await state.update_data(kitchen_items=kitchen_items)

    # Очищаем временные данные
    await state.update_data(current_kitchen_items=[])
    await state.update_data(current_kitchen_extras=[])
    await state.update_data(current_extras_counts={})
    await state.update_data(selected_kitchen_items={})

    await show_total_calculation(callback, state)


# ==================== ВОЗВРАТ К КАТЕГОРИЯМ ====================

@router.callback_query(F.data == "back_to_kitchen_categories")
async def back_to_kitchen_categories(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору категории кухни"""
    await state.set_state(CalcState.KITCHEN_CATEGORY)
    await callback.message.delete()
    await callback.message.answer(
        "🍳 **Расчет кухни**\n\nВыберите категорию:",
        reply_markup=kitchen_category_kb()
    )
    await callback.answer()