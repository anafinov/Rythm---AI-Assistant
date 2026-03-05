from aiogram.fsm.state import State, StatesGroup


class OnboardingState(StatesGroup):
    weight = State()
    height = State()
    age = State()
    gender = State()
    activity = State()
    goal_weight = State()


class CheckInState(StatesGroup):
    weight = State()
    sleep = State()
    stress = State()
    mood = State()
