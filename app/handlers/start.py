from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from app.states import CalcState
from app.keyboards import main_menu_kb, kitchen_category_kb, after_calculation_kb
from app.handlers.common import WARDROBE_FRAMES

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🪑 **Добро пожаловать в бот расчета мебели!**\n\n"
        "👇 Выберите тип мебели:",
        reply_markup=main_menu_kb()
    )
    await state.set_state(CalcState.CHOOSING_TYPE)


@router.callback_query(F.data == "main_menu")
@router.callback_query(F.data == "new_calculation")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    # Полностью очищаем состояние при новом расчете
    await state.clear()
    await callback.message.edit_text(
        "🏠 **Главное меню**\n\nВыберите тип мебели:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "furniture_kitchen")
async def kitchen_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.KITCHEN_CATEGORY)
    await state.update_data(furniture_type="kitchen")
    await callback.message.edit_text(
        "🍳 **Расчет кухни**\n\nВыберите категорию:",
        reply_markup=kitchen_category_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "furniture_wardrobe")
async def wardrobe_start_from_menu(callback: CallbackQuery, state: FSMContext):
    """Вызов из главного меню -> передаем в wardrobe.py"""
    from app.handlers.wardrobe import wardrobe_start
    await wardrobe_start(callback, state)