import asyncio
import unittest
from dataclasses import dataclass
from typing import Any

from stevie.identifiers import ServiceName, TelemetryMessage
from stevie.kernel import StevieKernel


@dataclass
class FakeService:
    name: str
    operations: list[tuple[str, str]]
    start_error: Exception | None = None
    stop_error: Exception | None = None

    async def start(self) -> None:
        self.operations.append(("start", self.name))
        if self.start_error is not None:
            raise self.start_error

    async def stop(self) -> None:
        self.operations.append(("stop", self.name))
        if self.stop_error is not None:
            raise self.stop_error


class FakeTelemetry:
    def __init__(self) -> None:
        self.messages: list[tuple[TelemetryMessage, dict[str, Any]]] = []

    async def emit(self, message: TelemetryMessage, **context: Any) -> None:
        self.messages.append((message, context))


class StevieKernelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.kernel = StevieKernel()
        self.operations: list[tuple[str, str]] = []
        self.telemetry = FakeTelemetry()
        self.kernel.register(self.telemetry, name=ServiceName.TELEMETRY)
        self.services = [FakeService(name, self.operations) for name in ("A", "B", "C")]
        for service in self.services:
            self.kernel.register(service)

    async def test_start_in_registration_order(self) -> None:
        await self.kernel.start()

        self.assertEqual(self.operations, [("start", "A"), ("start", "B"), ("start", "C")])
        self.assertTrue(self.kernel.running)

    async def test_start_failure_rolls_back_in_reverse_order(self) -> None:
        error = RuntimeError("C failed to start")
        self.services[2].start_error = error

        with self.assertRaises(RuntimeError) as caught:
            await self.kernel.start()

        self.assertIs(caught.exception, error)
        self.assertEqual(self.operations, [
            ("start", "A"), ("start", "B"), ("start", "C"),
            ("stop", "B"), ("stop", "A"),
        ])
        self.assertFalse(self.kernel.running)
        self.assertEqual(self.telemetry.messages[-1], (
            TelemetryMessage.KERNEL_START_FAILED,
            {"source": "kernel", "name": self.kernel.name, "error": str(error)},
        ))

    async def test_stop_in_reverse_order(self) -> None:
        await self.kernel.start()
        self.operations.clear()

        await self.kernel.stop()

        self.assertEqual(self.operations, [("stop", "C"), ("stop", "B"), ("stop", "A")])
        self.assertFalse(self.kernel.running)
        self.assertTrue(self.kernel._stop_event.is_set())

    async def test_stop_failure_does_not_abort_shutdown(self) -> None:
        self.services[1].stop_error = RuntimeError("B failed to stop")
        await self.kernel.start()
        self.operations.clear()
        self.telemetry.messages.clear()

        await self.kernel.stop()

        self.assertEqual(self.operations, [("stop", "C"), ("stop", "B"), ("stop", "A")])
        self.assertFalse(self.kernel.running)
        self.assertTrue(self.kernel._stop_event.is_set())
        self.assertEqual(self.telemetry.messages, self.stop_messages(failed="B"))

    async def test_stop_uses_kernel_telemetry_helper(self) -> None:
        await self.kernel.start()
        self.telemetry.messages.clear()

        await self.kernel.stop()

        self.assertEqual(self.telemetry.messages, self.stop_messages())

    def stop_messages(self, failed: str | None = None) -> list[tuple[TelemetryMessage, dict[str, Any]]]:
        messages = [(
            TelemetryMessage.KERNEL_STOPPING,
            {"source": "kernel", "name": self.kernel.name},
        )]
        for name in ("C", "B", "A"):
            context = {"source": "kernel", "service": name}
            messages.append((TelemetryMessage.KERNEL_SERVICE_STOPPING, context))
            if name == failed:
                messages.append((
                    TelemetryMessage.KERNEL_SERVICE_STOP_FAILED,
                    {**context, "error": f"{name} failed to stop"},
                ))
            else:
                messages.append((TelemetryMessage.KERNEL_SERVICE_STOPPED, context))
        messages.append((
            TelemetryMessage.KERNEL_STOPPED,
            {"source": "kernel", "name": self.kernel.name},
        ))
        return messages

    async def test_registration_and_components_without_lifecycle(self) -> None:
        component = object()
        self.kernel.register(component, name="plain")
        self.assertIs(self.kernel.get("plain"), component)
        self.assertTrue(self.kernel.has("plain"))
        self.assertFalse(self.kernel.has("absent"))
        with self.assertRaises(KeyError):
            self.kernel.get("absent")
        with self.assertRaises(ValueError):
            self.kernel.register(object(), name="plain")
        await self.kernel.start()
        self.assertTrue(self.kernel.running)
        await self.kernel.stop()
        self.assertFalse(self.kernel.running)
        self.assertEqual(self.operations, [
            ("start", "A"), ("start", "B"), ("start", "C"),
            ("stop", "C"), ("stop", "B"), ("stop", "A"),
        ])

    async def test_request_stop_releases_waiter(self) -> None:
        entered = asyncio.Event()

        async def wait():
            entered.set()
            await self.kernel.wait_until_stopped()

        waiter = asyncio.create_task(wait())
        try:
            async with asyncio.timeout(2):
                await entered.wait()
                self.assertFalse(waiter.done())
                self.kernel.request_stop()
                await waiter
        finally:
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
