"""Kernel-owned Uvicorn task; no additional event loop or signal owner."""

import asyncio
from contextlib import contextmanager, suppress
from collections.abc import Iterator

import uvicorn

from stevie.api.app import create_app
from stevie.identifiers import ServiceName
from stevie.kernel import StevieKernel


class KernelServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        # Uvicorn 0.50 uses this hook in serve(); the kernel owns process signals.
        yield


class APIServerService:
    name = ServiceName.API_SERVER

    def __init__(self, kernel: StevieKernel, host: str, port: int) -> None:
        self.kernel = kernel
        self.server = KernelServer(uvicorn.Config(
            create_app(kernel), host=host, port=port, access_log=False,
            timeout_graceful_shutdown=10,
        ))
        self._task: asyncio.Task[None] | None = None

    async def _serve(self) -> None:
        try:
            await self.server.serve()
        except (Exception, SystemExit):
            # Uvicorn uses SystemExit for bind/startup failures. Let the kernel
            # handle these as ordinary service failures without leaking state.
            raise RuntimeError("API server failed") from None
        finally:
            if self.server.started and not self.server.should_exit:
                self.kernel.request_stop()

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("API server already started")
        self._task = asyncio.create_task(self._serve(), name="stevie-api")
        try:
            async with asyncio.timeout(10):
                while not self.server.started:
                    if self._task.done():
                        await self._task
                        raise RuntimeError("API server exited before startup")
                    await asyncio.sleep(0.01)
                if self._task.done():
                    await self._task
                    raise RuntimeError("API server exited during startup")
        except BaseException:
            with suppress(Exception):
                await self.stop()
            raise

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self.server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=15)
        finally:
            self._task = None
