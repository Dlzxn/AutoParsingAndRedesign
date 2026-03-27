import asyncio
import csv
import aiofiles
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


from WebApp.BackEnd.db.create_tables import User
from WebApp.BackEnd.db.create_database import engine, DATABASE_URL
from WebApp.BackEnd.db.CRUD import db

async def export_to_csv():
    rows = await db.db_to_csv_data()
    print(f"rows: {rows}")

    async with aiofiles.open('data.csv', mode='w', encoding='utf-8', newline='') as f:

        header = "id,email,password,is_admin,subscribe_status,date_start,date_end,token_today\n"
        await f.write(header)
        for row in rows:
            line = (
                f"{row.id},"
                f"{row.email},"
                f"{row.password},"
                f"{row.is_admin},"
                f"{row.subscribe_status},"
                f"{row.date_start or 'None'},"
                f"{row.date_end or 'None'},"
                f"{row.token_today}\n"
            )
            await f.write(line)

# asyncio.run(export_to_csv())