"""
app/integrations/africastalking.py
===================================
Integration with Africa's Talking API for sending SMS messages.
Used heavily for dunning notifications (T-3, T-1, T+0, suspension).
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

class SMSClient:
    def __init__(self, username: str, api_key: str):
        self.username = username
        self.api_key = api_key
        # Use sandbox URL if username is 'sandbox', otherwise production
        if self.username == "sandbox":
            self.base_url = "https://api.sandbox.africastalking.com/version1/messaging"
        else:
            self.base_url = "https://api.africastalking.com/version1/messaging"
        
        self.headers = {
            "ApiKey": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    async def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Sends an SMS via Africa's Talking.
        """
        # Formulate phone number to international format, assuming Kenya (+254) for local
        if phone_number.startswith("0"):
            phone_number = "+254" + phone_number[1:]
        elif not phone_number.startswith("+"):
            phone_number = "+" + phone_number

        data = {
            "username": self.username,
            "to": phone_number,
            "message": message
        }

        logger.info(f"SMS: Sending message to {phone_number}: '{message}'")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.base_url, headers=self.headers, data=data)
                
            if response.is_success:
                logger.info(f"SMS: Successfully sent to {phone_number}")
                return True
            else:
                logger.error(f"SMS: Failed to send to {phone_number}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"SMS: Exception while sending to {phone_number}: {e}")
            return False

# Initialize a global SMS client using environment variables.
# For production, these should be securely stored, but for now we pull from settings.
sms_client = SMSClient(
    username=getattr(settings, "AT_USERNAME", "sandbox"),
    api_key=getattr(settings, "AT_API_KEY", "dummy_key")
)

async def send_sms(phone_number: str, message: str) -> bool:
    """Convenience wrapper for the global SMS client."""
    return await sms_client.send_sms(phone_number, message)
