from loguru import logger
import sys

# Configure loguru to print to stdout so we can see it
logger.remove()
logger.add(sys.stdout, level="INFO")

from utils import timer  # noqa: E402

logger.info("--- Starting Import Test ---")
with timer("Total Startup Simulation"):
    with timer("Telemetry init"):
        import telemetry

        telemetry.init_telemetry()

    with timer("App Imports"):
        pass

logger.info("--- Import Test Complete ---")
