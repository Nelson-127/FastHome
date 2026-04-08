"""Inline keyboards (UI only)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from translations.service import t


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇬🇪 ქართული", callback_data="lang:ka")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")],
        ]
    )


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:search")],
            [InlineKeyboardButton(text="📊 Последние 10", callback_data="admin:all")],
            [InlineKeyboardButton(text="⏳ Ожидают оплаты", callback_data="admin:unpaid")],
            [InlineKeyboardButton(text="🔄 Меню", callback_data="admin:main")],
        ]
    )


def district_keyboard(lang: str) -> InlineKeyboardMarkup:
    keys = [
        "dist_Vake",
        "dist_Saburtalo",
        "dist_Didube",
        "dist_Isani",
        "dist_Mtatsminda",
        "dist_Other",
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(k, lang), callback_data=f"district:{k}")] for k in keys
        ]
    )


def term_keyboard(lang: str) -> InlineKeyboardMarkup:
    keys = {"1-3": "term_1_3", "6": "term_6", "12": "term_12"}
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(v, lang), callback_data=f"term:{k}")] for k, v in keys.items()
        ]
    )


def urgency_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("urg_urgent", lang), callback_data="urgency:urgent")],
            [InlineKeyboardButton(text=t("urg_normal", lang), callback_data="urgency:normal")],
        ]
    )


def confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_confirm", lang), callback_data="confirm:yes")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="confirm:no")],
        ]
    )
