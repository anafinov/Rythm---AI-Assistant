import asyncio
import logging
import threading

from llama_cpp import Llama

logger = logging.getLogger(__name__)


class LLM:
    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_threads: int = 4,
        n_gpu_layers: int = 0,
    ):
        logger.info("Loading model from %s …", model_path)
        self._lock = threading.Lock()
        self.model = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
        logger.info("Model loaded successfully")

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_generate, prompt, system, max_tokens, temperature
        )

    def _sync_generate(
        self, prompt: str, system: str | None, max_tokens: int, temperature: float
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        with self._lock:
            output = self.model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return output["choices"][0]["message"]["content"]
