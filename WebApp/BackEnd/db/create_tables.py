from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from WebApp.BackEnd.db.create_database import engine

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), nullable=False)
    password = Column(String(100), nullable=False)

# Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

print("Таблицы созданы.")