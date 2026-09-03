from typing import List, Dict

# --- Верхние ящики (6 шт) с картинками ---
UPPER_TYPES: List[Dict[str, str]] = [
    {"id": "upper_1", "text": "🖼️ Верхний распашной 1", "image": "app/images/upper_1.jpg"},
    {"id": "upper_2", "text": "🖼️ Верхний распашной 2", "image": "app/images/upper_2.jpg"},
    {"id": "upper_3", "text": "🖼️ Верхний гориз. откр.2", "image": "app/images/upper_3.jpg"},
    {"id": "upper_4", "text": "🖼️ Верхний складной", "image": "app/images/upper_4.jpg"},
    {"id": "upper_5", "text": "🖼️ Верхний угловой", "image": "app/images/upper_5.jpg"},
    {"id": "upper_6", "text": "🖼️ Верхний вытяжка", "image": "app/images/upper_6.jpg"},
]

# --- Нижние ящики (8 шт) с картинками ---
LOWER_TYPES: List[Dict[str, str]] = [
    {"id": "lower_1", "text": "🖼️ Нижний распашной", "image": "app/images/lower_1.jpg"},
    {"id": "lower_2", "text": "🖼️ Нижний распашной 2дв", "image": "app/images/lower_2.jpg"},
    {"id": "lower_3", "text": "🖼️ Нижний выдвижной 2 ящ", "image": "app/images/lower_3.jpg"},
    {"id": "lower_4", "text": "🖼️ Нижний выдвижной 3 ящ", "image": "app/images/lower_4.jpg"},
    {"id": "lower_5", "text": "🖼️ Нижний выдвижной 4 ящ", "image": "app/images/lower_5.jpg"},
    {"id": "lower_6", "text": "🖼️ Нижний угловой", "image": "app/images/lower_6.jpg"},
    {"id": "lower_7", "text": "🖼️ Нижний Карго", "image": "app/images/lower_7.jpg"},
    {"id": "lower_8", "text": "🖼️ Нижний духовой", "image": "app/images/lower_8.jpg"},
]

# --- Пеналы (3 шт) с картинками ---
PANTRY_TYPES: List[Dict[str, str]] = [
    {"id": "pantry_1", "text": "🖼️ Пенал с полками", "image": "app/images/pantry_1.jpg"},
    {"id": "pantry_2", "text": "🖼️ Пенал Духовка/микров-ка", "image": "app/images/pantry_2.jpg"},
    {"id": "pantry_3", "text": "🖼️ Пенал Холодильник", "image": "app/images/pantry_3.jpg"},
]

# --- Шкаф (3 каркаса) с картинками ---
WARDROBE_FRAMES: List[Dict[str, str]] = [
    {"id": "standard", "text": "Ширина до 800мм", "image": "app/images/standard.jpg"},
    {"id": "compact", "text": "Ширина до 1500мм", "image": "app/images/compact.jpg"},
    {"id": "extended", "text": "ширина до 2500мм", "image": "app/images/extended.jpg"},
]