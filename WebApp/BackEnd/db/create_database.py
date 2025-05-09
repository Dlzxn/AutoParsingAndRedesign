from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database

DATABASE_URL = "postgresql+asyncpg://myuser:mypassword@localhost:5432/dbname"

engine = create_async_engine(DATABASE_URL, echo=True)


async def check_and_create_database():
    if not database_exists(engine.url):
        await create_database(engine.url)
        print("Database creating....")
    else:
        print("Database already exists....")
