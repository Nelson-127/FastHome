"""English strings: convenience re-export."""

from translations.service import t as t_en


def t(key: str, **kwargs) -> str:
    return t_en(key, "en", **kwargs)
