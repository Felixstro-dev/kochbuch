from __future__ import annotations

import hashlib
import html
import re
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.providers.base import Step

_CHEFKOCH_RECIPE_RE = re.compile(r"/rezepte/(\d+)/")
_CHEFKOCH_URL_RE = re.compile(r"^(?:https?://)?(?:www\.)?chefkoch\.de/", re.IGNORECASE)
_TIME_RE = re.compile(
    r"(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*"
    r"(?:(?:-|–|bis)\s*(\d{1,3}(?:[.,]\d+)?)\s*)?"
    r"(min(?:uten)?|std(?:unden)?|stunden?|h|sek(?:unden)?|s)\b",
    re.IGNORECASE,
)
_NUMBERED_STEP_RE = re.compile(r"(?m)^\s*(?:\d{1,2}[.)]|Schritt\s+\d+)\s*")


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = parts.hostname.lower() if parts.hostname else ""
    port = parts.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, path, query, ""))


def is_chefkoch_url(url: str) -> bool:
    try:
        host = (urlsplit(url if "://" in url else f"https://{url}").hostname or "").lower()
    except ValueError:
        return False
    if host != "chefkoch.de" and not host.endswith(".chefkoch.de"):
        return False
    return bool(_CHEFKOCH_RECIPE_RE.search(url))


def chefkoch_id_from_url(url: str) -> str | None:
    match = _CHEFKOCH_RECIPE_RE.search(url)
    return match.group(1) if match else None


def chefkoch_recipe_url(recipe_id: str, slug: str = "") -> str:
    suffix = f"/{slug}" if slug else "/"
    return f"https://www.chefkoch.de/rezepte/{recipe_id}{suffix}"


def web_cache_key(url: str) -> str:
    normalized = normalize_url(url)
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:20]
    return f"web:{digest}"


def canonical_cache_key(source: str, external_id: str) -> str:
    if source == "web":
        return web_cache_key(external_id)
    return f"{source}:{external_id}"


def source_label(source: str) -> str:
    return {
        "chefkoch": "Chefkoch",
        "web": "Web",
        "local": "Eigene",
    }.get(source, source.title())


def parse_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    text = str(value).strip()
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def parse_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def parse_servings(value: object) -> int | None:
    parsed = parse_int(value)
    if parsed and 0 < parsed <= 100:
        return parsed
    return None


def parse_iso_duration(value: object) -> int | None:
    if not value:
        return None
    text = str(value).strip()
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return parse_int(text)
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total = int(timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds).total_seconds())
    return total // 60 if total >= 60 else (1 if total > 0 else 0)


def _flatten_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(part for part in (_flatten_text(item) for item in value) if part)
    if isinstance(value, dict):
        return _flatten_text(value.get("text") or value.get("name") or "")
    return ""


def split_steps(instructions: object) -> list[Step]:
    if instructions is None:
        return []
    if isinstance(instructions, list):
        raw_parts: list[str] = []
        for item in instructions:
            if isinstance(item, str):
                raw_parts.append(item)
            elif isinstance(item, dict):
                text = _flatten_text(item.get("text") or item.get("name") or "")
                if text:
                    raw_parts.append(text)
                for child in item.get("itemListElement") or []:
                    if isinstance(child, dict):
                        child_text = _flatten_text(child.get("text"))
                        if child_text:
                            raw_parts.append(child_text)
        raw = "\n\n".join(raw_parts)
    else:
        raw = str(instructions)

    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    raw = html.unescape(raw).strip()
    if not raw:
        return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n+", raw) if block.strip()]
    parts: list[str] = []
    for block in blocks:
        numbered = _NUMBERED_STEP_RE.split(block)
        if len([item for item in numbered if item.strip()]) > 1:
            parts.extend(item.strip() for item in numbered if item.strip())
        elif len(blocks) == 1 and "\n" in block and not _NUMBERED_STEP_RE.search(block):
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if len(lines) > 1:
                parts.extend(lines)
            else:
                parts.append(block)
        else:
            parts.append(block)
    if not parts:
        parts = [raw]

    steps: list[Step] = []
    for part in parts:
        cleaned = _NUMBERED_STEP_RE.sub("", part).strip()
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        if cleaned:
            steps.append(Step(text=cleaned, timer_seconds=detect_timer(cleaned)))
    return steps


def detect_timer(text: str) -> int | None:
    match = _TIME_RE.search(text)
    if not match:
        return None
    first = float(match.group(1).replace(",", "."))
    second = float(match.group(2).replace(",", ".")) if match.group(2) else first
    amount = max(first, second)
    unit = match.group(3).lower()
    if unit.startswith(("h", "std", "stunde")):
        seconds = amount * 3600
    elif unit.startswith(("s", "sek")):
        seconds = amount
    else:
        seconds = amount * 60
    seconds_int = int(round(seconds))
    return seconds_int if 5 <= seconds_int <= 24 * 3600 else None


def image_from_template(template: object, size: str = "crop-480x360") -> str | None:
    if not template:
        return None
    return str(template).replace("<format>", size)


def absolute_image_url(value: object, base_url: str) -> str | None:
    if not value:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    if not value:
        return None
    return urljoin(base_url, str(value))


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


_UNITS = {
    "g",
    "kg",
    "mg",
    "ml",
    "l",
    "el",
    "tl",
    "stk",
    "stück",
    "stueck",
    "prise",
    "prisen",
    "zehe",
    "zehen",
    "bund",
    "dose",
    "dosen",
    "packung",
    "packungen",
    "päckchen",
    "paeckchen",
    "becher",
    "tasse",
    "tassen",
    "scheibe",
    "scheiben",
    "handvoll",
    "msp",
    "tropfen",
    "würfel",
    "wuerfel",
    "gramm",
    "kilogramm",
    "liter",
    "milliliter",
    "esslöffel",
    "teelöffel",
}
_UNICODE_FRACTIONS = {
    "½": 0.5,
    "¼": 0.25,
    "¾": 0.75,
    "⅓": 1 / 3,
    "⅔": 2 / 3,
    "⅛": 0.125,
}


def parse_amount(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    for char, amount in _UNICODE_FRACTIONS.items():
        text = text.replace(char, f" {amount}")
    match = re.search(r"(\d+)\s+(\d+)\s*/\s*(\d+)", text)
    if match:
        return int(match.group(1)) + int(match.group(2)) / int(match.group(3))
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if match:
        return int(match.group(1)) / int(match.group(2))
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    return float(match.group().replace(",", ".")) if match else None


def parse_ingredient_text(text: str) -> tuple[float | None, str, str]:
    line = clean_text(text)
    match = re.match(
        r"^(\d+(?:[.,]\d+)?\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+(?:[.,]\d+)?|[½¼¾⅓⅔⅛])\s*(.*)$",
        line,
    )
    if not match:
        return None, "", line
    amount = parse_amount(match.group(1))
    rest = match.group(2).strip()
    unit = ""
    if rest:
        first, _, remainder = rest.partition(" ")
        if first.lower().rstrip(".") in _UNITS:
            unit = first.rstrip(".")
            rest = remainder.strip()
    return amount, unit, rest or line
