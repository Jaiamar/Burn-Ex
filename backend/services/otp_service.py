"""
backend/services/otp_service.py

OTP Provider abstraction with a mock implementation for development.
Swap MockOTPProvider → TwilioOTPProvider by changing one env variable (OTP_PROVIDER=twilio).

Usage:
    from services.otp_service import otp_service
    code = otp_service.generate_and_send(phone)
    ok   = otp_service.verify(phone, submitted_code)
"""

import os
import random
import string
import time
from abc import ABC, abstractmethod
from typing import Dict, Tuple

OTP_TTL_SECONDS = 600  # 10 minutes


class OTPProvider(ABC):
    @abstractmethod
    def generate_and_send(self, phone: str) -> str:
        """Generate an OTP, send it, and return the code (for dev logging)."""
        ...

    @abstractmethod
    def verify(self, phone: str, code: str) -> bool:
        """Return True if the code is valid and not expired."""
        ...

    @abstractmethod
    def invalidate(self, phone: str):
        """Invalidate any active OTP for the given phone (after successful verify)."""
        ...


class MockOTPProvider(OTPProvider):
    """
    Development-only OTP provider.
    Generates a random 6-digit code, stores it in memory, and prints it to console.
    No real SMS is sent.
    """

    def __init__(self):
        # { phone: (code, expires_at_unix) }
        self._store: Dict[str, Tuple[str, float]] = {}

    def generate_and_send(self, phone: str) -> str:
        code = "".join(random.choices(string.digits, k=6))
        expires_at = time.time() + OTP_TTL_SECONDS
        self._store[phone] = (code, expires_at)
        # In production this line would be replaced by an SMS API call
        print(f"\n{'='*50}")
        print(f"[MockOTP] Phone: {phone}")
        print(f"[MockOTP] OTP Code: {code}   (valid for 10 minutes)")
        print(f"{'='*50}\n")
        return code  # Returned so tests / API response can surface it in dev mode

    def verify(self, phone: str, code: str) -> bool:
        entry = self._store.get(phone)
        if not entry:
            return False
        stored_code, expires_at = entry
        if time.time() > expires_at:
            del self._store[phone]
            return False
        return stored_code == code.strip()

    def invalidate(self, phone: str):
        self._store.pop(phone, None)


class TwilioOTPProvider(OTPProvider):
    """
    Production Twilio SMS OTP provider.
    Requires environment variables:
        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
    Install: pip install twilio
    """

    def __init__(self):
        self._store: Dict[str, Tuple[str, float]] = {}
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token  = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_FROM_NUMBER", "")

    def generate_and_send(self, phone: str) -> str:
        try:
            from twilio.rest import Client  # type: ignore
        except ImportError:
            raise RuntimeError("twilio package not installed. Run: pip install twilio")
        code = "".join(random.choices(string.digits, k=6))
        expires_at = time.time() + OTP_TTL_SECONDS
        self._store[phone] = (code, expires_at)
        client = Client(self.account_sid, self.auth_token)
        client.messages.create(
            body=f"Your Burn-Ex OTP is: {code}. Valid for 10 minutes.",
            from_=self.from_number,
            to=phone
        )
        return code

    def verify(self, phone: str, code: str) -> bool:
        entry = self._store.get(phone)
        if not entry:
            return False
        stored_code, expires_at = entry
        if time.time() > expires_at:
            del self._store[phone]
            return False
        return stored_code == code.strip()

    def invalidate(self, phone: str):
        self._store.pop(phone, None)


def _build_provider() -> OTPProvider:
    provider_name = os.environ.get("OTP_PROVIDER", "mock").lower()
    if provider_name == "twilio":
        return TwilioOTPProvider()
    return MockOTPProvider()


# Singleton used across the app
otp_service: OTPProvider = _build_provider()
