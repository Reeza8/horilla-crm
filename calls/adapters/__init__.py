"""
Telephony provider adapters for Horilla Calls Integration.

Import all adapters here so they self-register via @register_adapter() when
AppConfig.ready() triggers auto_import_modules.
"""

from .twilio_adapter import TwilioAdapter
from .signalwire_adapter import SignalWireAdapter
from .telnyx_adapter import TelnyxAdapter
from .sinch_adapter import SinchAdapter
from .exotel_adapter import ExotelAdapter
from .mock_adapter import MockAdapter
from .factory import get_adapter, registered_providers

__all__ = [
    "TwilioAdapter",
    "SignalWireAdapter",
    "TelnyxAdapter",
    "SinchAdapter",
    "ExotelAdapter",
    "MockAdapter",
    "get_adapter",
    "registered_providers",
]
