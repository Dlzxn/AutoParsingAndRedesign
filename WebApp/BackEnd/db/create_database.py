from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import sessionmaker


USER = "myuser"
PASSWORD = "mypassword"
HOST = "localhost"
PORT = 5432
DATABASE = "dbname"

DATABASE_URL = f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

if not database_exists(engine.url):
    create_database(engine.url)
    print("Database creating....")
else:
    print("Database already exists....")
