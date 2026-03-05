"""Entry point for the Ritm Telegram bot."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.database import create_engine, create_session_maker, init_db
from src.handlers import router
from src.llm import LLM
from src.rag import KnowledgeBase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _make_session_middleware(session_maker):
    """Middleware that injects an AsyncSession into every handler."""
    from aiogram import BaseMiddleware
    from typing import Any, Awaitable, Callable, Dict

    class DbSessionMiddleware(BaseMiddleware):
        async def __call__(
            self,
            handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
            event: Any,
            data: Dict[str, Any],
        ) -> Any:
            async with session_maker() as session:
                data["session"] = session
                return await handler(event, data)

    return DbSessionMiddleware()


def _make_deps_middleware(llm: LLM, kb: KnowledgeBase):
    """Middleware that injects LLM and KnowledgeBase into handlers."""
    from aiogram import BaseMiddleware
    from typing import Any, Awaitable, Callable, Dict

    class DepsMiddleware(BaseMiddleware):
        async def __call__(
            self,
            handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
            event: Any,
            data: Dict[str, Any],
        ) -> Any:
            data["llm"] = llm
            data["kb"] = kb
            return await handler(event, data)

    return DepsMiddleware()


async def main():
    settings = Settings()

    engine = await create_engine(settings.database_url)
    await init_db(engine)
    session_maker = await create_session_maker(engine)

    logger.info("Loading LLM …")
    llm = LLM(
        model_path=settings.model_path,
        n_ctx=settings.model_n_ctx,
        n_threads=settings.model_n_threads,
        n_gpu_layers=settings.model_n_gpu_layers,
    )

    kb = KnowledgeBase(persist_dir=settings.kb_dir)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(router)

    db_mw = _make_session_middleware(session_maker)
    deps_mw = _make_deps_middleware(llm, kb)
    router.message.middleware(db_mw)
    router.message.middleware(deps_mw)
    router.callback_query.middleware(db_mw)
    router.callback_query.middleware(deps_mw)

    logger.info("Bot starting …")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
