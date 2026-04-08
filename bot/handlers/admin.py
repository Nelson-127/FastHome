"""Admin Telegram UI (thin) — uses backend REST + Telegram messaging."""

from __future__ import annotations

import logging

from aiogram import F, Router, html
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import admin_api
from bot.keyboards.common import admin_main_keyboard
from core.config import get_settings

logger = logging.getLogger(__name__)

router = Router(name="admin")


class AdminStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_user_msg = State()


def _header() -> str:
    return "🏠 <b>FAST HOME | TBILISI</b>\n━━━━━━━━━━━━━━━━━━━━\n"


@router.callback_query(F.data == "admin:main")
async def admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    settings = get_settings()
    if callback.from_user.id not in settings.admin_id_list:
        return
    await state.clear()
    await callback.message.edit_text(
        _header() + "👨‍💻 <b>Админ</b>\n\nВыберите действие:",
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:search")
async def admin_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    settings = get_settings()
    if callback.from_user.id not in settings.admin_id_list:
        return
    await callback.message.answer("⌨️ Введите ID заявки или фрагмент контакта:")
    await state.set_state(AdminStates.waiting_for_search)
    await callback.answer()


@router.message(AdminStates.waiting_for_search, F.text)
async def admin_search_process(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    if message.from_user.id not in settings.admin_id_list:
        return
    q = message.text.strip()
    await state.clear()
    try:
        rows = await admin_api.admin_list_requests(limit=100)
    except Exception as e:
        await message.answer(f"❌ API ошибка: {html.quote(str(e))}", parse_mode="HTML")
        return
    q_lower = q.lower()
    filtered = []
    for r in rows:
        if q.isdigit() and str(r.get("id")) == q:
            filtered.append(r)
            continue
        contact = str(r.get("contact") or "").lower()
        if q_lower in contact:
            filtered.append(r)
    if not filtered:
        await message.answer("❌ Ничего не найдено.", reply_markup=admin_main_keyboard())
        return
    text = f"🔎 <b>Результаты</b>\n\n"
    kb = []
    for r in filtered[:10]:
        text += f"ID {r['id']} | {html.quote(str(r.get('district','')))} | {r.get('status')}\n"
        kb.append([InlineKeyboardButton(text=f"🔎 #{r['id']}", callback_data=f"admin_view:{r['id']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="admin:main")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")


@router.callback_query(F.data.in_(["admin:all", "admin:unpaid"]))
async def admin_actions(callback: CallbackQuery) -> None:
    settings = get_settings()
    if callback.from_user.id not in settings.admin_id_list:
        return
    action = callback.data.split(":")[1]
    try:
        rows = await admin_api.admin_list_requests(
            limit=20,
            status="waiting_payment" if action == "unpaid" else None,
        )
    except Exception as e:
        await callback.message.answer(f"❌ API: {html.quote(str(e))}", parse_mode="HTML")
        await callback.answer()
        return
    title = "⏳ Ожидают оплаты" if action == "unpaid" else "📋 Последние"
    if not rows:
        await callback.message.edit_text(f"<b>{title}</b>\n\nПусто.", reply_markup=admin_main_keyboard(),
                                         parse_mode="HTML")
        await callback.answer()
        return
    text = f"<b>{title}</b>\n\n"
    kb = []
    for r in rows[:15]:
        text += f"#{r['id']} | {html.quote(str(r.get('district','')))} | {r.get('status')}\n"
        kb.append([InlineKeyboardButton(text=f"🔎 #{r['id']}", callback_data=f"admin_view:{r['id']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="admin:main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_view:"))
async def admin_view_detail(callback: CallbackQuery) -> None:
    settings = get_settings()
    if callback.from_user.id not in settings.admin_id_list:
        return
    rid = int(callback.data.split(":")[1])
    try:
        req = await admin_api.admin_get_request(rid)
        matches = await admin_api.admin_get_matches(rid, limit=5)
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
        return
    detail = (
        f"📝 <b>Заявка #{req['id']}</b>\n"
        f"TG: <code>{req.get('telegram_id')}</code>\n"
        f"📞 {html.quote(str(req.get('contact')))}\n"
        f"📍 {html.quote(str(req.get('district')))}\n"
        f"💰 {req.get('budget')} | 🏠 {req.get('rooms')}\n"
        f"💳 {req.get('status')}\n"
    )
    if matches:
        detail += "\n<b>Топ совпадений:</b>\n"
        for m in matches:
            detail += f"• {m.get('price')} — <a href=\"{m.get('url')}\">link</a>\n"
    kb = []
    if req.get("status") == "waiting_payment":
        kb.append(
            [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"admin_mark_paid:{rid}")],
        )
    kb.extend(
        [
            [InlineKeyboardButton(text="✍️ Написать", callback_data=f"admin_msg_prepare:{req.get('telegram_id')}")],
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="admin:main")],
        ]
    )
    await callback.message.answer(detail, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_mark_paid:"))
async def admin_mark_paid(callback: CallbackQuery) -> None:
    settings = get_settings()
    if callback.from_user.id not in settings.admin_id_list:
        return
    rid = int(callback.data.split(":")[1])
    try:
        await admin_api.admin_patch_request(rid, {"status": "paid"})
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
        return
    await callback.answer("Оплата подтверждена")
    await callback.message.answer("✅ Заявка помечена как оплаченная; пользователь получит уведомление.")


@router.callback_query(F.data.startswith("admin_msg_prepare:"))
async def admin_msg_prepare(callback: CallbackQuery, state: FSMContext) -> None:
    settings = get_settings()
    if callback.from_user.id not in settings.admin_id_list:
        return
    target_id = int(callback.data.split(":")[1])
    await state.update_data(target_user_id=target_id)
    await state.set_state(AdminStates.waiting_for_user_msg)
    await callback.message.answer(f"Введите сообщение для <code>{target_id}</code>:", parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_for_user_msg, F.text)
async def admin_msg_send_process(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    if message.from_user.id not in settings.admin_id_list:
        return
    data = await state.get_data()
    target_id = data.get("target_user_id")
    if not target_id:
        return
    try:
        s = get_settings()
        import httpx

        url = f"{s.backend_base_url.rstrip('/')}/admin/messages"
        async with httpx.AsyncClient(timeout=30.0, auth=(s.admin_username, s.admin_password)) as client:
            r = await client.post(url, json={"telegram_id": target_id, "text": message.text})
            r.raise_for_status()
        await message.answer("✅ Отправлено.", reply_markup=admin_main_keyboard())
    except Exception as e:
        await message.answer(f"❌ {html.quote(str(e))}", parse_mode="HTML")
    await state.clear()
