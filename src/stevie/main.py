import asyncio
import logging

import structlog

from stevie.config import ConfigurationService
from stevie.kernel import StevieKernel

def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO
    )

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True
    )

async def main() -> None:
    configure_logging()

    kernel = StevieKernel()
    kernel.install_signal_handlers()

    kernel.register(ConfigurationService())

    await kernel.start()

    config = kernel.get("configuration")
    print("Environment:", config.settings.stevie_env)
    
    await kernel.wait_until_stopped()
    await kernel.stop()

if __name__ == "__main__":
    asyncio.run(main())
