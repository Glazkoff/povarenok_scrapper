import logging
import asyncio
from aiogram import Bot, Dispatcher, types, md
from aiogram.utils import exceptions, executor
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from settings.config import TELEGRAM_API_TOKEN, PROXY_URL
from db.tables import User
from db.base import Session, engine, Base

Base.metadata.create_all(engine)
db_session = Session()

# -----------------------------------------------------------

# Конфигурация логирования
logging.basicConfig(level=logging.INFO)
broadcast_log = logging.getLogger("broadcast")

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
        db_session.add(tg_user)
        db_session.commit()
        await call.message.answer("Пользователь добавлен\!")
        await call.answer(text="Вы были успешно добавлены в рассылку!")
    except (IntegrityError, PendingRollbackError) as e:
        await call.message.answer("Вы уже добавлены в рассылку\!")
        await call.answer(text="Действие недоступно\.")
        db_session.rollback()
        broadcast_log.error(f"[ERROR]: {e}.")
    except Exception as e:
        await call.message.answer("Произошла неизвестная ошибка")
        await call.answer(text="Попробуйте позднее.")
        db_session.rollback()
        broadcast_log.error(f"[ERROR]: {e}.")


@dp.message_handler(commands=["chat_info"])
async def send_chat_info(message: types.Message):
    await message.answer(
        md.text(
            md.text("ID чата: ", md.code(message.chat.id)),
            sep="\n",
        ),
    )


# -----------------------------------------------------------
def get_users():
    users = db_session.query(User).all()
    return [user.tg_chat_id for user in users]


async def send_message(
    user_id: int, text: str, disable_notification: bool = False
) -> bool:
    """
    Safe messages sender

    :param user_id:
    :param text:
    :param disable_notification:
    :return:
    """
    try:
        await bot.send_message(
            user_id,
            text,
            disable_notification=disable_notification,
            parse_mode="",
        )
    except exceptions.BotBlocked:
        broadcast_log.error(f"Target [ID:{user_id}]: blocked by user")
    except exceptions.ChatNotFound:
        broadcast_log.error(f"Target [ID:{user_id}]: invalid user ID")
    except exceptions.RetryAfter as e:
        broadcast_log.error(
            f"Target [ID:{user_id}]: Flood limit is exceeded. Sleep {e.timeout} seconds."
        )
        await asyncio.sleep(e.timeout)
        return await send_message(user_id, text)  # Recursive call
    except exceptions.UserDeactivated:
        broadcast_log.error(f"Target [ID:{user_id}]: user is deactivated")
    except exceptions.TelegramAPIError:
        broadcast_log.exception(f"Target [ID:{user_id}]: failed")
    except Exception as e:
        broadcast_log.error(f"Target [ID:{user_id}]: {e}")
    else:
        broadcast_log.info(f"Target [ID:{user_id}]: success")
        return True
    return False


async def broadcaster(message: str = "Привет\!") -> int:
    """
    Simple broadcaster

    * return Count of messages
    """
    count = 0
    try:
        for user_id in get_users():
            if await send_message(user_id, md.text(message)):
                count += 1
            await asyncio.sleep(
                0.05
            )  # 20 messages per second (Limit: 30 messages per second)
    except Exception as e:
        broadcast_log.error(f"{e}")
    finally:
        broadcast_log.info(f"{count} messages successful sent.")

    return count


@dp.message_handler(commands=["message"])
async def send_messages(message: types.Message):
    await message.reply(
        md.text(
            md.text("Рассылка сообщений\.\.\.\!"),
            sep="\n",
        )
    )
    await broadcaster()


def main():
    executor.start_polling(dp)


if __name__ == "__main__":
    main()
