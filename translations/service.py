"""Translation helper `t(key, lang, **kwargs)`."""

from __future__ import annotations

from translations.catalog import MESSAGES


def t(key: str, lang: str, **kwargs) -> str:
    lang = (lang or "ru").lower()
    block = MESSAGES.get(key)
    if isinstance(block, dict):
        text = block.get(lang) or block.get("ru")
        if text is None:
            text = key
    elif isinstance(block, str):
        text = block
    else:
        text = key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return str(text)
    return str(text)
