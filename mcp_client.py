"""Клиент MCP: поднимает сервер Авито отдельным процессом и оборачивает
его инструменты в Tool.

Сервер: npx avito-shopping-mcp (Node-процесс). Общение: JSON-RPC 2.0
через stdio. Настройки сервера читаются из переменных окружения
(AVITO_MCP_STATE_DIR — где лежит сессия после setup).
"""

import asyncio
import os
import threading
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tools.registry import Tool

SERVER_COMMAND = "npx"
SERVER_ARGS = ["-y", "avito-shopping-mcp", "serve"]

STARTUP_TIMEOUT = 120.0   # первый запуск npx может скачивать пакет
CALL_TIMEOUT = 180.0      # сервер ходит на Авито с паузами — вызовы небыстрые

# Пересоздание сессии открывает окно браузера и ждёт, пока человек пройдёт
# капчу, — разрешаем вызов не чаще раза в 10 минут и даём ему больше времени.
SETUP_MIN_INTERVAL_S = 600.0
SETUP_CALL_TIMEOUT = 900.0

# Служебный вывод сервера в консоль не печатаем — он пишется в никуда.
_DEVNULL = open(os.devnull, "w")


class McpClient:
    """Синхронная обёртка над асинхронным MCP-SDK.

    SDK требует свой event loop, а цикл агента синхронный, поэтому клиент
    живёт в отдельном потоке: поток держит loop и соединение, а вызовы
    перекидываются в него через run_coroutine_threadsafe.
    """

    def __init__(self, state_dir: str | None = None, executable_path: str | None = None):
        env = dict(os.environ)
        env.setdefault("npm_config_loglevel", "error")  # глушим «npm notice» npx
        state_dir = state_dir or os.environ.get("AVITO_MCP_STATE_DIR")
        executable_path = executable_path or os.environ.get("AVITO_MCP_EXECUTABLE_PATH")
        if state_dir:
            env["AVITO_MCP_STATE_DIR"] = state_dir
        if executable_path:
            env["AVITO_MCP_EXECUTABLE_PATH"] = executable_path
        self._params = StdioServerParameters(
            command=SERVER_COMMAND, args=SERVER_ARGS, env=env
        )
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._tools: list[Tool] = []
        self._session: ClientSession | None = None
        self._last_setup_at = 0.0  # монотонное время последнего пересоздания сессии
        self._thread = threading.Thread(target=self._run, daemon=True, name="mcp-client")

    # ---- запуск ----

    def start(self, timeout: float = STARTUP_TIMEOUT) -> None:
        """Поднимает сервер и ждёт, пока он отдаст список инструментов."""
        self._thread.start()
        if not self._ready.wait(timeout):
            raise RuntimeError(f"MCP-сервер не поднялся за {timeout:.0f} секунд")
        if self._error:
            import traceback
            details = "".join(traceback.format_exception(self._error))
            raise RuntimeError(f"MCP-сервер не запустился:\n{details}")

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self) -> None:
        try:
            async with stdio_client(self._params, errlog=_DEVNULL) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    listed = await session.list_tools()
                    self._tools = [self._wrap(tool) for tool in listed.tools]
                    self._ready.set()
                    await asyncio.Event().wait()  # держим соединение до конца прогона
        except Exception as error:
            self._error = error
            self._ready.set()

    def close(self) -> None:
        """Останавливает фоновый цикл, чтобы процесс агента завершался чисто."""
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    # ---- инструменты ----

    def tools(self) -> list[Tool]:
        return list(self._tools)

    def _wrap(self, tool) -> Tool:
        return Tool(
            name=tool.name,
            description=tool.description or "",
            schema=tool.input_schema or {"type": "object", "properties": {}},
            func=lambda name=tool.name, **kwargs: self.call(name, kwargs),
        )

    # ---- вызовы ----

    def call(self, name: str, arguments: dict) -> str:
        """Синхронный вызов инструмента сервера. Результат — строка для role=tool.

        Сами не ретраим: каждый повтор — это лишние запросы к Авито, из-за
        которых IP ловит 429. Пересоздание сессии ограничено по частоте —
        модель не может гонять setup по кругу.
        """
        if self._error or self._session is None:
            return f"ОШИБКА MCP: сервер недоступен ({self._error})"
        if name == "avito_setup_session":
            throttle = self._check_setup_throttle()
            if throttle:
                return throttle
        return self._call_sync(name, arguments)

    def _check_setup_throttle(self) -> str:
        """Разрешает пересоздание сессии не чаще раза в SETUP_MIN_INTERVAL_S."""
        elapsed = time.monotonic() - self._last_setup_at
        if elapsed < SETUP_MIN_INTERVAL_S:
            wait_min = (SETUP_MIN_INTERVAL_S - elapsed) / 60
            return (
                f"ОШИБКА: пересоздание сессии уже запускалось {elapsed / 60:.0f} мин назад. "
                f"Повторный запуск разрешён не раньше чем через {wait_min:.0f} мин. "
                "Не вызывай этот инструмент повторно."
            )
        self._last_setup_at = time.monotonic()
        return ""

    def _call_sync(self, name: str, arguments: dict) -> str:
        timeout = SETUP_CALL_TIMEOUT if name == "avito_setup_session" else CALL_TIMEOUT
        future = asyncio.run_coroutine_threadsafe(self._call(name, arguments), self._loop)
        return future.result(timeout=timeout)

    async def _call(self, name: str, arguments: dict) -> str:
        try:
            result = await self._session.call_tool(name, arguments)
        except Exception as error:
            return f"ОШИБКА MCP при вызове {name}: {error}"
        texts = [
            getattr(block, "text", "")
            for block in result.content
            if getattr(block, "text", None)
        ]
        if result.is_error:
            return "ОШИБКА от сервера Авито: " + "\n".join(texts)
        return "\n".join(texts) if texts else "(пустой результат)"
