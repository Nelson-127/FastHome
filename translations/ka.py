"""Georgian strings: convenience re-export."""

from translations.service import t as t_ka


def t(key: str, **kwargs) -> str:
    return t_ka(key, "ka", **kwargs)
