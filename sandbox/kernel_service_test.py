import asyncio
import logging

import structlog

from stevie.kernel import StevieKernel

def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=logging.INFO)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True
    )

class FakeService:
    name = "fake_service"

    async def start(self) -> None:
        print("Fake service started")
    
    async def stop(self) -> None:
        print("Fake service stopped")

async def main() -> None:
    configure_logging()

    kernel = StevieKernel()
    kernel.add_service(FakeService())

    await kernel.start()
    await kernel.stop()

asyncio.run(main())
