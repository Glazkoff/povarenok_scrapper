import logging
from aiogram import Bot, Dispatcher, executor, types, md
from settings.config import TELEGRAM_API_TOKEN, PROXY_URL

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
    await call.message.answer("---")
    await call.answer(text="Вы были успешно добавлены в рассылку!")


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
