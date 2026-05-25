"""
Telephony provider adapters for Horilla Calls Integration.

Import all adapters here so they self-register via @register_adapter() when
AppConfig.ready() triggers auto_import_modules.
"""

from .twilio_adapter import TwilioAdapter
from .exotel_adapter import ExotelAdapter
from .asterisk_adapter import AsteriskAdapter
from .three_cx_adapter import ThreeCXAdapter
from .custom_adapter import CustomAdapter
from .factory import get_adapter, registered_providers

__all__ = [
    "TwilioAdapter",
    "ExotelAdapter",
    "AsteriskAdapter",
    "ThreeCXAdapter",
    "CustomAdapter",
    "get_adapter",
    "registered_providers",
]
