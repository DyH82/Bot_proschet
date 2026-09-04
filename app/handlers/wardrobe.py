from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.states import CalcState
from app.keyboards import extras_kb, after_calculation_kb, main_menu_kb
from app.handlers.common import WARDROBE_FRAMES, SHELF_TYPES, DRAWER_TYPES
from app.schemas import WardrobeFrame, AdditionalService
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


# ==================== ВЫБОР КАРКАСА ====================

@router.callback_query(F.data == "furniture_wardrobe")
async def wardrobe_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.WARDROBE_FRAME)

    data = await state.get_data()
    wardrobe_items = data.get("wardrobe_items", [])
    current_index = len(wardrobe_items) + 1
    await state.update_data(current_wardrobe_index=current_index)

    await callback.message.answer(
        f"🚪 **Шкаф №{current_index}**\n\nВыберите тип каркаса:"
    )

    for frame in WARDROBE_FRAMES:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Выбрать",
                    callback_data=f"wardrobe_frame_{frame['id']}"
                )]
            ]
        )

        try:
            photo = FSInputFile(frame["image"])
            await callback.message.answer_photo(
                photo=photo,
                caption=f"📦 **{frame['text']}**",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Ошибка загрузки картинки {frame['image']}: {e}")
            await callback.message.answer(
                f"📦 **{frame['text']}**\n(картинка не найдена)",
                reply_markup=keyboard
            )

    await callback.answer()


@router.callback_query(F.data.startswith("wardrobe_frame_"))
async def wardrobe_frame_chosen(callback: CallbackQuery, state: FSMContext):
    frame_type = callback.data.replace("wardrobe_frame_", "")
    await state.update_data(current_frame_type=frame_type)
    await state.set_state(CalcState.WARDROBE_SHELVES)

    await show_shelf_selection(callback, state)


# ==================== ВЫБОР ПОЛОК ====================

async def show_shelf_selection(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_shelves = data.get("selected_shelves", {})
    total_shelves = sum(selected_shelves.values())

    # Шапка с счетчиком — сохраняем ID
    msg = await callback.message.answer(
        f"📚 **Выберите полки**\n\n"
        f"✅ **Выбрано полок: {total_shelves} шт**\n\n"
        "Выберите количество полок с помощью кнопок ➕ и ➖ под каждой картинкой."
    )
    await state.update_data(shelf_header_message_id=msg.message_id)

    for item in SHELF_TYPES:
        item_id = item["id"]
        current_count = selected_shelves.get(item_id, 0)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➖",
                        callback_data=f"shelf_decr_{item_id}"
                    ),
                    InlineKeyboardButton(
                        text=f"{current_count}",
                        callback_data=f"shelf_count_{item_id}"
                    ),
                    InlineKeyboardButton(
                        text="➕",
                        callback_data=f"shelf_incr_{item_id}"
                    )
                ]
            ]
        )

        try:
            photo = FSInputFile(item["image"])
            await callback.message.answer_photo(
                photo=photo,
                caption=f"📚 **{item['text']}**",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Ошибка загрузки картинки {item['image']}: {e}")
            await callback.message.answer(
                f"📚 **{item['text']}**\n(картинка не найдена)",
                reply_markup=keyboard
            )

    control_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Далее → Ящики", callback_data="shelf_done")],
            [InlineKeyboardButton(text="🔙 Назад к каркасам", callback_data="back_to_frames")]
        ]
    )

    await callback.message.answer(
        "👇 Когда выберете все нужные полки, нажмите «Далее».",
        reply_markup=control_keyboard
    )


# ==================== КНОПКИ + И - ДЛЯ ПОЛОК ====================

@router.callback_query(F.data.startswith("shelf_incr_"))
async def shelf_increment(callback: CallbackQuery, state: FSMContext):
    item_id = callback.data.replace("shelf_incr_", "")
    data = await state.get_data()
    selected = data.get("selected_shelves", {})
    selected[item_id] = selected.get(item_id, 0) + 1
    await state.update_data(selected_shelves=selected)
    await update_shelf_count(callback, state, item_id)


@router.callback_query(F.data.startswith("shelf_decr_"))
async def shelf_decrement(callback: CallbackQuery, state: FSMContext):
    item_id = callback.data.replace("shelf_decr_", "")
    data = await state.get_data()
    selected = data.get("selected_shelves", {})
    current = selected.get(item_id, 0)
    if current > 0:
        selected[item_id] = current - 1
    else:
        selected[item_id] = 0
    await state.update_data(selected_shelves=selected)
    await update_shelf_count(callback, state, item_id)


async def update_shelf_count(callback: CallbackQuery, state: FSMContext, item_id: str):
    data = await state.get_data()
    selected = data.get("selected_shelves", {})
    current_count = selected.get(item_id, 0)
    total_shelves = sum(selected.values())
    header_msg_id = data.get("shelf_header_message_id")

    # Обновляем кнопку у картинки
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➖",
                    callback_data=f"shelf_decr_{item_id}"
                ),
                InlineKeyboardButton(
                    text=f"{current_count}",
                    callback_data=f"shelf_count_{item_id}"
                ),
                InlineKeyboardButton(
                    text="➕",
                    callback_data=f"shelf_incr_{item_id}"
                )
            ]
        ]
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

    # ✅ ОБНОВЛЯЕМ ШАПКУ
    if header_msg_id:
        try:
            await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=header_msg_id,
                text=(
                    f"📚 **Выберите полки**\n\n"
                    f"✅ **Выбрано полок: {total_shelves} шт**\n\n"
                    "Выберите количество полок с помощью кнопок ➕ и ➖ под каждой картинкой."
                )
            )
        except Exception as e:
            print(f"Ошибка обновления шапки: {e}")

    await callback.answer(f"Количество: {current_count}")


# ==================== ЗАВЕРШЕНИЕ ВЫБОРА ПОЛОК ====================

@router.callback_query(F.data == "shelf_done")
async def shelf_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_shelves", {})
    total_shelves = sum(selected.values())

    await state.update_data(current_shelves=total_shelves)
    await state.set_state(CalcState.WARDROBE_DRAWERS)

    await show_drawer_selection(callback, state)


# ==================== ВЫБОР ЯЩИКОВ ====================

async def show_drawer_selection(callback: CallbackQuery, state: FSMContext):
    """Показывает выбор ящиков с картинками и кнопками + и -"""

    data = await state.get_data()
    selected_drawers = data.get("selected_drawers", {})
    total_drawers = sum(selected_drawers.values())

    # Получаем информацию о каркасе и полках
    frame_type = data.get("current_frame_type")
    frame_names = {
        "standard": "150-800мм",
        "compact": "801-1500мм",
        "extended": "1501-2500мм"
    }
    frame_name = frame_names.get(frame_type, "не выбран")

    total_shelves = data.get("current_shelves", 0)

    # Шапка с полной информацией
    await callback.message.answer(
        f"📦 **Выберите выдвижные ящики**\n\n"
        f"📐 **Каркас:** {frame_name}\n"
        f"📚 **Полок выбрано:** {total_shelves} шт\n"
        f"✅ **Ящиков выбрано:** {total_drawers} шт\n\n"
        "Выберите количество ящиков с помощью кнопок ➕ и ➖ под каждой картинкой."
    )

    for item in DRAWER_TYPES:
        item_id = item["id"]
        current_count = selected_drawers.get(item_id, 0)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➖",
                        callback_data=f"drawer_decr_{item_id}"
                    ),
                    InlineKeyboardButton(
                        text=f"{current_count}",
                        callback_data=f"drawer_count_{item_id}"
                    ),
                    InlineKeyboardButton(
                        text="➕",
                        callback_data=f"drawer_incr_{item_id}"
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
            [InlineKeyboardButton(text="✅ Далее → Доп. услуги", callback_data="drawer_done")],
            [InlineKeyboardButton(text="🔙 Назад к полкам", callback_data="back_to_shelves")]
        ]
    )

    await callback.message.answer(
        "👇 Когда выберете все нужные ящики, нажмите «Далее».",
        reply_markup=control_keyboard
    )


# ==================== КНОПКИ + И - ДЛЯ ЯЩИКОВ ====================

@router.callback_query(F.data.startswith("drawer_incr_"))
async def drawer_increment(callback: CallbackQuery, state: FSMContext):
    item_id = callback.data.replace("drawer_incr_", "")
    data = await state.get_data()
    selected = data.get("selected_drawers", {})
    selected[item_id] = selected.get(item_id, 0) + 1
    await state.update_data(selected_drawers=selected)
    await update_drawer_count(callback, state, item_id)


@router.callback_query(F.data.startswith("drawer_decr_"))
async def drawer_decrement(callback: CallbackQuery, state: FSMContext):
    item_id = callback.data.replace("drawer_decr_", "")
    data = await state.get_data()
    selected = data.get("selected_drawers", {})
    current = selected.get(item_id, 0)
    if current > 0:
        selected[item_id] = current - 1
    else:
        selected[item_id] = 0
    await state.update_data(selected_drawers=selected)
    await update_drawer_count(callback, state, item_id)


async def update_drawer_count(callback: CallbackQuery, state: FSMContext, item_id: str):
    data = await state.get_data()
    selected = data.get("selected_drawers", {})
    current_count = selected.get(item_id, 0)
    total_drawers = sum(selected.values())
    header_msg_id = data.get("drawer_header_message_id")

    # Обновляем кнопку у картинки
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➖",
                    callback_data=f"drawer_decr_{item_id}"
                ),
                InlineKeyboardButton(
                    text=f"{current_count}",
                    callback_data=f"drawer_count_{item_id}"
                ),
                InlineKeyboardButton(
                    text="➕",
                    callback_data=f"drawer_incr_{item_id}"
                )
            ]
        ]
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

    # ✅ ОБНОВЛЯЕМ ШАПКУ
    if header_msg_id:
        try:
            await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=header_msg_id,
                text=(
                    f"📦 **Выберите выдвижные ящики**\n\n"
                    f"✅ **Выбрано ящиков: {total_drawers} шт**\n\n"
                    "Выберите количество ящиков с помощью кнопок ➕ и ➖ под каждой картинкой."
                )
            )
        except Exception as e:
            print(f"Ошибка обновления шапки: {e}")

    await callback.answer(f"Количество: {current_count}")


# ==================== ЗАВЕРШЕНИЕ ВЫБОРА ЯЩИКОВ ====================

@router.callback_query(F.data == "drawer_done")
async def drawer_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_drawers", {})
    total_drawers = sum(selected.values())

    await state.update_data(current_drawers=total_drawers)
    await state.set_state(CalcState.WARDROBE_EXTRAS)

    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        price_service = PriceService(session)
        add_prices = await price_service.get_additional_prices()

        services_text = "\n".join([
            f"• {name}: {add_prices.get(key, 0):,.0f} руб"
            for key, name in [
                ("lighting", "💡 Подсветка"),
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
        f"✅ **Шкаф №{data.get('current_wardrobe_index', 1)}**\n"
        f"📐 Каркас: {frame_names.get(data.get('current_frame_type'), data.get('current_frame_type'))}\n"
        f"📚 Полки: {data.get('current_shelves')} шт\n"
        f"📦 Ящики: {data.get('current_drawers')} шт\n\n"
        "**Дополнительные услуги:**\n"
        f"{services_text}\n\n"
        "Нажмите на услугу, чтобы добавить/убрать.\n"
        "Когда закончите — нажмите «Рассчитать стоимость»."
    )

    await callback.message.answer(text, reply_markup=extras_kb(), parse_mode=None)


# ==================== ДОП. УСЛУГИ ====================

@router.callback_query(StateFilter(CalcState.WARDROBE_EXTRAS))
async def wardrobe_extras_toggle(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    wardrobe_extras = data.get("current_wardrobe_extras", [])

    if callback.data == "calculate_final":
        await save_wardrobe_and_show_result(callback, state)
        return

    if callback.data == "back_to_prev":
        await state.set_state(CalcState.WARDROBE_DRAWERS)
        await callback.message.edit_text("📦 Введите количество ящиков:")
        await callback.answer()
        return

    if callback.data.startswith("extras_"):
        service = callback.data.replace("extras_", "")
        await state.update_data(current_extra_service=service)
        await state.set_state(CalcState.WARDROBE_EXTRAS_COUNT)

        # Определяем единицу измерения
        if service == "lighting":
            unit = "метров (погонных)"
        else:
            unit = "штук"

        await callback.message.answer(
            f"✏️ Введите количество {unit} для **{extras_names.get(service, service)}**:\n"
            "Введите число (0 — чтобы убрать)"
        )
        await callback.answer()


# ==================== ВВОД КОЛИЧЕСТВА ДЛЯ ДОПОВ ШКАФА ====================

@router.message(StateFilter(CalcState.WARDROBE_EXTRAS_COUNT))
async def wardrobe_extras_count_entered(message: Message, state: FSMContext):
    try:
        count = float(message.text.replace(",", "."))
        if count < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число (например: 2.5 или 3)")
        return

    data = await state.get_data()
    service = data.get("current_extra_service")
    wardrobe_extras = data.get("current_wardrobe_extras", [])
    wardrobe_extras_counts = data.get("current_wardrobe_extras_counts", {})

    if count > 0:
        if service not in wardrobe_extras:
            wardrobe_extras.append(service)
        wardrobe_extras_counts[service] = count
        unit = "м" if service == "lighting" else "шт"
        await message.answer(f"✅ Добавлено: {extras_names.get(service, service)} — {count} {unit}")
    else:
        if service in wardrobe_extras:
            wardrobe_extras.remove(service)
        if service in wardrobe_extras_counts:
            del wardrobe_extras_counts[service]
        await message.answer(f"❌ Убран: {extras_names.get(service, service)}")

    await state.update_data(current_wardrobe_extras=wardrobe_extras)
    await state.update_data(current_wardrobe_extras_counts=wardrobe_extras_counts)
    await state.set_state(CalcState.WARDROBE_EXTRAS)

    # Показываем обновлённый список
    await show_wardrobe_extras_summary(message, state)


async def show_wardrobe_extras_summary(message: Message, state: FSMContext):
    """Показывает текущий список выбранных допов для шкафа с количеством"""
    data = await state.get_data()
    wardrobe_extras = data.get("current_wardrobe_extras", [])
    wardrobe_extras_counts = data.get("current_wardrobe_extras_counts", {})

    if not wardrobe_extras:
        await message.answer("📋 Вы не выбрали ни одного допа")
        return

    # Получаем цены на услуги
    async with AsyncSessionLocal() as session:
        price_service = PriceService(session)
        add_prices = await price_service.get_additional_prices()

        services_text = "\n".join([
            f"• {name}: {add_prices.get(key, 0):,.0f} руб"
            for key, name in [
                ("lighting", "💡 Подсветка"),
                ("extra_1", "🔧 Доп 1"),
                ("extra_2", "🔧 Доп 2"),
                ("extra_3", "🔧 Доп 3"),
                ("extra_4", "🔧 Доп 4"),
                ("extra_5", "🔧 Доп 5")
            ]
        ])

    data = await state.get_data()
    frame_names = {
        "standard": "150-800мм",
        "compact": "801-1500мм",
        "extended": "1501-2500мм"
    }

    text = (
        f"✅ **Шкаф №{data.get('current_wardrobe_index', 1)}**\n"
        f"📐 Каркас: {frame_names.get(data.get('current_frame_type'), data.get('current_frame_type'))}\n"
        f"📚 Полки: {data.get('current_shelves')} шт\n"
        f"📦 Ящики: {data.get('current_drawers')} шт\n\n"
        "**Дополнительные услуги:**\n"
        f"{services_text}\n\n"
        "Нажмите на услугу, чтобы добавить/убрать.\n"
        "Когда закончите — нажмите «Рассчитать стоимость»."
    )

    await message.answer(text, reply_markup=extras_kb())


# ==================== НАВИГАЦИЯ ====================

@router.callback_query(F.data == "back_to_frames")
async def back_to_frames(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.WARDROBE_FRAME)
    await callback.message.delete()
    await wardrobe_start(callback, state)


@router.callback_query(F.data == "back_to_shelves")
async def back_to_shelves(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.WARDROBE_SHELVES)
    await callback.message.delete()
    await show_shelf_selection(callback, state)


# ==================== СОХРАНЕНИЕ И СМЕТА ====================

async def save_wardrobe_and_show_result(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    wardrobe_items = data.get("wardrobe_items", [])
    editing_index = data.get("editing_wardrobe_index")

    current_frame_type = data.get("current_frame_type")
    current_shelves = data.get("current_shelves", 0)
    current_drawers = data.get("current_drawers", 0)
    current_extras = data.get("current_wardrobe_extras", [])
    current_extras_counts = data.get("current_wardrobe_extras_counts", {})

    if editing_index is not None and editing_index < len(wardrobe_items):
        old_wardrobe = wardrobe_items[editing_index]
        old_frame_type = old_wardrobe.get("frame_type")
        old_extras = old_wardrobe.get("extras", {})

        # ✅ ОБЪЕДИНЯЕМ ДОПЫ
        merged_extras = old_extras.copy()
        for extra in current_extras:
            if extra in current_extras_counts:
                merged_extras[extra] = current_extras_counts[extra]

        wardrobe_item = {
            "index": data.get("current_wardrobe_index", 1),
            "frame_type": old_frame_type,
            "shelves": current_shelves,
            "drawers": current_drawers,
            "extras": merged_extras
        }

        wardrobe_items[editing_index] = wardrobe_item
        await state.update_data(wardrobe_items=wardrobe_items)
        await state.update_data(editing_wardrobe_index=None)

    else:
        # Новый шкаф
        extras_dict = {}
        for extra in current_extras:
            if extra in current_extras_counts:
                extras_dict[extra] = current_extras_counts[extra]

        wardrobe_item = {
            "index": data.get("current_wardrobe_index", 1),
            "frame_type": current_frame_type,
            "shelves": current_shelves,
            "drawers": current_drawers,
            "extras": extras_dict
        }
        wardrobe_items.append(wardrobe_item)
        await state.update_data(wardrobe_items=wardrobe_items)

    await state.update_data(current_frame_type=None)
    await state.update_data(current_shelves=0)
    await state.update_data(current_drawers=0)
    await state.update_data(current_wardrobe_extras=[])
    await state.update_data(current_wardrobe_extras_counts={})
    await state.update_data(selected_shelves={})
    await state.update_data(selected_drawers={})

    from app.handlers.kitchen import show_total_calculation
    await show_total_calculation(callback, state)