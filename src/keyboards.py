from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# ── Main menu ────────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Чек-ин", callback_data="checkin"),
            InlineKeyboardButton(text="⚔️ Квесты", callback_data="quests"),
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
            InlineKeyboardButton(text="🗺 Роадмап", callback_data="roadmap"),
        ],
        [
            InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask"),
        ],
    ])


# ── Gender picker ────────────────────────────────────────────────────────────

def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Мужской", callback_data="gender_male"),
            InlineKeyboardButton(text="Женский", callback_data="gender_female"),
        ]
    ])


# ── Activity level ───────────────────────────────────────────────────────────

def activity_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сидячий (офис)", callback_data="act_sedentary")],
        [InlineKeyboardButton(text="Лёгкая (1-3 тренировки/нед)", callback_data="act_light")],
        [InlineKeyboardButton(text="Умеренная (3-5 тренировок/нед)", callback_data="act_moderate")],
        [InlineKeyboardButton(text="Высокая (6-7 тренировок/нед)", callback_data="act_high")],
    ])


# ── Numeric scale 1-5 ───────────────────────────────────────────────────────

def scale_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}_{i}") for i in range(1, 6)]
    ])


# ── Quest actions ────────────────────────────────────────────────────────────

def quest_actions(quest_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"quest_done_{quest_id}"),
            InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"quest_skip_{quest_id}"),
        ],
        [InlineKeyboardButton(text="🔍 Подробнее", callback_data=f"quest_info_{quest_id}")],
    ])


# ── Skip weight in check-in ─────────────────────────────────────────────────

def skip_weight_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="checkin_skip_weight")]
    ])


# ── Skip note in check-in ──────────────────────────────────────────────

def skip_note_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="checkin_skip_note")]
    ])


# ── Yes / No ─────────────────────────────────────────────────────────────────

def yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data=f"{prefix}_yes"),
            InlineKeyboardButton(text="Нет", callback_data=f"{prefix}_no"),
        ]
    ])
