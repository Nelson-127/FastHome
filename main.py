import asyncio
import logging
#from datetime import datetime, timedelta
#import pytz

from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.filters import CommandStart#, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
#from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.chat_action import ChatActionSender

from config import BOT_TOKEN, ADMIN_IDS, IBAN_TBC, IBAN_BOG, RECIPIENT_NAME
from database import (
    init_db,
    add_request,
    update_payment_status,
    get_request_by_id,
    get_user_language,
    set_user_language,
    get_all_requests,
    get_unpaid_requests,
    search_requests
)
from translations import t

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_VARIANTS = 5

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router(name="main_router")


# --- Состояния (FSM) ---

class AdminStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_user_msg = State()


class SurveyStates(StatesGroup):
    district = State()
    budget = State()
    rooms = State()
    term = State()
    move_in_date = State()
    contact = State()
    urgency = State()
    confirm = State()
    waiting_for_admin_msg = State()


# --- Красивые декорации и хелперы ---

def get_header():
    """Возвращает заголовок, который будет в каждом сообщении."""
    return "🏠 <b>FAST HOME | TBILISI</b>\n━━━━━━━━━━━━━━━━━━━━\n"


def get_progress_bar(step: int, total: int = 7):
    """Рисует индикатор прогресса [🔵🔵⚪⚪⚪⚪⚪]"""
    filled = "🔵"
    empty = "⚪"
    bar = filled * step + empty * (total - step)
    return f"<code>{bar}</code> (Шаг {step}/{total})\n\n"


async def get_lang(user_id: int, state: FSMContext) -> str:
    """Получает язык пользователя (всегда в нижнем регистре)."""
    data = await state.get_data()
    lang = data.get("lang")
    if not lang:
        lang = await get_user_language(user_id) or "ru"
        await state.update_data(lang=lang)
    return lang.lower()


def _price_and_hours(urgency_key: str) -> tuple[str, float, int]:
    """Возвращает цену и время в зависимости от срочности."""
    is_urgent = "urgent" in urgency_key
    price_text = "79 GEL" if is_urgent else "59 GEL"
    hours = 24 if is_urgent else 48
    return price_text, 79.0 if is_urgent else 59.0, hours


# --- Клавиатуры ---

def language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇬🇪 ქართული", callback_data="lang:ka")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")],
    ])


def admin_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск (ID / @User / Тел)", callback_data="admin:search")],
        [InlineKeyboardButton(text="📊 Последние 10 заявок", callback_data="admin:all")],
        [InlineKeyboardButton(text="⏳ Ожидают оплаты", callback_data="admin:unpaid")],
        [InlineKeyboardButton(text="🔄 Обновить меню", callback_data="admin:main")],
    ])


def district_keyboard(lang: str):
    keys = ["dist_Vake", "dist_Saburtalo", "dist_Didube", "dist_Isani", "dist_Mtatsminda", "dist_Other"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(k, lang), callback_data=f"district:{k}")] for k in keys
    ])


def term_keyboard(lang: str):
    keys = {"1-3": "term_1_3", "6": "term_6", "12": "term_12"}
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(v, lang), callback_data=f"term:{k}")] for k, v in keys.items()
    ])


def urgency_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("urg_urgent", lang), callback_data="urgency:urgent")],
        [InlineKeyboardButton(text=t("urg_normal", lang), callback_data="urgency:normal")],
    ])


def confirm_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_confirm", lang), callback_data="confirm:yes")],
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="confirm:no")],
    ])


# --- АДМИНСКИЕ ОБРАБОТЧИКИ ---

@router.callback_query(F.data == "admin:main")
async def admin_menu(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id not in ADMIN_IDS: return
    if state: await state.clear()
    await callback.message.edit_text(
        get_header() + "👨‍💻 <b>Панель администратора</b>\n\nВыберите действие ниже:",
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin:search")
async def admin_search_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("⌨️ <b>Введите ID, @username или телефон для поиска:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_search)
    await callback.answer()


@router.message(AdminStates.waiting_for_search)
async def admin_search_process(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    query = message.text.strip().replace("@", "")
    rows = await search_requests(query)
    await state.clear()

    if not rows:
        await message.answer("❌ Ничего не найдено.", reply_markup=admin_main_keyboard())
        return

    text = f"🔎 <b>Результаты поиска '{html.quote(query)}':</b>\n\n"
    kb = []
    for r in rows:
        req = dict(r)
        status = "✅" if req['payment_status'] == 'paid' else "⏳"
        text += f"{status} ID: {req['id']} | @{html.quote(req['username'] or '—')}\n"
        kb.append([InlineKeyboardButton(text=f"🔎 Детали #{req['id']}", callback_data=f"admin_view:{req['id']}")])

    kb.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="admin:main")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:"))
async def admin_actions(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    action = callback.data.split(":")[1]

    if action == "all":
        rows = await get_all_requests(10)
        title = "📋 Последние 10 заявок"
    elif action == "unpaid":
        rows = await get_unpaid_requests()
        title = "⏳ Ожидают оплаты"
    else:
        return

    if not rows:
        await callback.message.edit_text(f"<b>{title}</b>\n\nПусто.", reply_markup=admin_main_keyboard(),
                                         parse_mode="HTML")
        return

    text = f"<b>{title}:</b>\n\n"
    kb = []
    for r in rows:
        req = dict(r)
        status = "✅" if req['payment_status'] == 'paid' else "⏳"
        # Экранируем данные из БД для безопасности
        dist_safe = html.quote(str(req['district']))
        text += f"{status} ID: {req['id']} | {dist_safe} | {req['budget']} GEL\n"
        kb.append([InlineKeyboardButton(text=f"🔎 Детали #{req['id']}", callback_data=f"admin_view:{req['id']}")])

    kb.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="admin:main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_view:"))
async def admin_view_detail(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return

    # Определяем, пришло ли это из списка или из уведомления
    # Если в callback.data есть пометка "new", отправим новое сообщение
    data_parts = callback.data.split(":")
    req_id = int(data_parts[1])
    is_new_msg = len(data_parts) > 2 and data_parts[2] == "new"

    row = await get_request_by_id(req_id)
    if not row:
        await callback.answer("Заявка не найдена")
        return
    req = dict(row)

    detail = (
        f"📝 <b>Заявка #{req['id']}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Клиент: @{html.quote(req.get('username') or '—')}\n"
        f"🆔 ID пользователя: <code>{req['user_id']}</code>\n"
        f"📞 Контакт: {html.quote(str(req['contact']))}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Район: {html.quote(str(req['district']))}\n"
        f"💰 Бюджет: {req['budget']} GEL\n"
        f"🏠 Комнат: {req['rooms']} | Срок: {req['term']}\n"
        f"🔑 Заезд: {req['move_in_date']}\n"
        f"⚡ Срочность: {req['urgency']}\n"
        f"💳 Статус: <b>{req['payment_status']}</b>\n"
        f"🌐 Язык: {req['language']}\n"
    )

    kb = []
    # Кнопка подтверждения оплаты
    if req['payment_status'] != 'paid':
        kb.append([InlineKeyboardButton(text="✅ Подтвердить оплату",
                                        callback_data=f"admin_paid:{req['id']}:{req['language']}")])

    # Кнопка ответа (теперь она всегда тут под рукой)
    kb.append([InlineKeyboardButton(text="✍️ Написать / Ответить", callback_data=f"admin_msg_prepare:{req['user_id']}")])

    # Кнопка назад
    kb.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin:main")])

    markup = InlineKeyboardMarkup(inline_keyboard=kb)

    if is_new_msg:
        # Если это из уведомления — шлем новым сообщением, чтобы не затереть вопрос
        await callback.message.answer(detail, reply_markup=markup, parse_mode="HTML")
        await callback.answer()
    else:
        # Если из списка — редактируем текущее
        await callback.message.edit_text(detail, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_msg_prepare:"))
async def admin_msg_prepare(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    target_id = int(callback.data.split(":")[1])

    await state.update_data(target_user_id=target_id)
    await state.set_state(AdminStates.waiting_for_user_msg)

    user_lang = await get_user_language(target_id) or "ru"

    await callback.message.answer(
        get_header() + t("admin_msg_instruction", "ru") + f"\n\nClient ID: <code>{target_id}</code>\nЯзык: {user_lang}",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_user_msg)
async def admin_msg_send_process(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return

    data = await state.get_data()
    target_id = data.get("target_user_id")
    if not target_id: return

    user_lang = await get_user_language(target_id) or "ru"

    try:
        header = t("admin_msg_header", user_lang)
        # Имитируем печатание
        async with ChatActionSender.typing(bot=bot, chat_id=target_id):
            await bot.send_message(target_id, f"{header}{message.text}", parse_mode="HTML")

        await message.answer("✅ Сообщение успешно доставлено!", reply_markup=admin_main_keyboard())
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")

    await state.clear()


@router.callback_query(F.data.startswith("admin_paid:"))
async def admin_confirm_paid(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return

    parts = callback.data.split(":")
    rid = int(parts[1])
    lang = parts[2]

    await update_payment_status(rid, "paid")
    req = await get_request_by_id(rid)

    if req:
        # Уведомляем пользователя
        _, _, hours = _price_and_hours(req['urgency'])
        success_msg = t("user_paid_success", lang, max_v=MAX_VARIANTS, hours=hours)
        try:
            await bot.send_message(req['user_id'], success_msg)
        except:
            pass

    await callback.answer("Оплата подтверждена")
    await callback.message.edit_text(callback.message.text + "\n\n✅ <b>ОПЛАЧЕНО</b>", parse_mode="HTML")


# --- ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ (ОПРОС) ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    if message.from_user.id in ADMIN_IDS:
        await message.answer(
            get_header() + "👨‍💻 <b>Панель администратора</b>",
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML"
        )
        return

    # Вступление для обычного пользователя (MVP: говорим сразу, что платно)
    await message.answer(
        get_header() + t("welcome_intro", "en"),
        reply_markup=language_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split(":")[1]
    await set_user_language(callback.from_user.id, lang)
    await state.update_data(lang=lang)
    await callback.answer()

    text = get_header() + t("start_text", lang, max_v=MAX_VARIANTS)

    await callback.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 " + t("find_apartment", lang), callback_data="start_survey")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "start_survey")
async def start_survey(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id, state)
    await state.set_state(SurveyStates.district)

    text = get_header() + get_progress_bar(1) + t("choose_district", lang)
    await callback.message.edit_text(text, reply_markup=district_keyboard(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("district:"), SurveyStates.district)
async def set_district(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id, state)
    dist_key = callback.data.split(":")[1]

    if dist_key == "dist_Other":
        await callback.message.answer(t("write_other_district", lang))
        await state.update_data(wait_other_district=True)
        return

    await state.update_data(district=t(dist_key, lang))
    await state.set_state(SurveyStates.budget)

    text = get_header() + get_progress_bar(2) + t("enter_budget", lang)
    await callback.message.edit_text(text, parse_mode="HTML")


@router.message(SurveyStates.district, F.text)
async def set_district_other(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id, state)
    data = await state.get_data()
    if not data.get("wait_other_district"): return

    await state.update_data(district=message.text.strip(), wait_other_district=False)
    await state.set_state(SurveyStates.budget)

    text = get_header() + get_progress_bar(2) + t("enter_budget", lang)
    await message.answer(text, parse_mode="HTML")


@router.message(SurveyStates.budget, F.text)
async def set_budget(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id, state)
    val = message.text.replace(" ", "")
    if not val.isdigit():
        await message.answer(t("error_budget", lang))
        return

    await state.update_data(budget=int(val))
    await state.set_state(SurveyStates.rooms)

    text = get_header() + get_progress_bar(3) + t("enter_rooms", lang)
    await message.answer(text, parse_mode="HTML")


@router.message(SurveyStates.rooms, F.text)
async def set_rooms(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id, state)
    await state.update_data(rooms=message.text.strip())
    await state.set_state(SurveyStates.term)

    text = get_header() + get_progress_bar(4) + t("enter_term", lang)
    await message.answer(text, reply_markup=term_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("term:"), SurveyStates.term)
async def set_term(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id, state)
    term_key = callback.data.split(":")[1]
    term_map = {"1-3": "term_1_3", "6": "term_6", "12": "term_12"}

    await state.update_data(term=t(term_map[term_key], lang))
    await state.set_state(SurveyStates.move_in_date)

    text = get_header() + get_progress_bar(5) + t("enter_move_date", lang)
    await callback.message.edit_text(text, parse_mode="HTML")


@router.message(SurveyStates.move_in_date, F.text)
async def set_move_in(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id, state)
    await state.update_data(move_in_date=message.text.strip())
    await state.set_state(SurveyStates.contact)

    text = get_header() + get_progress_bar(6) + t("enter_contact", lang)
    await message.answer(text, parse_mode="HTML")


@router.message(SurveyStates.contact, F.text)
async def set_contact(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id, state)
    await state.update_data(contact=message.text.strip())
    await state.set_state(SurveyStates.urgency)

    text = get_header() + get_progress_bar(7) + t("urgency_title", lang)
    await message.answer(text, reply_markup=urgency_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("urgency:"), SurveyStates.urgency)
async def set_urgency(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id, state)
    urg_key = callback.data.split(":")[1]
    price_text, _, hours = _price_and_hours(urg_key)
    await state.update_data(urgency=urg_key)
    data = await state.get_data()

    # Сводка данных и оферта (MVP защита)
    summary = (
            get_header() +
            f"<b>{t('confirm_title', lang)}</b>\n\n"
            f"📍 {t('summary_district', lang)}: {html.quote(data['district'])}\n"
            f"💰 {t('summary_budget', lang)}: {data['budget']} GEL\n"
            f"🏠 {t('summary_rooms', lang)}: {html.quote(data['rooms'])}\n"
            f"⚡ {t('summary_urgency', lang)}: {t('summary_hours', lang, h=hours)}\n\n"
            f"{t('conditions_list', lang, max_v=MAX_VARIANTS, hours=hours)}\n\n"
            f"💵 <b>{t('price_label', lang)}: {price_text}</b>"
    )

    await state.set_state(SurveyStates.confirm)
    await callback.message.edit_text(summary, reply_markup=confirm_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data == "confirm:no", SurveyStates.confirm)
async def cancel_confirm(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id, state)
    await state.clear()
    await callback.message.answer(t("order_cancelled", lang))

@router.callback_query(F.data == "confirm:yes", SurveyStates.confirm)
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id, state)
    data = await state.get_data()
    user = callback.from_user
    price, _, _ = _price_and_hours(data['urgency'])

    # 1. Сохраняем заявку в БД
    rid = await add_request(
        user.id, user.username, lang, data['district'], data['budget'],
        data['rooms'], data['term'], data['move_in_date'], data['contact'], data['urgency'], "waiting_payment"
    )

    # 2. Формируем текст сообщения об оплате
    pay_msg = (
            get_header() +
            t("pay_manual_text", lang, price=price, iban_tbc=IBAN_TBC, iban_bog=IBAN_BOG, name=RECIPIENT_NAME)
    )

    # 3. Создаем клавиатуру с ДВУМЯ кнопками
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_i_paid", lang), callback_data=f"paid:{rid}")],
        [InlineKeyboardButton(text=t("btn_contact_admin", lang), callback_data=f"user_msg_admin:{rid}")]
    ])

    # 4. ОТПРАВЛЯЕМ ОДИН РАЗ (это важно!)
    await callback.message.edit_text(pay_msg, reply_markup=kb, parse_mode="HTML")

    # 5. Уведомляем админов о новой заявке
    admin_alert = (
        f"🆕 <b>ЗАЯВКА #{rid}</b>\n"
        f"Юзер: @{html.quote(user.username or '—')}\n"
        f"Цена: {price}\n"
        f"Район: {html.quote(data['district'])}"
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, admin_alert, parse_mode="HTML")
        except:
            pass

    await state.clear()

# Пользователь нажал "Написать администратору"
@router.callback_query(F.data.startswith("user_msg_admin:"))
async def user_msg_admin_start(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id) or "ru"
    rid = callback.data.split(":")[1]

    await state.update_data(active_rid=rid)
    await state.set_state(SurveyStates.waiting_for_admin_msg)

    await callback.message.answer(t("user_msg_instruction", lang))
    await callback.answer()

# Пользователь отправил текст
@router.message(SurveyStates.waiting_for_admin_msg)
async def user_msg_to_admin_process(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "ru"
    data = await state.get_data()
    rid = data.get("active_rid")

    admin_text = (
        f"📩 <b>СООБЩЕНИЕ ОТ КЛИЕНТА</b>\n"
        f"Заявка: #{rid}\n"
        f"Юзер: @{html.quote(message.from_user.username or '—')} (ID: <code>{message.from_user.id}</code>)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 {html.quote(message.text)}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"admin_msg_prepare:{message.from_user.id}")],
        # Добавляем :new в конце callback_data
        [InlineKeyboardButton(text="🔎 Посмотреть анкету", callback_data=f"admin_view:{rid}:new")]
    ])

    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, admin_text, reply_markup=kb, parse_mode="HTML")
        except:
            pass

    await message.answer(t("msg_sent_to_admin", lang))
    await state.clear()

@router.callback_query(F.data.startswith("paid:"))
async def user_paid_click(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id) or "ru"
    await callback.answer()
    await callback.message.answer(t("wait_admin", lang))


# --- ЗАПУСК БОТА ---

async def main():
    await init_db()
    dp.include_router(router)
    logger.info("Bot started and polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Bot stopped!")