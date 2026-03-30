"""Constants for Airfi."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

# Integration metadata
DOMAIN = "airfi"
ATTRIBUTION = "Data provided by Airfi ventilation unit"

# Configuration keys
CONF_SERIAL_NUMBER = "serial_number"
CONF_MODEL_NAME = "model_name"

# Platform parallel updates - applied to all platforms
PARALLEL_UPDATES = 1

# Default configuration values
DEFAULT_MODBUS_PORT = 502
DEFAULT_POLL_INTERVAL_SECONDS = 10

# Discovery configuration
DISCOVERY_MULTICAST_GROUP = "239.255.100.200"
DISCOVERY_MULTICAST_PORT = 3000
DISCOVERY_INITIAL_SCAN_TIMEOUT_SECONDS = 5
DISCOVERY_SCAN_TIMEOUT_SECONDS = 10
DISCOVERY_PACKET_TIMEOUT_SECONDS = 2
DISCOVERY_QUIET_PERIOD_SECONDS = 3
DISCOVERY_DEVICE_PORT = 4000
DISCOVERY_RECOVERY_SCAN_TIMEOUT_SECONDS = 5
DISCOVERY_RECOVERY_COOLDOWN_SECONDS = 60

# Recovery configuration
# How long the device must be unreachable before rediscovery is triggered (90 seconds)
RECOVERY_TRIGGER_SECONDS = 90
# How long the device must be unreachable before a repairs issue is raised (10 minutes)
RECOVERY_ISSUE_SECONDS = 600

# Repairs issue identifiers
ISSUE_DEVICE_UNREACHABLE = "device_unreachable"

# Device models (byte 11 parsing: index = (model_id - 1) // 2, variant = L if odd else R)
# Variant placeholder {} is replaced with L/R based on model_id parity
AIRFI_MODELS = [
    "60 {}",  # 0x01-0x02 "60L, 60R"
    "100 {}",  # 0x03-0x04 "100L, 100R"
    "150 {}",  # 0x05-0x06 "150L, 150R"
    "130 {}",  # 0x07-0x08 "130L, 130R"
    "250 {} Electric",  # 0x09-0x0A "250L, 250R"
    "250 {} Water",  # 0x0B-0x0C "250L, 250R"
    "350 {} Electric",  # 0x0D-0x0E "350L, 350R"
    "350 {} Water",  # 0x0F-0x10 "350L, 350R"
    "C5 {} Electric",  # 0x11-0x12 "C5LE, C5RE"
    "C5 {} Water",  # 0x13-0x14 "C5LW, C5RW"
    "53 mini {}",  # 0x15-0x16 "53ML, 53MR"
    "53 miniENT {}",  # 0x17-0x18 "53MEL, 53MER"
    "60 ENT {}",  # 0x19-0x1A "60EL, 60ER",
    "130 ENT {}",  # 0x1B-0x1C "130EL, 130ER",
    "150 ENT {}",  # 0x1D-0x1E "150EL, 150ER",
    "250 ENT {} Electric",  # 0x1F-0x20 "250ELE, 250ERE",
    "250 ENT {} Water",  # 0x21-0x22 "250ELW, 250ERW",
    "350 ENT {} Electric",  # 0x23-0x24 "350ELE, 350ERE",
    "350 ENT {} Water",  # 0x25-0x26 "350ELW, 350ERW",
]
