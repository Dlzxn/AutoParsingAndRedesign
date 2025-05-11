from sqlalchemy import select, asc, desc, or_, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
import asyncio
from fastapi import HTTPException
from typing import Optional
from functools import wraps

from WebApp.BackEnd.promo.db.create_tables_promo import Promo
from WebApp.BackEnd.db.create_database import DATABASE_URL, engine


# Создаём асинхронный SessionLocal
AsyncSessionLocal = sessionmaker(
    engine, class_= AsyncSession, expire_on_commit=False
)

def with_session(func):
    """Create and Delete Session"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        self.db = AsyncSessionLocal()
        try:
            return await func(self, *args, **kwargs)
        finally:
            await self.db.close()

    return wrapper

class CRUD:
    def __init__(self):
        self.db = None
    @with_session
    async def get_all_promo(self):
        query = await self.db.execute(select(Promo))
        return query.scalars().all()
    @with_session
    async def get_promo(self, num):
        query = await self.db.execute(select(Promo).filter(Promo.id == num))
        return query.scalars().first()
    @with_session
    async def create_promo(self, data: Promo):
        promo = Promo(name = data.name, type = data.type, status = data.status,
                     date_ended = data.date_ended, count_activated=data.count_activated,
                     bonus_count=data.bonus_count, description = data.description,)
        async with self.db.begin():
            self.db.add(promo)


        await self.db.commit()
        return promo
    @with_session
    async def update_promo(self, id: int, data: Promo):
        result = await self.db.execute(select(Promo).filter(Promo.id == id))
        promo = result.scalars().first()
        if promo is None:
            raise HTTPException(status_code=404, detail="Promo Not Found")
        for attr, value in data.__dict__.items():
            if attr != "id" and hasattr(promo, attr):
                setattr(promo, attr, value)

        await self.db.commit()
        await self.db.refresh(promo)
        return promo


db_promo = CRUD()