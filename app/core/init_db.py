import asyncio
from app.core.database import engine, Base
from app.models import User, AnalyticsEvent, Transaction

async def main():
    async with engine.begin() as conn:
        print("♻️ Обновляю структуру базы данных...")
        # Drop all удалит данные! Если не хочешь терять - используй ALTER TABLE вручную или Alembic
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        print("✅ База данных готова к кэшированию.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())