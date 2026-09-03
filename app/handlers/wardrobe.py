from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.states import CalcState
from app.keyboards import wardrobe_frame_kb, extras_kb, after_calculation_kb, main_menu_kb
from app.handlers.common import WARDROBE_FRAMES
from app.schemas import WardrobeFrame, AdditionalService
from app.services.price_service import PriceService
from app.services.calculator import FurnitureCalculator
from app.database import AsyncSessionLocal

router = Router()


@router.callback_query(F.data == "furniture_wardrobe")
async def wardrobe_start(callback: CallbackQuery, state: FSMContext):
    """Начинаем новый расчет шкафа."""
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

    frame_names = {
        "standard": "Стандартный (600×2000)",
        "compact": "Компактный (500×1800)",
        "extended": "Ширина до 2500мм"
    }

    text = (
        f"✅ Выбран каркас: {frame_names.get(frame_type, frame_type)}\n\n"
        "📚 **Введите количество полок**\n"
        "(введите число)"
    )

    await callback.message.answer(text)
    await callback.answer()


@router.message(StateFilter(CalcState.WARDROBE_SHELVES))
async def wardrobe_shelves_entered(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите целое число (0 или больше)")
        return

    data = await state.get_data()
    old_shelves = data.get("current_shelves", 0)
    new_shelves = old_shelves + count
    await state.update_data(current_shelves=new_shelves)
    await state.set_state(CalcState.WARDROBE_DRAWERS)

    text = (
        f"✅ Полок: {new_shelves} (добавлено: +{count})\n\n"
        "📦 **Введите количество выдвижных ящиков**\n"
        "(введите число, 0 — чтобы пропустить)"
    )

    await message.answer(text)


@router.message(StateFilter(CalcState.WARDROBE_DRAWERS))
async def wardrobe_drawers_entered(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите целое число (0 или больше)")
        return

    data = await state.get_data()
    old_drawers = data.get("current_drawers", 0)
    new_drawers = old_drawers + count
    await state.update_data(current_drawers=new_drawers)
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
        "standard": "Стандартный",
        "compact": "Компактный",
        "extended": "до 2500мм"
    }

    text = (
        f"✅ **Шкаф №{data.get('current_wardrobe_index', 1)}**\n"
        f"📐 Каркас: {frame_names.get(data.get('current_frame_type'), data.get('current_frame_type'))}\n"
        f"📚 Полок: {data.get('current_shelves')}\n"
        f"📦 Ящиков: {data.get('current_drawers')}\n\n"
        "**Дополнительные услуги:**\n"
        f"{services_text}\n\n"
        "Нажмите на услугу, чтобы добавить/убрать.\n"
        "Когда закончите — нажмите «Рассчитать стоимость»."
    )

    await message.answer(text, reply_markup=extras_kb())


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
        if service in wardrobe_extras:
            wardrobe_extras.remove(service)
        else:
            wardrobe_extras.append(service)
        await state.update_data(current_wardrobe_extras=wardrobe_extras)
        await callback.message.edit_reply_markup(
            reply_markup=extras_kb(wardrobe_extras)
        )
        await callback.answer()


async def save_wardrobe_and_show_result(callback: CallbackQuery, state: FSMContext):
    """Сохраняем текущий шкаф в список и показываем общую смету."""

    data = await state.get_data()

    # Собираем данные текущего шкафа
    wardrobe_item = {
        "index": data.get("current_wardrobe_index", 1),
        "frame_type": data.get("current_frame_type"),
        "shelves": data.get("current_shelves", 0),
        "drawers": data.get("current_drawers", 0),
        "extras": data.get("current_wardrobe_extras", [])
    }

    # Сохраняем в список
    wardrobe_items = data.get("wardrobe_items", [])
    wardrobe_items.append(wardrobe_item)
    await state.update_data(wardrobe_items=wardrobe_items)

    # Очищаем временные данные
    await state.update_data(current_frame_type=None)
    await state.update_data(current_shelves=0)
    await state.update_data(current_drawers=0)
    await state.update_data(current_wardrobe_extras=[])

    # Показываем общую смету
    from app.handlers.kitchen import show_total_calculation
    await show_total_calculation(callback, state)