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

ASK_FULL_NAME, ASK_ROLE, ASK_PHONE, CONFIRM_CONSENT = range(4)

ROLE_OPTIONS = [
    "Руководитель",
    "Собственник бизнеса",
    "Индивидуальный предприниматель",
    "Физическое лицо",
]

CONSENT_ACCEPT = "✅ Даю согласие"
CONSENT_DECLINE = "❌ Не даю согласие"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и информация об обработке персональных данных."""

    keyboard = [[KeyboardButton(text="📄 Получить чек-лист")]]
    welcome_text = dedent(
        """
        👋 Добро пожаловать! Этот бот поможет вам получить чек-лист по подготовке бизнеса.

        Нажимая кнопку «📄 Получить чек-лист», вы инициируете передачу своих персональных данных для связи и отправки материала. Передача данных осуществляется в соответствии с Федеральным законом № 152-ФЗ «О персональных данных».

        Политика ПДн: /policy • Данные запрошу только после согласия.
        """
    ).strip()

    await update.message.reply_text(
        welcome_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


async def show_policy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет текст политики обработки персональных данных."""

    policy_text = dedent(
        """
        ℹ️ Политика обработки персональных данных

        1. Оператор: Индивидуальный предприниматель Иванов Илья Сергеевич, ИНН 000000000000. Контакт для обращений: privacy@example.ru.

        2. Персональные данные: фамилия и имя, статус, номер телефона, а также идентификатор и username в Telegram.

        3. Цели обработки: отправка чек-листа, обратная связь по запросу и информирование о продуктах и услугах оператора.

        4. Действия с данными: сбор, запись, систематизация, накопление, хранение, уточнение, использование, передача (в том числе сервисам рассылок, расположенным на территории РФ), обезличивание и уничтожение.

        5. Правовые основания: статья 6 Федерального закона № 152-ФЗ «О персональных данных», статья 18 Федерального закона № 38-ФЗ «О рекламе», а также ваше добровольное согласие.

        6. Срок обработки: до достижения указанных целей или до отзыва согласия.

        7. Права субъекта: вы можете запросить доступ, актуализацию, блокирование или удаление данных, а также отозвать согласие.

        8. Контакты: privacy@example.ru или команда /revoke для отзыва согласия.
        """
    ).strip()

    await update.message.reply_text(policy_text, reply_markup=ReplyKeyboardRemove())


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
        "Пожалуйста, укажите вашу фамилию и имя.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_FULL_NAME


async def ask_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.text.strip()
    if len(full_name.split()) < 2:
        await update.message.reply_text(
            "Пожалуйста, введите фамилию и имя полностью, например: Иванов Иван."
        )
        return ASK_FULL_NAME

    context.user_data["full_name"] = full_name
    keyboard = [[KeyboardButton(text=option)] for option in ROLE_OPTIONS]
    await update.message.reply_text(
        "Уточните, в каком статусе вы обращаетесь:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
    )
    return ASK_ROLE


def _phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    role = update.message.text.strip()
    context.user_data["role"] = role
    await update.message.reply_text(
        "Отправьте, пожалуйста, номер телефона кнопкой ниже.",
        reply_markup=_phone_keyboard(),
    )
    return ASK_PHONE


def _normalize_phone_number(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return phone

    if digits.startswith("8"):
        digits = "7" + digits[1:]

    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits}"

    if phone.startswith("+"):
        return phone

    return f"+{digits}" if digits else phone


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.message.contact
    if not contact or not contact.phone_number:
        await update.message.reply_text(
            "Не удалось получить номер телефона. Пожалуйста, воспользуйтесь кнопкой ниже.",
            reply_markup=_phone_keyboard(),
        )
        return ASK_PHONE

    normalized_phone = _normalize_phone_number(contact.phone_number)
    context.user_data["phone"] = normalized_phone

    return await ask_consent(update, context)


async def request_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Пожалуйста, отправьте номер телефона, нажав на кнопку ниже.",
        reply_markup=_phone_keyboard(),
    )
    return ASK_PHONE


async def ask_consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    consent_text = dedent(
        f"""
        Для завершения оформления необходимо ваше согласие на обработку персональных данных.

        Подтверждая согласие, вы разрешаете оператору (ИП Иванов Илья Сергеевич, ИНН 000000000000) обрабатывать указанные вами данные: фамилию и имя, статус, номер телефона, а также идентификатор и username в Telegram. Цель обработки — отправка чек-листа, обратная связь и направление информации о продуктах и услугах. Обработка включает сбор, запись, систематизацию, накопление, хранение, уточнение, использование, передачу (в том числе с использованием сервисов рассылок, расположенных на территории РФ), обезличивание и уничтожение данных.

        Политика обработки персональных данных: /policy.

        Согласие действует до достижения целей обработки или до вашего отзыва. Вы можете отозвать его в любой момент, отправив запрос на privacy@example.ru или используя команду /revoke.

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
    if choice == CONSENT_DECLINE:
        await update.message.reply_text(
            "Вы отказались от обработки персональных данных. Чек-лист не будет отправлен. Если передумаете — нажмите «📄 Получить чек-лист».",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(text="📄 Получить чек-лист")]], resize_keyboard=True
            ),
        )
        context.user_data.clear()
        return ConversationHandler.END

    if choice != CONSENT_ACCEPT:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки ниже для выбора.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(text=CONSENT_ACCEPT)], [KeyboardButton(text=CONSENT_DECLINE)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return CONFIRM_CONSENT

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
        "Спасибо! Ниже прикреплён чек-лист.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(text="📄 Получить чек-лист")]], resize_keyboard=True
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
        "Опрос прерван. Если захотите начать заново — нажмите «📄 Получить чек-лист».",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(text="📄 Получить чек-лист")]], resize_keyboard=True
        ),
    )
    return ConversationHandler.END


def main() -> None:
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN отсутствует. Заполни его в файле .env")

    app = Application.builder().token(TOKEN).build()

    conversation_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^📄 Получить чек-лист$"), start_questionnaire)],
        states={
            ASK_FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_role)],
            ASK_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, handle_contact),
                MessageHandler(filters.TEXT & ~filters.COMMAND, request_contact),
            ],
            CONFIRM_CONSENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("policy", show_policy))
    app.add_handler(CommandHandler("revoke", revoke_consent))
    app.add_handler(conversation_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
