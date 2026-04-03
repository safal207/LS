# -*- coding: utf-8 -*-
"""
OCR-модуль — извлечение текста из кадра экрана.

Иерархия бэкендов (первый доступный побеждает):
  1. pytesseract  — быстрый, нужен системный tesseract-ocr
  2. easyocr      — тяжелее, но без системных зависимостей (torch уже есть)
  3. fallback     — возвращает "" (агент работает без OCR, не падает)

Использование:
    from perception.ocr import extract_text
    text = extract_text(pil_image_or_numpy_array)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Определяем доступный бэкенд один раз при импорте ─────────────────────────

_BACKEND: str = "none"
_EASY_READER: Any = None


def _probe_backends() -> str:
    global _EASY_READER

    # 1. pytesseract
    try:
        import pytesseract  # noqa: F401
        pytesseract.get_tesseract_version()
        return "pytesseract"
    except Exception:
        pass

    # 2. easyocr (lazy — инициализируем reader только при первом вызове)
    try:
        import easyocr  # noqa: F401
        return "easyocr"
    except Exception:
        pass

    logger.warning(
        "OCR: нет доступных бэкендов (pytesseract, easyocr). "
        "Установи: pip install pytesseract или pip install easyocr. "
        "Агент продолжает работу без чтения экрана."
    )
    return "none"


_BACKEND = _probe_backends()


def _get_easy_reader():
    """Ленивая инициализация EasyOCR Reader (загрузка модели ~первый раз)."""
    global _EASY_READER
    if _EASY_READER is None:
        import easyocr
        _EASY_READER = easyocr.Reader(["ru", "en"], gpu=False, verbose=False)
        logger.info("EasyOCR reader инициализирован (ru+en)")
    return _EASY_READER


# ── Публичный API ─────────────────────────────────────────────────────────────

def extract_text(image: Any, lang: str = "rus+eng") -> str:
    """
    Извлечь текст из PIL Image или numpy array.

    Args:
        image: PIL.Image.Image или np.ndarray (BGR или RGB)
        lang:  язык для pytesseract (игнорируется при easyocr)

    Returns:
        Строка с текстом, очищенная от лишних пробелов.
        Пустая строка если OCR недоступен или текст не найден.
    """
    if _BACKEND == "none":
        return ""

    try:
        if _BACKEND == "pytesseract":
            return _ocr_pytesseract(image, lang)
        if _BACKEND == "easyocr":
            return _ocr_easyocr(image)
    except Exception as exc:
        logger.debug("OCR extract_text failed (%s): %s", _BACKEND, exc)
    return ""


def backend_name() -> str:
    """Вернуть имя активного OCR-бэкенда."""
    return _BACKEND


# ── Бэкенды ───────────────────────────────────────────────────────────────────

def _ocr_pytesseract(image: Any, lang: str) -> str:
    import pytesseract
    from PIL import Image as PILImage
    import numpy as np

    if isinstance(image, np.ndarray):
        # numpy BGR → PIL RGB
        import cv2
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image
        pil = PILImage.fromarray(rgb)
    else:
        pil = image

    # Конфиг: один блок текста, без OSD
    config = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(pil, lang=lang, config=config)
    return _clean(text)


def _ocr_easyocr(image: Any) -> str:
    import numpy as np
    from PIL import Image as PILImage

    reader = _get_easy_reader()

    if isinstance(image, PILImage.Image):
        arr = np.array(image)
    else:
        arr = image

    results = reader.readtext(arr, detail=0, paragraph=True)
    return _clean(" ".join(results))


def _clean(text: str) -> str:
    """Убрать лишние пробелы и пустые строки."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines)
