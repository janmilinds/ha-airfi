"""Constants for airfi."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

# Integration metadata
DOMAIN = "airfi"
ATTRIBUTION = "Data provided by Airfi ventilation unit"

# Configuration keys
CONF_SERIAL_NUMBER = "serial_number"

# Platform parallel updates - applied to all platforms
PARALLEL_UPDATES = 1

# Default configuration values
DEFAULT_UPDATE_INTERVAL_HOURS = 1
DEFAULT_ENABLE_DEBUGGING = False
DEFAULT_MODBUS_PORT = 502
DEFAULT_POLL_INTERVAL_SECONDS = 10
