#!/usr/bin/env python3
"""
Скрипт для автоматического создания структуры проекта furniture_bot.
Запускается из корневой директории.
"""

import os
import sys
from pathlib import Path

# Структура проекта: папки и файлы (пустые или с содержимым)
PROJECT_STRUCTURE = {
    # ====== КОРНЕВЫЕ ФАЙЛЫ (на одном уровне с папкой app) ======
    ".env": """BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=furniture_bot
""",
    "docker-compose.yml": """version: '3.8'

services:
  db:
    image: postgres:16-alpine
    container_name: furniture_db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: furniture_bot
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  bot:
    build: .
    container_name: furniture_bot
    depends_on:
      - db
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - ./app:/app/app

  adminer:
    image: adminer:latest
    container_name: furniture_adminer
    ports:
      - "8080:8080"
    depends_on:
      - db
    restart: unless-stopped

volumes:
  postgres_data:
""",
    "Dockerfile": """FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "app.main"]
""",
    "requirements.txt": """aiogram==3.16.0
sqlalchemy==2.0.35
asyncpg==0.29.0
alembic==1.13.0
pydantic-settings==2.4.0
python-dotenv==1.0.1
""",
    "alembic.ini": """[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql://postgres:postgres@localhost/furniture_bot

[post_write_hooks]
hooks = black
black.type = console_scripts
black.entrypoint = black
""",

    # ====== ПАПКА app и всё её содержимое ======
    "app/__init__.py": "",
    "app/main.py": """#!/usr/bin/env python3
\"\"\"Точка входа бота.\"\"\"

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.handlers import start, kitchen, wardrobe
from app.database import engine, Base


async def create_tables():
    \"\"\"Создание таблиц в БД.\"\"\"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    \"\"\"Запуск бота.\"\"\"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Создаем таблицы
    await create_tables()

    # Инициализируем бота и диспетчер
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()

    # Регистрируем роутеры
    dp.include_router(start.router)
    dp.include_router(kitchen.router)
    dp.include_router(wardrobe.router)

    # Запускаем поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
""",
    "app/config.py": """from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    bot_token: str = Field(..., env="BOT_TOKEN")

    db_host: str = Field("localhost", env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    db_user: str = Field("postgres", env="DB_USER")
    db_password: str = Field("postgres", env="DB_PASSWORD")
    db_name: str = Field("furniture_bot", env="DB_NAME")

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
""",
    "app/database.py": """from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from app.config import settings

engine = create_async_engine(
    settings.db_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
""",
    "app/models.py": """from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    JSON, Enum as SQLEnum, Text, Boolean
)
from sqlalchemy.sql import func
from app.database import Base
import enum


class FurnitureType(str, enum.Enum):
    KITCHEN = "kitchen"
    WARDROBE = "wardrobe"


class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False, index=True)
    key = Column(String(100), nullable=False, index=True)
    value = Column(Float, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CalculationHistory(Base):
    __tablename__ = "calculation_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    furniture_type = Column(SQLEnum(FurnitureType), nullable=False)
    params = Column(JSON, nullable=False)
    breakdown = Column(JSON, nullable=False)
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
""",
    "app/schemas.py": """from pydantic import BaseModel
from typing import List, Optional, Dict
from enum import Enum


class FurnitureType(str, Enum):
    KITCHEN = "kitchen"
    WARDROBE = "wardrobe"


class CabinetType(str, Enum):
    UPPER = "upper"
    LOWER = "lower"


class WardrobeFrame(str, Enum):
    STANDARD = "standard"
    COMPACT = "compact"
    EXTENDED = "extended"


class AdditionalService(str, Enum):
    LIGHTING = "lighting"
    HANDLES = "handles"
    DELIVERY = "delivery"
    ASSEMBLY = "assembly"
    INDIVIDUAL = "individual"


class CalculationResult(BaseModel):
    total_price: float
    breakdown: Dict[str, float]
    details: str
    base_price: float
""",
    "app/states.py": """from aiogram.fsm.state import State, StatesGroup


class CalcState(StatesGroup):
    CHOOSING_TYPE = State()

    KITCHEN_CABINET = State()
    KITCHEN_LENGTH = State()
    KITCHEN_EXTRAS = State()

    WARDROBE_FRAME = State()
    WARDROBE_DRAWERS = State()
    WARDROBE_SHELVES = State()
    WARDROBE_DOORS = State()
    WARDROBE_EXTRAS = State()
""",

    # ====== ПАПКА services ======
    "app/services/__init__.py": "",
    "app/services/calculator.py": """from typing import List, Dict, Optional
from app.schemas import (
    CabinetType, WardrobeFrame, AdditionalService, 
    CalculationResult
)


class FurnitureCalculator:
    def __init__(self, prices: Dict[str, Dict[str, float]]):
        self.prices = prices
        self.kitchen_prices = prices.get("kitchen", {})
        self.wardrobe_prices = prices.get("wardrobe", {})
        self.additional_prices = prices.get("additional", {})

    def calculate_kitchen(
        self,
        cabinet_type: CabinetType,
        length_meters: float,
        extras: List[AdditionalService]
    ) -> CalculationResult:
        base = self.kitchen_prices.get(cabinet_type.value, 0)
        per_meter = self.kitchen_prices.get("per_meter", 0)
        base_length = self.kitchen_prices.get("base_length", 1.0)

        if length_meters > base_length:
            length_surcharge = (length_meters - base_length) * per_meter
        else:
            length_surcharge = 0

        extras_cost = sum(
            self.additional_prices.get(service.value, 0) 
            for service in extras
        )

        total = base + length_surcharge + extras_cost

        breakdown = {"Базовый ящик": base}
        if length_surcharge > 0:
            breakdown[f"Доплата за длину ({length_meters:.1f}м)"] = length_surcharge

        service_names = {
            "lighting": "Подсветка",
            "handles": "Ручки",
            "delivery": "Доставка",
            "assembly": "Сборка",
            "individual": "Индивидуальный размер"
        }
        for service in extras:
            price = self.additional_prices.get(service.value, 0)
            if price > 0:
                breakdown[service_names.get(service.value, service.value)] = price

        return CalculationResult(
            base_price=base,
            total_price=total,
            breakdown=breakdown,
            details=f"Кухня, тип: {cabinet_type.value}, длина: {length_meters:.1f}м"
        )

    def calculate_wardrobe(
        self,
        frame_type: WardrobeFrame,
        drawers_count: int,
        shelves_count: int,
        doors_count: int,
        extras: List[AdditionalService]
    ) -> CalculationResult:
        frame_cost = self.wardrobe_prices.get(f"frame_{frame_type.value}", 0)
        drawer_price = self.wardrobe_prices.get("drawer", 0)
        shelf_price = self.wardrobe_prices.get("shelf", 0)
        door_price = self.wardrobe_prices.get("door", 0)

        drawers_cost = drawers_count * drawer_price
        shelves_cost = shelves_count * shelf_price
        doors_cost = doors_count * door_price

        base = frame_cost + drawers_cost + shelves_cost + doors_cost

        extras_cost = sum(
            self.additional_prices.get(service.value, 0) 
            for service in extras
        )

        total = base + extras_cost

        frame_names = {
            "standard": "Стандартный (600×2000)",
            "compact": "Компактный (500×1800)",
            "extended": "Увеличенный (800×2400)"
        }

        breakdown = {
            f"Каркас ({frame_names.get(frame_type.value, frame_type.value)})": frame_cost,
            f"Выдвижные ящики ({drawers_count} шт)": drawers_cost,
            f"Полки ({shelves_count} шт)": shelves_cost,
            f"Дверцы ({doors_count} шт)": doors_cost
        }

        service_names = {
            "lighting": "Подсветка",
            "handles": "Ручки",
            "delivery": "Доставка",
            "assembly": "Сборка",
            "individual": "Индивидуальный размер"
        }
        for service in extras:
            price = self.additional_prices.get(service.value, 0)
            if price > 0:
                breakdown[service_names.get(service.value, service.value)] = price

        return CalculationResult(
            base_price=base,
            total_price=total,
            breakdown=breakdown,
            details=f"Шкаф, каркас: {frame_type.value}, ящиков: {drawers_count}, полок: {shelves_count}"
        )
""",
    "app/services/price_service.py": """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Price
from typing import Dict, Optional


class PriceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_price(self, category: str, key: str) -> Optional[float]:
        query = select(Price).where(
            Price.category == category,
            Price.key == key
        )
        result = await self.session.execute(query)
        price = result.scalar_one_or_none()
        return price.value if price else None

    async def get_all_prices(self) -> Dict[str, Dict[str, float]]:
        query = select(Price)
        result = await self.session.execute(query)
        prices = result.scalars().all()

        data = {}
        for p in prices:
            if p.category not in data:
                data[p.category] = {}
            data[p.category][p.key] = p.value

        return data

    async def get_additional_prices(self) -> Dict[str, float]:
        query = select(Price).where(Price.category == "additional")
        result = await self.session.execute(query)
        prices = result.scalars().all()
        return {p.key: p.value for p in prices}
""",

    # ====== ПАПКА handlers ======
    "app/handlers/__init__.py": "",
    "app/handlers/start.py": """from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from app.states import CalcState
from app.keyboards import main_menu_kb

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    text = (
        "🪑 **Добро пожаловать в бот расчета мебели!**\\n\\n"
        "Я помогу вам рассчитать стоимость проектирования "
        "кухонь и шкафов.\\n\\n"
        "📋 **Как я работаю:**\\n"
        "1. Вы выбираете тип мебели\\n"
        "2. Указываете параметры\\n"
        "3. Добавляете дополнительные услуги\\n"
        "4. Получаете детальную смету\\n\\n"
        "👇 **Выберите тип мебели:**"
    )

    await message.answer(text, reply_markup=main_menu_kb())
    await state.set_state(CalcState.CHOOSING_TYPE)


@router.callback_query(F.data == "main_menu")
@router.callback_query(F.data == "new_calculation")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🏠 **Главное меню**\\n\\nВыберите тип мебели:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()
""",
    "app/handlers/kitchen.py": """from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.states import CalcState
from app.keyboards import kitchen_cabinet_kb, extras_kb, after_calculation_kb
from app.schemas import CabinetType, AdditionalService
from app.services.price_service import PriceService
from app.services.calculator import FurnitureCalculator
from app.database import AsyncSessionLocal

router = Router()


@router.callback_query(F.data == "kitchen_start")
async def kitchen_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.KITCHEN_CABINET)
    await state.update_data(furniture_type="kitchen")

    text = "🍳 **Расчет кухни**\\n\\nВыберите тип ящика:"
    await callback.message.edit_text(text, reply_markup=kitchen_cabinet_kb())
    await callback.answer()


@router.callback_query(
    StateFilter(CalcState.KITCHEN_CABINET),
    F.data.startswith("cabinet_")
)
async def kitchen_cabinet_chosen(callback: CallbackQuery, state: FSMContext):
    cabinet_type = callback.data.replace("cabinet_", "")
    await state.update_data(cabinet_type=cabinet_type)
    await state.set_state(CalcState.KITCHEN_LENGTH)

    text = (
        "📐 **Введите длину кухонного гарнитура**\\n\\n"
        "Введите число в метрах, например: 1.5, 2.0, 3.5\\n\\n"
        "⚠️ Базовая длина 1 метр включена в стоимость."
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_kitchen_cabinet")

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "back_to_kitchen_cabinet")
async def back_to_cabinet_choice(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.KITCHEN_CABINET)
    await callback.message.edit_text(
        "🍳 Выберите тип ящика:",
        reply_markup=kitchen_cabinet_kb()
    )
    await callback.answer()


@router.message(StateFilter(CalcState.KITCHEN_LENGTH))
async def kitchen_length_entered(message: Message, state: FSMContext):
    try:
        length = float(message.text.replace(",", "."))
        if length <= 0 or length > 20:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0.1 до 20")
        return

    await state.update_data(length=length)
    await state.set_state(CalcState.KITCHEN_EXTRAS)

    data = await state.get_data()
    cabinet_type = data.get("cabinet_type", "не выбран")

    text = (
        f"✅ Вы выбрали: {cabinet_type} ящик\\n"
        f"📐 Длина: {length:.1f} м\\n\\n"
        "**Дополнительные услуги:**\\n"
        "Нажмите на услугу, чтобы добавить/убрать.\\n"
        "Когда закончите — нажмите «Рассчитать стоимость»."
    )

    await message.answer(text, reply_markup=extras_kb())


@router.callback_query(StateFilter(CalcState.KITCHEN_EXTRAS))
async def kitchen_extras_toggle(callback: CallbackQuery, state: FSMContext):
    if callback.data == "calculate_final":
        await calculate_kitchen_result(callback, state)
        return

    if callback.data == "back_to_prev":
        await state.set_state(CalcState.KITCHEN_LENGTH)
        await callback.message.edit_text("📐 Введите длину:")
        await callback.answer()
        return

    if callback.data.startswith("extras_"):
        service = callback.data.replace("extras_", "")
        data = await state.get_data()
        selected = data.get("selected_extras", [])

        if service in selected:
            selected.remove(service)
        else:
            selected.append(service)

        await state.update_data(selected_extras=selected)
        await callback.message.edit_reply_markup(
            reply_markup=extras_kb(selected)
        )
        await callback.answer()


async def calculate_kitchen_result(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    try:
        cabinet_enum = CabinetType(data.get("cabinet_type"))
    except ValueError:
        await callback.answer("❌ Ошибка")
        return

    length = data.get("length", 0)
    selected = data.get("selected_extras", [])
    extras_enum = [AdditionalService(s) for s in selected if s in AdditionalService._value2member_map_]

    async with AsyncSessionLocal() as session:
        price_service = PriceService(session)
        prices = await price_service.get_all_prices()

    calculator = FurnitureCalculator(prices)
    result = calculator.calculate_kitchen(cabinet_enum, length, extras_enum)

    text = (
        "🧮 **Результат расчета кухни**\\n\\n"
        f"📋 {result.details}\\n\\n"
        "💰 **Смета:**\\n"
    )
    for item, price in result.breakdown.items():
        if price > 0:
            text += f"  • {item}: {price:,.0f} руб\\n"
    text += f"\\n**Итого: {result.total_price:,.0f} руб**"

    await callback.message.edit_text(text, reply_markup=after_calculation_kb())
    await callback.answer("✅ Расчет выполнен!")
""",
    "app/handlers/wardrobe.py": """from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.states import CalcState
from app.keyboards import wardrobe_frame_kb, extras_kb, after_calculation_kb
from app.schemas import WardrobeFrame, AdditionalService
from app.services.price_service import PriceService
from app.services.calculator import FurnitureCalculator
from app.database import AsyncSessionLocal

router = Router()


@router.callback_query(F.data == "wardrobe_start")
async def wardrobe_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.WARDROBE_FRAME)
    await state.update_data(furniture_type="wardrobe")
    await callback.message.edit_text(
        "🚪 **Расчет шкафа**\\n\\nВыберите тип каркаса:",
        reply_markup=wardrobe_frame_kb()
    )
    await callback.answer()


@router.callback_query(
    StateFilter(CalcState.WARDROBE_FRAME),
    F.data.startswith("frame_")
)
async def wardrobe_frame_chosen(callback: CallbackQuery, state: FSMContext):
    frame_type = callback.data.replace("frame_", "")
    await state.update_data(frame_type=frame_type)
    await state.set_state(CalcState.WARDROBE_DRAWERS)

    text = f"✅ Выбран каркас: {frame_type}\\n\\n📦 **Введите количество выдвижных ящиков** (0-10)"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_wardrobe_frame")

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "back_to_wardrobe_frame")
async def back_to_frame_choice(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.WARDROBE_FRAME)
    await callback.message.edit_text(
        "🚪 Выберите тип каркаса:",
        reply_markup=wardrobe_frame_kb()
    )
    await callback.answer()


@router.message(StateFilter(CalcState.WARDROBE_DRAWERS))
async def wardrobe_drawers_entered(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count < 0 or count > 10:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0 до 10")
        return

    await state.update_data(drawers=count)
    await state.set_state(CalcState.WARDROBE_SHELVES)
    await message.answer(f"✅ Ящиков: {count}\\n\\n📚 **Введите количество полок** (0-10)")


@router.message(StateFilter(CalcState.WARDROBE_SHELVES))
async def wardrobe_shelves_entered(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count < 0 or count > 10:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0 до 10")
        return

    await state.update_data(shelves=count)
    await state.set_state(CalcState.WARDROBE_DOORS)
    await message.answer(f"✅ Полок: {count}\\n\\n🚪 **Введите количество дверей** (0-10)")


@router.message(StateFilter(CalcState.WARDROBE_DOORS))
async def wardrobe_doors_entered(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count < 0 or count > 10:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0 до 10")
        return

    await state.update_data(doors=count)
    await state.set_state(CalcState.WARDROBE_EXTRAS)

    data = await state.get_data()
    text = (
        f"✅ Каркас: {data.get('frame_type')}\\n"
        f"📦 Ящиков: {data.get('drawers')}\\n"
        f"📚 Полок: {data.get('shelves')}\\n"
        f"🚪 Дверей: {data.get('doors')}\\n\\n"
        "**Дополнительные услуги:**\\n"
        "Нажмите на услугу, чтобы добавить/убрать."
    )

    await message.answer(text, reply_markup=extras_kb())


@router.callback_query(StateFilter(CalcState.WARDROBE_EXTRAS))
async def wardrobe_extras_toggle(callback: CallbackQuery, state: FSMContext):
    if callback.data == "calculate_final":
        await calculate_wardrobe_result(callback, state)
        return

    if callback.data == "back_to_prev":
        await state.set_state(CalcState.WARDROBE_DOORS)
        await callback.message.edit_text("🚪 Введите количество дверей:")
        await callback.answer()
        return

    if callback.data.startswith("extras_"):
        service = callback.data.replace("extras_", "")
        data = await state.get_data()
        selected = data.get("selected_extras", [])

        if service in selected:
            selected.remove(service)
        else:
            selected.append(service)

        await state.update_data(selected_extras=selected)
        await callback.message.edit_reply_markup(
            reply_markup=extras_kb(selected)
        )
        await callback.answer()


async def calculate_wardrobe_result(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    try:
        frame_enum = WardrobeFrame(data.get("frame_type"))
    except ValueError:
        await callback.answer("❌ Ошибка")
        return

    drawers = data.get("drawers", 0)
    shelves = data.get("shelves", 0)
    doors = data.get("doors", 0)
    selected = data.get("selected_extras", [])
    extras_enum = [AdditionalService(s) for s in selected if s in AdditionalService._value2member_map_]

    async with AsyncSessionLocal() as session:
        price_service = PriceService(session)
        prices = await price_service.get_all_prices()

    calculator = FurnitureCalculator(prices)
    result = calculator.calculate_wardrobe(frame_enum, drawers, shelves, doors, extras_enum)

    text = (
        "🧮 **Результат расчета шкафа**\\n\\n"
        f"📋 {result.details}\\n\\n"
        "💰 **Смета:**\\n"
    )
    for item, price in result.breakdown.items():
        if price > 0:
            text += f"  • {item}: {price:,.0f} руб\\n"
    text += f"\\n**Итого: {result.total_price:,.0f} руб**"

    await callback.message.edit_text(text, reply_markup=after_calculation_kb())
    await callback.answer("✅ Расчет выполнен!")
""",

    # ====== ПАПКА keyboards ======
    "app/keyboards/__init__.py": """from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from app.schemas import CabinetType, WardrobeFrame, AdditionalService


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🍳 Кухня", callback_data="kitchen_start")
    builder.button(text="🚪 Шкаф", callback_data="wardrobe_start")
    builder.adjust(1)
    return builder.as_markup()


def back_to_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    return builder.as_markup()


def kitchen_cabinet_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Верхний ящик", callback_data="cabinet_upper")
    builder.button(text="📦 Нижний ящик", callback_data="cabinet_lower")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def wardrobe_frame_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📐 Стандартный", callback_data="frame_standard")
    builder.button(text="📐 Компактный", callback_data="frame_compact")
    builder.button(text="📐 Увеличенный", callback_data="frame_extended")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def extras_kb(selected: list[str] = None) -> InlineKeyboardMarkup:
    selected = selected or []
    services = {
        "lighting": "💡 Подсветка",
        "handles": "🔧 Ручки",
        "delivery": "🚚 Доставка",
        "assembly": "🔩 Сборка",
        "individual": "📏 Индивидуальный размер"
    }

    builder = InlineKeyboardBuilder()
    for key, label in services.items():
        if key in selected:
            label = f"✅ {label}"
        builder.button(text=label, callback_data=f"extras_{key}")

    builder.button(text="✅ Рассчитать стоимость", callback_data="calculate_final")
    builder.button(text="🔙 Назад", callback_data="back_to_prev")
    builder.adjust(1)
    return builder.as_markup()


def after_calculation_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Новый расчет", callback_data="new_calculation")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()
""",

    # ====== ПАПКА migrations ======
    "migrations/__init__.py": "",
    "migrations/versions/.gitkeep": "",
    "migrations/env.py": """from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base
from app.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
""",
    "migrations/script.py.mako": "\"\"\"${message}\n\nRevision ID: ${up_revision}\nRevises: ${down_revision | comma,n}\nCreate Date: ${create_date}\n\n\"\"\"\nfrom typing import Sequence, Union\n\nfrom alembic import op\nimport sqlalchemy as sa\n${imports if imports else \"\"}\n\n# revision identifiers, used by Alembic.\nrevision: str = ${repr(up_revision)}\ndown_revision: Union[str, None] = ${repr(down_revision)}\nbranch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}\ndepends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}\n\n\ndef upgrade() -> None:\n    ${upgrades if upgrades else \"pass\"}\n\n\ndef downgrade() -> None:\n    ${downgrades if downgrades else \"pass\"}\n""",
}


def create_project_structure(base_path: str = "."):
    """Создает структуру проекта."""
    base = Path(base_path)

    print(f"🚀 Создаю структуру проекта в {base.absolute()}")
    print("-" * 60)

    created_files = 0
    created_dirs = 0
    skipped = 0

    for path, content in PROJECT_STRUCTURE.items():
        full_path = base / path

        # Проверяем, не существует ли уже файл
        if full_path.exists():
            print(f"⏭️ Пропущен (существует): {path}")
            skipped += 1
            continue

        if full_path.suffix == "":  # Это папка
            full_path.mkdir(parents=True, exist_ok=True)
            created_dirs += 1
            print(f"📁 Создана папка: {path}")
        else:
            # Создаем файл
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            created_files += 1
            print(f"📄 Создан файл: {path}")

    print("-" * 60)
    print(f"✅ Готово! Создано:")
    print(f"   • Папок: {created_dirs}")
    print(f"   • Файлов: {created_files}")
    print(f"   • Пропущено: {skipped}")
    print(f"\n📌 Теперь выполните:")
    print(f"   cd {base.absolute()}")
    print(f"   docker-compose up -d --build")
    print(f"\n📌 Или для локальной разработки:")
    print(f"   pip install -r requirements.txt")
    print(f"   python -m app.main")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Создать структуру проекта furniture_bot"
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Путь для создания проекта (по умолчанию: текущая папка)"
    )

    args = parser.parse_args()

    # Проверяем, не существует ли уже папка app
    target = Path(args.path)
    if (target / "app").exists():
        print("⚠️ Папка app уже существует в указанной директории!")
        response = input("Продолжить и перезаписать файлы? (y/N): ")
        if response.lower() != 'y':
            print("❌ Отменено.")
            sys.exit(0)

    create_project_structure(args.path)