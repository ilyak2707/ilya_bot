import logging
import os
import re
from textwrap import dedent

from dotenv import load_dotenv
from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
CHECKLIST_PATH = os.getenv("CHECKLIST_PATH", "/home/deploy/tg-bot/checklist.pdf")

ASK_FULL_NAME, ASK_ROLE, ASK_PHONE, ASK_EMAIL, CONFIRM_CONSENT = range(5)

ROLE_OPTIONS = [
    "Руководитель",
    "Собственник бизнеса",
    "Индивидуальный предприниматель",
    "Физическое лицо",
    "Другое",
]

CONSENT_ACCEPT = "✅ Да, даю согласие"
CONSENT_DECLINE = "❌ Нет, не даю согласие"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и информация об обработке персональных данных."""

    keyboard = [[KeyboardButton(text="Получить чек-лист")]]
    welcome_text = dedent(
        """
        👋 Добро пожаловать! Этот бот поможет вам получить чек-лист по подготовке бизнеса.

        Нажимая кнопку «Получить чек-лист», вы инициируете передачу своих персональных данных для связи и отправки материала. Передача данных осуществляется в соответствии с Федеральным законом № 152-ФЗ «О персональных данных».

        Вы можете ознакомиться с дополнительной информацией и своими правами с помощью команды /privacy.
        """
    ).strip()

    await update.message.reply_text(
        welcome_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


async def show_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет информацию об обработке персональных данных."""

    privacy_text = dedent(
        """
        ℹ️ Информация об обработке персональных данных

        Оператор: Индивидуальный предприниматель Колдышев Илья Евгеньевич, ИНН 245689644332, адрес электронной почты для связи: office@koldyshev.ru.

        Цели обработки: связь с вами по запросу чек-листа, предоставление материалов, а также информирование о новых продуктах и услугах.

        Правовые основания: ваша инициатива по получению чек-листа и добровольно предоставленное согласие согласно Федеральному закону № 152-ФЗ «О персональных данных» и Федеральному закону № 38-ФЗ «О рекламе» (для возможных рассылок).

        Срок обработки: до достижения целей обработки либо до отзыва согласия.

        Права субъекта: вы вправе запросить уточнение, блокирование, уничтожение данных или отозвать согласие. Для этого отправьте письмо на office@koldyshev.ru либо воспользуйтесь командой /revoke.
        """
    ).strip()

    await update.message.reply_text(privacy_text, reply_markup=ReplyKeyboardRemove())


async def revoke_consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Фиксирует отзыв согласия и уведомляет оператора."""

    user = update.effective_user
    message = (
        "Получен запрос на отзыв согласия. Мы перестанем использовать ваши данные и удалим их в разумный срок."
    )

    if ADMIN_CHAT_ID:
        admin_message = dedent(
            f"""
            ⚠️ Пользователь отозвал согласие на обработку данных.
            ID: {user.id}
            Имя: {user.full_name}
            Username: @{user.username if user.username else '—'}
            """
        ).strip()
        await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=admin_message)

    await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())


async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает анкету для получения чек-листа."""

    context.user_data.clear()
    await update.message.reply_text(
        "Пожалуйста, укажите вашу фамилию, имя и отчество (при наличии).",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_FULL_NAME


async def ask_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.text.strip()
    if len(full_name.split()) < 2:
        await update.message.reply_text(
            "Пожалуйста, введите фамилию и имя полностью, например: Иванов Иван." \
            " Если отчества нет — напишите «без отчества»."
        )
        return ASK_FULL_NAME

    context.user_data["full_name"] = full_name
    keyboard = [[KeyboardButton(text=option)] for option in ROLE_OPTIONS]
    await update.message.reply_text(
        "Уточните, в каком статусе вы обращаетесь:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
    )
    return ASK_ROLE


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    role = update.message.text.strip()
    context.user_data["role"] = role
    await update.message.reply_text(
        "Оставьте, пожалуйста, номер телефона для связи (формат +7XXXXXXXXXX)."
    )
    return ASK_PHONE


async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    if not re.fullmatch(r"\+7\d{10}", phone):
        await update.message.reply_text(
            "Номер должен быть в формате +7XXXXXXXXXX. Попробуйте ещё раз."
        )
        return ASK_PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text(
        "Укажите адрес электронной почты (для отправки материалов и обратной связи).",
    )
    return ASK_EMAIL


async def ask_consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if not re.fullmatch(email_pattern, email):
        await update.message.reply_text("Пожалуйста, введите корректный адрес электронной почты.")
        return ASK_EMAIL

    context.user_data["email"] = email

    consent_text = dedent(
        f"""
        Для завершения оформления необходимо ваше согласие на обработку персональных данных.

        Подтверждая согласие, вы разрешаете оператору (ИП Колдышев Илья Евгеньевич, ИНН 245689644332) обрабатывать указанные вами данные с целью отправки чек-листа, обратной связи и направления информации о продуктах и услугах. Обработка включает сбор, запись, систематизацию, накопление, хранение, уточнение, использование, передачу (в том числе с использованием сервисов рассылок, расположенных на территории РФ), обезличивание и уничтожение данных.

        Согласие действует до достижения целей обработки или до вашего отзыва. Вы можете отозвать его в любой момент, отправив запрос на office@koldyshev.ru или используя команду /revoke.

        Пожалуйста, подтвердите своё решение.
        """
    ).strip()

    keyboard = [[KeyboardButton(text=CONSENT_ACCEPT)], [KeyboardButton(text=CONSENT_DECLINE)]]
    await update.message.reply_text(
        consent_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
    )
    return CONFIRM_CONSENT


async def finalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    if choice != CONSENT_ACCEPT:
        await update.message.reply_text(
            "Вы отказались от обработки персональных данных. Чек-лист не будет отправлен. Если передумаете — нажмите «Получить чек-лист».",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(text="Получить чек-лист")]], resize_keyboard=True
            ),
        )
        context.user_data.clear()
        return ConversationHandler.END

    user_data = context.user_data.copy()
    user = update.effective_user

    summary = dedent(
        f"""
        ✅ Получены новые данные по заявке на чек-лист.

        Telegram ID: {user.id}
        Имя в Telegram: {user.full_name}
        Username: @{user.username if user.username else '—'}

        ФИО: {user_data.get('full_name')}
        Статус: {user_data.get('role')}
        Телефон: {user_data.get('phone')}
        Email: {user_data.get('email')}
        """
    ).strip()

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=summary)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Не удалось отправить сообщение администратору: %s", exc)
    else:
        logger.warning("ADMIN_CHAT_ID не задан. Данные пользователя не отправлены администратору.")

    await update.message.reply_text(
        "Спасибо! Ниже прикреплён чек-лист. Если письмо не пришло, проверьте папку «Спам».",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(text="Получить чек-лист")]], resize_keyboard=True
        ),
    )

    if os.path.exists(CHECKLIST_PATH):
        try:
            with open(CHECKLIST_PATH, "rb") as checklist_file:
                await update.message.reply_document(
                    document=checklist_file,
                    filename=os.path.basename(CHECKLIST_PATH),
                    caption="Чек-лист по подготовке бизнеса",
                )
        except OSError as exc:
            logger.exception("Не удалось отправить файл чек-листа: %s", exc)
            await update.message.reply_text(
                "Файл временно недоступен. Мы отправим его вам позже по электронной почте."
            )
    else:
        logger.error("Файл чек-листа не найден по пути %s", CHECKLIST_PATH)
        await update.message.reply_text(
            "Файл чек-листа временно недоступен. Мы отправим его вам позже по электронной почте."
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Опрос прерван. Если захотите начать заново — нажмите «Получить чек-лист».",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(text="Получить чек-лист")]], resize_keyboard=True
        ),
    )
    return ConversationHandler.END


def main() -> None:
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN отсутствует. Заполни его в файле .env")

    app = Application.builder().token(TOKEN).build()

    conversation_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Получить чек-лист$"), start_questionnaire)],
        states={
            ASK_FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_role)],
            ASK_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_consent)],
            CONFIRM_CONSENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("privacy", show_privacy))
    app.add_handler(CommandHandler("revoke", revoke_consent))
    app.add_handler(conversation_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
