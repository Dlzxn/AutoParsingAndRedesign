from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
import asyncio

from WebApp.BackEnd.db.create_tables import User
from WebApp.BackEnd.db.create_database import DATABASE_URL, engine


# Создаём асинхронный SessionLocal
AsyncSessionLocal = sessionmaker(
    engine, class_= AsyncSession, expire_on_commit=False
)

class CRUD:
    def __getattribute__(self, name):
        attr = object.__getattribute__(self, name)
        if callable(attr):
            print(f"Метод {name} вызывается!")
            self.db = AsyncSessionLocal()
        return attr

    async def create_user(self, email, password):
        user = User(email=email, password=password)
        async with self.db.begin():
            self.db.add(user)
        await self.db.commit()
        return user

    async def verify_user(self, username, password):
        """Проверяем, существует ли пользователь с указанными данными"""
        result = await self.db.execute(
            select(User).filter(
                User.email == username,
                User.password == password
            )
        )
        user = result.scalars().first()
        return user

    async def is_subscribe(self, id) -> tuple[str, int] | None:
        """Проверяем статус подписки пользователя"""
        result = await self.db.execute(
            select(User).filter(User.id == id)
        )
        user = result.scalars().first()
        if user.is_admin:
            return ("Administrator", user.email)
        return (user.subscribe_status, user.email) if user else None

    async def is_admin(self, id) -> tuple[str, int] | None:
        result = await self.db.execute(
            select(User).filter(User.id == id)
        )
        user = result.scalars().first()
        return user.is_admin
    async def create_admin(self, email, password) -> bool:
        user = User(email=email, password=password, is_admin=True)
        async with self.db.begin():
            self.db.add(user)
        await self.db.commit()
        return user

db = CRUD()

