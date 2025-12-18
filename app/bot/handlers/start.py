from aiogram import Router, types
from aiogram.filters import CommandStart, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, AnalyticsEvent

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject, session: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    # Регистрация/проверка юзера в БД
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        referrer_id = None
        args = command.args
        if args and args.isdigit():
            possible_referrer_id = int(args)
            if possible_referrer_id != user_id:
                # Используем scalar_one_or_none для проверки
                ref_check = await session.execute(select(User).where(User.id == possible_referrer_id))
                if ref_check.scalar_one_or_none():
                    referrer_id = possible_referrer_id

        new_user = User(id=user_id, username=username, full_name=full_name, referrer_id=referrer_id)
        session.add(new_user)
        session.add(AnalyticsEvent(user_id=user_id, event_type="registration",
                                   details=f"Ref: {referrer_id}" if referrer_id else "Organic"))

        try:
            await session.commit()
            await message.answer(
                f"Приветствую тебя, {full_name}. ✨\n\nЗвезды указали мне на твое появление. Все ответы уже ждут тебя внутри.\n\nНажми на кнопку меню, чтобы открыть свою Звездную Карту.")
        except Exception as e:
            await session.rollback()  # Откат при ошибке
            # Логирование ошибки можно добавить, если нужно
            await message.answer("Звезды сегодня неспокойны. Попробуйте нажать /start позже.")

    else:
        await message.answer(
            "Звезды снова свели нас. ✨\nТвоя судьба записана в карте. Открой приложение через меню, чтобы узнать больше.")