from sqlalchemy import select, asc, desc, or_, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
import asyncio
from fastapi import HTTPException
from typing import Optional

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
        # Проверяем, существует ли пользователь с таким email
        result = await self.db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            return False

        # Если пользователя нет, создаём нового
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

    async def db_to_csv_data(self):
        result = await self.db.execute(select(User))
        rows = result.scalars().all()
        return rows

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

    """Admin Function"""
    async def get_users(
        self,
        page: int = 1,
        per_page: int = 10,
        sort: str = "id",
        order: str = "asc",
        search: Optional[str] = None
    ):
        try:
            # Базовый запрос
            query = select(User)

            # Поиск
            if search:
                query = query.where(
                    or_(
                        User.email.ilike(f"%{search}%"),
                        User.subscribe_status.ilike(f"%{search}%")
                    )
                )

            # Сортировка
            if order.lower() == "asc":
                order_func = asc
            else:
                order_func = desc

            if hasattr(User, sort):
                query = query.order_by(order_func(getattr(User, sort)))

            # Пагинация
            offset = (page - 1) * per_page
            result = await self.db.execute(
                query.offset(offset).limit(per_page)
            )
            users = result.scalars().all()

            # Общее количество
            total = await self.db.execute(
                select(func.count()).select_from(query.subquery()))
            total_count = total.scalar()

            return {
                "users": users,
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_count + per_page - 1) // per_page
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(e)}"
            )

    async def update_user(self, user_id: int, user_data: dict):
        try:
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Обновление полей с контролем типов
            for key, value in user_data.items():
                if hasattr(user, key):
                    field_type = User.__annotations__.get(key)
                    if field_type and not isinstance(value, field_type):
                        try:
                            value = field_type(value)
                        except (TypeError, ValueError):
                            raise ValueError(f"Invalid type for field {key}")

                    setattr(user, key, value)

            await self.db.commit()
            return user

        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Update failed: {str(e)}"
            )

db = CRUD()

# asyncio.run(db.create_admin("aleshamarichev09@gmail.com", "Yamnovo2006"))