import json
import asyncio
import uvicorn
import logging
from datetime import date, time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from openai import AsyncOpenAI
from flatlib.datetime import Datetime as FlatlibDatetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib import const

from app.core.config import settings
from app.core.database import async_session_factory, get_db
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.handlers import start
from app.models import User

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ---
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
session = AiohttpSession()
bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), session=session)
dp = Dispatcher()
dp.update.middleware(DbSessionMiddleware(session_pool=async_session_factory))
dp.include_router(start.router)


# --- LIFESPAN (КОРРЕКТНЫЙ ЗАПУСК И ОСТАНОВКА) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info("🚀 Starting Bot & API...")
    await bot.delete_webhook(drop_pending_updates=True)
    polling_task = asyncio.create_task(dp.start_polling(bot))

    yield

    # SHUTDOWN
    logger.info("🛑 Shutting down...")
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

    # Закрываем сессии корректно
    await session.close()
    await bot.session.close()
    await openai_client.close()  # <--- Добавлено
    logger.info("✅ Bot & OpenAI sessions closed.")


app = FastAPI(title="Mini App Backend", lifespan=lifespan)

# --- СТАТИКА ---
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://stateofbrain.ru", "https://www.stateofbrain.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,  # Добавьте это
)


# --- DTO ---
class ChatRequest(BaseModel):
    user_id: int
    message: str


class ChatResponse(BaseModel):
    reply: str


class HoroscopeRequest(BaseModel):
    user_id: int
    message: str


class ProfileResponse(BaseModel):
    user_id: int
    full_name: str | None
    birth_date: str | None
    birth_time: str | None
    birth_place: str | None
    theme: str | None
    natal_analysis: str | None
    numerology_analysis: str | None
    daily_advice: str | None
    daily_affirmation: str | None


class ProfileUpdate(BaseModel):
    user_id: int
    full_name: str | None = None
    birth_date: str | None = None
    birth_time: str | None = None
    birth_place: str | None = None
    theme: str | None = None


# --- API HANDLERS ---

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "system": "active"}


@app.get("/api/get_profile/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    today = date.today()

    if not user:
        return ProfileResponse(
            user_id=user_id, full_name="Гость", birth_date=None,
            birth_time=None, birth_place=None, theme="default",
            natal_analysis=None, numerology_analysis=None,
            daily_advice=None, daily_affirmation=None
        )

    # Проверяем дату кэша
    advice = user.daily_advice if user.last_advice_date == today else None
    affirmation = user.daily_affirmation if user.last_affirmation_date == today else None

    return ProfileResponse(
        user_id=user.id,
        full_name=user.full_name,
        birth_date=user.birth_date.isoformat() if user.birth_date else None,
        birth_time=user.birth_time.strftime("%H:%M") if user.birth_time else None,
        birth_place=user.birth_place,
        theme=user.theme,
        natal_analysis=user.natal_analysis,
        numerology_analysis=user.numerology_analysis,
        daily_advice=advice,
        daily_affirmation=affirmation
    )


@app.post("/api/update_profile")
async def update_profile(raw_req: Request, db: AsyncSession = Depends(get_db)):
    # Читаем "сырой" текст и парсим вручную
    body_bytes = await raw_req.body()
    data = json.loads(body_bytes)
    request = ProfileUpdate(**data)  # Валидируем через Pydantic

    result = await db.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(id=request.user_id)
        db.add(user)

    if request.full_name: user.full_name = request.full_name
    if request.birth_place: user.birth_place = request.birth_place
    if request.theme: user.theme = request.theme

    date_changed = False
    if request.birth_date:
        try:
            new_date = date.fromisoformat(request.birth_date)
            if user.birth_date != new_date:
                user.birth_date = new_date
                date_changed = True
        except ValueError:
            pass

    if request.birth_time:
        try:
            user.birth_time = time.fromisoformat(request.birth_time)
            date_changed = True
        except ValueError:
            pass

    if date_changed:
        user.natal_analysis = None
        user.numerology_analysis = None

    await db.commit()
    return {"status": "success"}


@app.post("/api/daily_advice", response_model=ChatResponse)
async def daily_advice(raw_req: Request, db: AsyncSession = Depends(get_db)):
    # Ручной парсинг
    body_bytes = await raw_req.body()
    data = json.loads(body_bytes)
    request = HoroscopeRequest(**data)

    result = await db.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()

    today = date.today()

    if user and user.daily_advice and user.last_advice_date == today:
        return ChatResponse(reply=user.daily_advice)

    try:
        response = await asyncio.wait_for(
            openai_client.chat.completions.create(
                model="gpt-4.1-mini-2025-04-14",
                messages=[
                    {"role": "system",
                     "content": "Ты мистический астролог. Дай короткий совет на день (макс 20 слов) с эмодзи."},
                    {"role": "user", "content": f"Дай совет. Данные: {request.message}"}
                ],
                temperature=0.9
            ),
            timeout=10.0
        )
        advice_text = response.choices[0].message.content

        if user:
            user.daily_advice = advice_text
            user.last_advice_date = today
            await db.commit()

        return ChatResponse(reply=advice_text)

    except asyncio.TimeoutError:
        return ChatResponse(reply="Звезды сегодня молчаливы... (Попробуйте позже)")
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return ChatResponse(reply="Энергетический сбой. Повторите запрос.")


# --- ASTRO ---
CITY_COORDS = {
    "москва": (55.75, 37.61), "санкт-петербург": (59.93, 30.33),
    "екатеринбург": (56.84, 60.60), "новосибирск": (55.00, 82.93),
    "казань": (55.78, 49.12), "киев": (50.45, 30.52),
    "минск": (53.90, 27.56), "алматы": (43.22, 76.85),
    "лондон": (51.50, -0.12), "нью-йорк": (40.71, -74.00),
}


@app.get("/api/get_natal_chart/{user_id}")
async def get_natal_chart(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.birth_date:
        return {"error": "Нет данных рождения"}

    b_time = user.birth_time.strftime("%H:%M") if user.birth_time else "12:00"
    b_date = user.birth_date.strftime("%Y/%m/%d")
    city_key = user.birth_place.lower().strip() if user.birth_place else ""
    # Координаты (можно расширить список)
    lat, lon = CITY_COORDS.get(city_key, (51.50, -0.12))

    try:
        # ВЫНОСИМ ТЯЖЕЛЫЙ РАСЧЕТ В ОТДЕЛЬНЫЙ ПОТОК, ЧТОБЫ НЕ БЛОКИРОВАТЬ СЕРВЕР
        def calculate_chart():
            date_obj = FlatlibDatetime(b_date, b_time, '+00:00')
            pos = GeoPos(lat, lon)
            return Chart(date_obj, pos)

        chart = await asyncio.to_thread(calculate_chart)

        planets_data = []
        objects = [
            (const.SUN, "Солнце", "☀️"), (const.MOON, "Луна", "🌙"),
            (const.MERCURY, "Меркурий", "☿️"), (const.VENUS, "Венера", "♀️"),
            (const.MARS, "Марс", "♂️"), (const.JUPITER, "Юпитер", "♃"),
            (const.SATURN, "Сатурн", "♄"),
        ]

        ZODIAC_NAMES = {
            "Aries": "Овен", "Taurus": "Телец", "Gemini": "Близнецы",
            "Cancer": "Рак", "Leo": "Лев", "Virgo": "Дева",
            "Libra": "Весы", "Scorpio": "Скорпион", "Sagittarius": "Стрелец",
            "Capricorn": "Козерог", "Aquarius": "Водолей", "Pisces": "Рыбы"
        }

        for obj_code, name, icon in objects:
            planet = chart.get(obj_code)
            sign_ru = ZODIAC_NAMES.get(planet.sign, planet.sign)
            planets_data.append({
                "name": name, "icon": icon, "sign": sign_ru,
                "deg": f"{int(planet.lon % 30)}°"
            })

        return {"status": "ok", "planets": planets_data}
    except Exception as e:
        logger.error(f"Astro calc error: {e}")
        return {"error": "Ошибка расчета орбит"}


@app.post("/api/analyze_natal_chart", response_model=ChatResponse)
async def analyze_natal_chart(raw_req: Request, db: AsyncSession = Depends(get_db)):
    body_bytes = await raw_req.body()
    data = json.loads(body_bytes)
    request = HoroscopeRequest(**data)

    result = await db.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.birth_date:
        return ChatResponse(reply="Сначала заполните дату рождения в настройках.")

    if user.natal_analysis:
        return ChatResponse(reply=user.natal_analysis)

    try:
        b_time = user.birth_time.strftime("%H:%M") if user.birth_time else "12:00"
        b_date = user.birth_date.strftime("%Y/%m/%d")
        city_key = user.birth_place.lower().strip() if user.birth_place else ""
        lat, lon = CITY_COORDS.get(city_key, (51.50, -0.12))

        def calculate_chart_summary():
            date_obj = FlatlibDatetime(b_date, b_time, '+00:00')
            pos = GeoPos(lat, lon)
            chart = Chart(date_obj, pos)
            planets_desc = []
            for obj in [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS]:
                p = chart.get(obj)
                planets_desc.append(f"{obj} in {p.sign}")
            return ", ".join(planets_desc)

        chart_summary = await asyncio.to_thread(calculate_chart_summary)
    except Exception as e:
        logger.error(f"Error calculating: {e}")
        return ChatResponse(reply="Звезды сейчас не видны.")

    try:
        response = await asyncio.wait_for(
            openai_client.chat.completions.create(
                model="gpt-4.1-mini-2025-04-14",
                messages=[
                    {"role": "system",
                     "content": "Ты профессиональный астролог. Дай краткий (100 слов) психологический портрет. Выдели 'Ядро', 'Эмоции', 'Мышление'. Markdown (жирный)."},
                    {"role": "user", "content": f"Проанализируй: {chart_summary}"}
                ],
                temperature=0.8
            ),
            timeout=15.0
        )
        analysis_text = response.choices[0].message.content

        user.natal_analysis = analysis_text
        await db.commit()

        return ChatResponse(reply=analysis_text)
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return ChatResponse(reply="Оракул сейчас отдыхает.")


# --- NUMEROLOGY ---
def calculate_life_path_number(birth_date: date) -> int:
    digits = f"{birth_date.year}{birth_date.month:02d}{birth_date.day:02d}"
    total = sum(int(d) for d in digits)
    while total > 9 and total not in [11, 22, 33]:
        total = sum(int(d) for d in str(total))
    return total


@app.post("/api/get_numerology", response_model=ChatResponse)
async def get_numerology(raw_req: Request, db: AsyncSession = Depends(get_db)):
    body_bytes = await raw_req.body()
    data = json.loads(body_bytes)
    request = HoroscopeRequest(**data)

    result = await db.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.birth_date:
        return ChatResponse(reply="Сначала укажите дату рождения.")

    if user.numerology_analysis:
        return ChatResponse(reply=user.numerology_analysis)

    life_path_number = calculate_life_path_number(user.birth_date)

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            messages=[
                {"role": "system",
                 "content": "Ты нумеролог. Опиши Число Жизненного Пути. Мистически, макс 120 слов, Markdown."},
                {"role": "user", "content": f"Число пути: {life_path_number}"}
            ],
            temperature=0.8
        )
        full_reply = f"YOUR_NUMBER:{life_path_number}\n\n" + response.choices[0].message.content

        user.numerology_analysis = full_reply
        await db.commit()

        return ChatResponse(reply=full_reply)
    except Exception as e:
        return ChatResponse(reply=f"Ошибка нумерологии: {e}")


@app.post("/api/get_affirmation", response_model=ChatResponse)
async def get_affirmation(raw_req: Request, db: AsyncSession = Depends(get_db)):
    # Парсим ID юзера, чтобы сохранить в базу
    body_bytes = await raw_req.body()
    # Нам нужен user_id, поэтому парсим JSON
    try:
        data = json.loads(body_bytes)
        user_id = data.get("user_id")
    except:
        user_id = None

    # Пытаемся достать юзера для сохранения
    user = None
    today = date.today()
    if user_id:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        # Если уже есть аффирмация на сегодня - возвращаем её (экономим GPT)
        if user and user.daily_affirmation and user.last_affirmation_date == today:
            return ChatResponse(reply=user.daily_affirmation)

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            messages=[
                {"role": "system",
                 "content": "Ты духовный наставник. Дай одну мощную, короткую аффирмацию (установку) на сегодня. Темы: уверенность, спокойствие, энергия. Без кавычек."},
                {"role": "user", "content": "Дай установку."}
            ],
            temperature=1.0
        )
        affirmation_text = response.choices[0].message.content

        # Сохраняем в БД
        if user:
            user.daily_affirmation = affirmation_text
            user.last_affirmation_date = today
            await db.commit()

        return ChatResponse(reply=affirmation_text)
    except Exception as e:
        logger.error(f"Affirmation error: {e}")
        return ChatResponse(reply="Вселенная любит тебя. (Ошибка связи)")


if __name__ == "__main__":
    # Запускаем Uvicorn напрямую, он будет управлять lifespan
    uvicorn.run(app, host="0.0.0.0", port=8000)