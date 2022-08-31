from enum import unique
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types, md
from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Column,
    DateTime,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from sqlalchemy.orm import Session, sessionmaker
from settings.config import TELEGRAM_API_TOKEN, PROXY_URL


engine = create_engine(
    "sqlite:///data/receipts.db",
    echo=True,
    encoding="utf-8",
)
engine.connect()

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_chat_id = Column(String(255), nullable=False, unique=True)
    created_on = Column(DateTime(), default=datetime.now)
    updated_on = Column(DateTime(), default=datetime.now)


Base.metadata.create_all(engine)

session = Session(bind=engine)
# -----------------------------------------------------------

# Конфигурация логирования
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчера
bot = Bot(
    token=TELEGRAM_API_TOKEN, proxy=PROXY_URL, parse_mode=types.ParseMode.MARKDOWN_V2
)
dp = Dispatcher(bot)


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    """
    Обработчик будет вызван когда пользователь отправить команду `/start` или `/help`
    """
    keyboard = types.InlineKeyboardMarkup()
    url_button = types.InlineKeyboardButton(
        text="Присоединиться к рассылке", callback_data="connect_user"
    )
    keyboard.add(url_button)
    await message.reply(
        md.text(
            md.text("Привет\!"),
            md.text('Я бот для парсера сайта "Поварёнок\.ру"\!'),
            md.text("Сделан Никитой Глазковым, 2022 год\."),
            sep="\n",
        ),
        reply_markup=keyboard,
    )


@dp.callback_query_handler(text="connect_user")
async def send_random_value(call: types.CallbackQuery):
    await call.message.answer("Добавляю в рассылку\.\.\.")
    try:
        tg_user = User(tg_chat_id=call.message.chat.id)
        session.add(tg_user)
        session.commit()
        await call.message.answer("Пользователь добавлен\!")
        await call.answer(text="Вы были успешно добавлены в рассылку!")
    except (IntegrityError, PendingRollbackError):
        await call.message.answer("Вы уже добавлены в рассылку\!")
        await call.answer(text="Действие недоступно\.")
    except Exception:
        await call.message.answer("Произошла неизвестная ошибка")
        await call.answer(text="Попробуйте позднее.")


@dp.message_handler(commands=["chat_info"])
async def send_chat_info(message: types.Message):
    await message.answer(
        md.text(
            md.text("ID чата: ", md.code(message.chat.id)),
            sep="\n",
        ),
    )


def main():
    executor.start_polling(dp)


if __name__ == "__main__":
    main()
