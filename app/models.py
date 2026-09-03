from sqlalchemy import (
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
