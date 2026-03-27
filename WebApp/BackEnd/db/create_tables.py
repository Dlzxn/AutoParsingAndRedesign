from WebApp.BackEnd.db.create_database import engine

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.future import select

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), nullable=False)
    password = Column(String(100), nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    subscribe_status = Column(String(20), nullable=False, default="Free")
    date_start = Column(DateTime, nullable=True)
    date_end = Column(DateTime, nullable=True)
    token_today = Column(Integer, nullable=False, default=0)

# Асинхронное создание всех таблиц
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Таблицы созданы.")

async def drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Таблицы удалены.")