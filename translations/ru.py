"""Russian strings: convenience re-export. Full catalog: `translations/catalog.py`."""

from translations.service import t as t_ru


def t(key: str, **kwargs) -> str:
    return t_ru(key, "ru", **kwargs)
