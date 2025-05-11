from sqlalchemy import select, asc, desc, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from functools import wraps
from typing import Optional, Dict

from WebApp.BackEnd.db.create_tables import User
from WebApp.BackEnd.db.create_database import DATABASE_URL, engine


# Создаём асинхронный SessionLocal
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def with_session(func):
    """Создание и закрытие сессии"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        async with AsyncSessionLocal() as db:  # создаем сессию для каждого запроса
            try:
                return await func(self, db, *args, **kwargs)  # передаем сессию в функцию
            except Exception as e:
                # Логируем ошибку и поднимаем HTTP исключение
                print(f"[ERROR] {e}")
                raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return wrapper

class CRUD:
    def __init__(self):
        self.db = None

    @with_session
    async def create_user(self, db: AsyncSession, email: str, password: str):
        # Проверяем, существует ли пользователь с таким email
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            return False

        # Если пользователя нет, создаём нового
        user = User(email=email, password=password)
        async with db.begin():
            db.add(user)

        await db.commit()
        return user

    @with_session
    async def verify_user(self, db: AsyncSession, username: str, password: str):
        """Проверяем, существует ли пользователь с указанными данными"""
        result = await db.execute(
            select(User).filter(
                User.email == username,
                User.password == password
            )
        )
        user = result.scalars().first()
        return user

    @with_session
    async def db_to_csv_data(self, db: AsyncSession):
        result = await db.execute(select(User))
        rows = result.scalars().all()
        return rows

    @with_session
    async def is_subscribe(self, db: AsyncSession, user_id: int) -> Optional[tuple[str, int]]:
        """Проверяем статус подписки пользователя"""
        result = await db.execute(
            select(User).filter(User.id == user_id)
        )
        user = result.scalars().first()
        if user and user.is_admin:
            return ("Administrator", user.email)
        return (user.subscribe_status, user.email) if user else None

    @with_session
    async def is_admin(self, db: AsyncSession, user_id: int) -> bool:
        result = await db.execute(
            select(User).filter(User.id == user_id)
        )
        user = result.scalars().first()
        return user.is_admin if user else False

    @with_session
    async def create_admin(self, db: AsyncSession, email: str, password: str) -> bool:
        user = User(email=email, password=password, is_admin=True)
        async with db.begin():
            db.add(user)
        await db.commit()
        return True

    """Admin Function"""
    @with_session
    async def get_users(
        self,
        db: AsyncSession,
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
            order_func = asc if order.lower() == "asc" else desc
            if hasattr(User, sort):
                query = query.order_by(order_func(getattr(User, sort)))

            # Пагинация
            offset = (page - 1) * per_page
            result = await db.execute(
                query.offset(offset).limit(per_page)
            )
            users = result.scalars().all()

            # Общее количество
            total = await db.execute(
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
            print(f"[ERROR] {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(e)}"
            )

    @with_session
    async def update_user(self, db: AsyncSession, user_id: int, user_data: dict):
        try:
            result = await db.execute(
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

            await db.commit()
            return user

        except ValueError as ve:
            print(f"[ERROR] {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            await db.rollback()
            print(f"[ERROR] {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Update failed: {str(e)}"
            )

db = CRUD()
