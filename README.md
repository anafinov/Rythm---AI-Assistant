# Ритм — Telegram-бот для снижения веса

Персональный AI-помощник на базе мультиагентной системы с локальным инференсом (Qwen 2.5 3B), RAG и геймификацией.

## Возможности

- **Онбординг**: сбор параметров, расчёт BMR/TDEE, формирование «карты маршрута»
- **Ежедневные квесты**: генерируются AI с учётом состояния пользователя (сон, стресс, настроение)
- **Геймификация**: XP, уровни, streak, достижения
- **Адаптивный режим**: при высоком стрессе или плохом сне бот переключается на «мягкий режим»
- **RAG**: ответы на вопросы со ссылками на доказательную базу
- **Кризисная поддержка**: эмпатичные ответы при тяжёлых состояниях

## Мультиагентная система

| Агент | Задача |
|-------|--------|
| **Аналитик** | Обрабатывает чек-ины, формирует JSON-профиль состояния |
| **Методолог** (RAG) | Ищет в базе знаний научное обоснование для рекомендаций |
| **Геймдизайнер** | Генерирует персонализированные квесты на день |

## Технологический стек

- Python 3.12, Aiogram 3, SQLAlchemy (async), Pandas, NumPy
- LangChain + llama-cpp-python (локальный инференс Qwen 2.5 3B GGUF)
- ChromaDB (RAG, векторный поиск)
- PostgreSQL 16, Redis 7
- Docker & Docker Compose

## Быстрый старт

### 1. Клонирование и настройка

```bash
git clone <repo-url> && cd ritm
cp .env.example .env
# Отредактируйте .env: укажите BOT_TOKEN от @BotFather
```

### 2. Скачивание модели

```bash
# Qwen 2.5 3B Instruct, квантизация Q4_K_M (~2 GB)
pip install huggingface-hub
huggingface-cli download Qwen/Qwen2.5-3B-Instruct-GGUF \
    qwen2.5-3b-instruct-q4_k_m.gguf \
    --local-dir models/
```

### 3. Запуск инфраструктуры

```bash
docker compose up -d postgres redis
```

### 4. Создание виртуального окружения и установка зависимостей

```bash
# Создание виртуального окружения
python3 -m venv .venv

# Активация (macOS / Linux)
source .venv/bin/activate

# Активация (Windows PowerShell)
# .venv\Scripts\Activate.ps1

# Установка зависимостей
pip install -r requirements.txt
```

> После активации в терминале появится префикс `(.venv)`.
> Все последующие команды (`python scripts/index_kb.py`, `python -m src.main` и т.д.)
> нужно запускать с активированным окружением.

### 5. Индексация базы знаний

```bash
python scripts/index_kb.py
```

### 6. Запуск бота

```bash
python -m src.main
```

### Запуск через Docker (полностью)

```bash
docker compose up --build
```

## Структура проекта

```
src/
├── main.py          # Точка входа
├── config.py        # Настройки (.env)
├── database.py      # SQLAlchemy модели + init
├── handlers.py      # Все Telegram-хендлеры
├── keyboards.py     # Inline-клавиатуры
├── states.py        # FSM-состояния
├── llm.py           # Обёртка над llama-cpp-python
├── rag.py           # ChromaDB: индексация + поиск
├── agents.py        # 3 агента (analyst, methodologist, game_designer)
├── gamification.py  # XP, уровни, streak, достижения
└── utils.py         # BMR, TDEE, расчёт темпа
```

## Бенчмарк

Запуск замеров потребления ресурсов:

```bash
python scripts/benchmark.py --model models/qwen2.5-3b-instruct-q4_k_m.gguf
```

Выводит: RAM до/после загрузки модели, скорость генерации (tok/s), CPU usage.

## Тесты

```bash
pip install pytest
pytest tests/
```

## Fine-tuning (опционально)

Для дообучения модели на датасете мотивационного консультирования:

1. Подготовьте датасет в формате ChatML (200-300 пар диалогов)
2. Используйте [Unsloth](https://github.com/unslothai/unsloth) + QLoRA на Google Colab (бесплатный T4)
3. Экспортируйте в GGUF и поместите в `models/`
