"""User survey + payment link (UI only)."""

from __future__ import annotations

import logging

from aiogram import F, Router, html
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import api_client
from bot.keyboards.common import (
    confirm_keyboard,
    district_keyboard,
    language_keyboard,
    term_keyboard,
    urgency_keyboard,
)
from core.config import get_settings
from translations.service import t

logger = logging.getLogger(__name__)

router = Router(name="user")


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


def get_header() -> str:
    return "🏠 <b>FAST HOME | TBILISI</b>\n━━━━━━━━━━━━━━━━━━━━\n"


def get_progress_bar(step: int, total: int = 7) -> str:
    filled = "🔵"
    empty = "⚪"
    bar = filled * step + empty * (total - step)
    return f"<code>{bar}</code> (Шаг {step}/{total})\n\n"


def _price_and_hours(urgency_key: str) -> tuple[str, float, int]:
    is_urgent = "urgent" in urgency_key
    price_text = "79 GEL" if is_urgent else "59 GEL"
    hours = 24 if is_urgent else 48
    return price_text, 79.0 if is_urgent else 59.0, hours


async def get_lang(user_id: int, state: FSMContext) -> str:
    data = await state.get_data()
    lang = data.get("lang")
    if not lang:
        lang = "ru"
        await state.update_data(lang=lang)
    return str(lang).lower()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    settings = get_settings()
    if message.from_user and message.from_user.id in settings.admin_id_list:
        from bot.keyboards.common import admin_main_keyboard

        await message.answer(
            get_header() + "👨‍💻 <b>Админ</b>",
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML",
        )
        return
    await message.answer(
        get_header() + t("welcome_intro", "en"),
        reply_markup=language_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery, state: FSMContext) -> None:
    lang = callback.data.split(":")[1]
    await state.update_data(lang=lang)
    await callback.answer()
    text = get_header() + t("start_text", lang, max_v=5)
    await callback.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🚀 " + t("find_apartment", lang), callback_data="start_survey")]]
        ),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "start_survey")
async def start_survey(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id, state)
    await state.set_state(SurveyStates.district)
    text = get_header() + get_progress_bar(1) + t("choose_district", lang)
    await callback.message.edit_text(text, reply_markup=district_keyboard(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("district:"), SurveyStates.district)
async def set_district(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id, state)
    dist_key = callback.data.split(":")[1]
    if dist_key == "dist_Other":
        await callback.message.answer(t("write_other_district", lang))
        await state.update_data(wait_other_district=True)
        await callback.answer()
        return
    await state.update_data(district=t(dist_key, lang))
    await state.set_state(SurveyStates.budget)
    text = get_header() + get_progress_bar(2) + t("enter_budget", lang)
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(SurveyStates.district, F.text)
async def set_district_other(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id, state)
    data = await state.get_data()
    if not data.get("wait_other_district"):
        return
    await state.update_data(district=message.text.strip(), wait_other_district=False)
    await state.set_state(SurveyStates.budget)
    text = get_header() + get_progress_bar(2) + t("enter_budget", lang)
    await message.answer(text, parse_mode="HTML")


@router.message(SurveyStates.budget, F.text)
async def set_budget(message: Message, state: FSMContext) -> None:
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
async def set_rooms(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id, state)
    await state.update_data(rooms=message.text.strip())
    await state.set_state(SurveyStates.term)
    text = get_header() + get_progress_bar(4) + t("enter_term", lang)
    await message.answer(text, reply_markup=term_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("term:"), SurveyStates.term)
async def set_term(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id, state)
    term_key = callback.data.split(":")[1]
    term_map = {"1-3": "term_1_3", "6": "term_6", "12": "term_12"}
    await state.update_data(term=t(term_map[term_key], lang))
    await state.set_state(SurveyStates.move_in_date)
    text = get_header() + get_progress_bar(5) + t("enter_move_date", lang)
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(SurveyStates.move_in_date, F.text)
async def set_move_in(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id, state)
    await state.update_data(move_in_date=message.text.strip())
    await state.set_state(SurveyStates.contact)
    text = get_header() + get_progress_bar(6) + t("enter_contact", lang)
    await message.answer(text, parse_mode="HTML")


@router.message(SurveyStates.contact, F.text)
async def set_contact(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id, state)
    await state.update_data(contact=message.text.strip())
    await state.set_state(SurveyStates.urgency)
    text = get_header() + get_progress_bar(7) + t("urgency_title", lang)
    await message.answer(text, reply_markup=urgency_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("urgency:"), SurveyStates.urgency)
async def set_urgency(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id, state)
    urg_key = callback.data.split(":")[1]
    price_text, _, hours = _price_and_hours(urg_key)
    await state.update_data(urgency=urg_key)
    data = await state.get_data()
    summary = (
        get_header()
        + f"<b>{t('confirm_title', lang)}</b>\n\n"
        f"📍 {t('summary_district', lang)}: {html.quote(data['district'])}\n"
        f"💰 {t('summary_budget', lang)}: {data['budget']} GEL\n"
        f"🏠 {t('summary_rooms', lang)}: {html.quote(data['rooms'])}\n"
        f"⚡ {t('summary_urgency', lang)}: {t('summary_hours', lang, h=hours)}\n\n"
        f"{t('conditions_list', lang, max_v=5, hours=hours)}\n\n"
        f"💵 <b>{t('price_label', lang)}: {price_text}</b>"
    )
    await state.set_state(SurveyStates.confirm)
    await callback.message.edit_text(summary, reply_markup=confirm_keyboard(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "confirm:no", SurveyStates.confirm)
async def cancel_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id, state)
    await state.clear()
    await callback.message.answer(t("order_cancelled", lang))


@router.callback_query(F.data == "confirm:yes", SurveyStates.confirm)
async def confirm_yes(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id, state)
    data = await state.get_data()
    user = callback.from_user
    price_text, _, _ = _price_and_hours(data["urgency"])

    payload = {
        "telegram_id": user.id,
        "telegram_username": user.username,
        "language": lang,
        "district": data["district"],
        "budget": float(data["budget"]),
        "rooms": data["rooms"],
        "term": data["term"],
        "move_in_date": data["move_in_date"],
        "contact": data["contact"],
        "urgency": data["urgency"],
    }
    try:
        created = await api_client.post_request(payload)
        rid = int(created["id"])
    except Exception as e:
        logger.exception("Backend error")
        await callback.message.answer(t("payment_create_error", lang) + f"\n<code>{html.quote(str(e))}</code>", parse_mode="HTML")
        await state.clear()
        await callback.answer()
        return

    settings = get_settings()
    if settings.tbc_enabled:
        try:
            pay = await api_client.create_payment(rid, user.id)
            approval_url = pay["approval_url"]
        except Exception as e:
            logger.exception("TBC create payment error")
            await callback.message.answer(t("payment_create_error", lang) + f"\n<code>{html.quote(str(e))}</code>", parse_mode="HTML")
            await state.clear()
            await callback.answer()
            return
        pay_msg = get_header() + t("pay_tbc_text", lang, price=price_text)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t("btn_pay_tbc", lang), url=approval_url)],
                [InlineKeyboardButton(text=t("btn_contact_admin", lang), callback_data=f"user_msg_admin:{rid}:{lang}")],
            ]
        )
    else:
        pay_msg = get_header() + t(
            "pay_manual_text",
            lang,
            price=price_text,
            iban_tbc=settings.iban_tbc or "—",
            iban_bog=settings.iban_bog or "—",
            name=settings.recipient_name or "—",
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t("btn_i_paid", lang), callback_data=f"paid_notify:{rid}:{lang}")],
                [InlineKeyboardButton(text=t("btn_contact_admin", lang), callback_data=f"user_msg_admin:{rid}:{lang}")],
            ]
        )
    await callback.message.edit_text(pay_msg, reply_markup=kb, parse_mode="HTML")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("paid_notify:"))
async def user_paid_notify(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    lang = parts[2] if len(parts) > 2 else "ru"
    await callback.answer()
    await callback.message.answer(t("wait_admin", lang))


@router.callback_query(F.data.startswith("user_msg_admin:"))
async def user_msg_admin_start(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    rid = parts[1]
    lang = parts[2] if len(parts) > 2 else await get_lang(callback.from_user.id, state)
    await state.update_data(active_rid=rid, lang=lang)
    await state.set_state(SurveyStates.waiting_for_admin_msg)
    await callback.message.answer(t("user_msg_instruction", lang))
    await callback.answer()


@router.message(SurveyStates.waiting_for_admin_msg, F.text)
async def user_msg_to_admin_process(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id, state)
    data = await state.get_data()
    rid = data.get("active_rid")
    settings = get_settings()
    admin_text = (
        f"📩 <b>СООБЩЕНИЕ ОТ КЛИЕНТА</b>\n"
        f"Заявка: #{rid}\n"
        f"Юзер: @{html.quote(message.from_user.username or '—')} (ID: <code>{message.from_user.id}</code>)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 {html.quote(message.text)}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"admin_msg_prepare:{message.from_user.id}")],
            [InlineKeyboardButton(text="🔎 Анкета", callback_data=f"admin_view:{rid}")],
        ]
    )
    for aid in settings.admin_id_list:
        try:
            await message.bot.send_message(aid, admin_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            logger.exception("Notify admin failed")
    await message.answer(t("msg_sent_to_admin", lang))
    await state.clear()
