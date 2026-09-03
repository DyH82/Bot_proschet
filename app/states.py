from aiogram.fsm.state import State, StatesGroup


class CalcState(StatesGroup):
    """FSM состояния для бота."""

    # Общие
    CHOOSING_TYPE = State()

    # Кухня
    KITCHEN_CATEGORY = State()  # Верх/Низ/Пенал
    KITCHEN_TYPE_SELECT = State()  # Выбор типа из списка
    KITCHEN_ITEM_COUNT = State()  # Ввод количества для конкретного типа
    KITCHEN_EXTRAS = State()  # Допы

    # Шкаф
    WARDROBE_FRAME = State()
    WARDROBE_SHELVES = State()
    WARDROBE_DRAWERS = State()
    WARDROBE_EXTRAS = State()
    WARDROBE_ADD_DETAILS = State()

    # Контакт
    CONTACT_WAITING = State()  # Ожидание ручного ввода номера