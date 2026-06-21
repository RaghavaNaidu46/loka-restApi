import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def main():
    engine = create_async_engine(settings.databaseUrl, echo=True)
    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE citizens ADD COLUMN IF NOT EXISTS original_name VARCHAR(100);")
        )
        await conn.execute(
            text("ALTER TABLE citizens ADD COLUMN IF NOT EXISTS date_of_birth VARCHAR(20);")
        )
        await conn.execute(
            text("ALTER TABLE citizens ADD COLUMN IF NOT EXISTS address TEXT;")
        )
        await conn.execute(
            text("ALTER TABLE citizens ADD COLUMN IF NOT EXISTS aadhaar_number VARCHAR(20);")
        )
    print("Database columns added successfully.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
