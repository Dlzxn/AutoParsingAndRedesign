
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.future import select

from WebApp.BackEnd.db.create_database import engine

Base = declarative_base()

class Promo(Base):
    __tablename__ = "promo"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(Boolean, default=True, nullable=False)
    type = Column(String, nullable=False) #подписка
    date_ended = Column(DateTime, nullable=True)
    count_activated = Column(Integer, nullable=False)
    bonus_count = Column(Integer, nullable=False)
    description = Column(String, nullable=True)


# Асинхронное создание всех таблиц
async def create_tables_promo():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Таблицы созданы. {promo table}")

async def drop_tables_promo():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Таблицы удалены. {promo table}")