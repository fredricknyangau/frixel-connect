"""
app/integrations/etims.py
=========================
HTTP client for Kenya Revenue Authority (KRA) eTIMS API.

This client interfaces with the OSCU (Online Sales Control Unit) to submit
sales transactions and receive compliance receipts/QR codes for invoices.
"""

import logging
import base64
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ETIMSError(Exception):
    """Raised when KRA eTIMS API returns an error."""
    pass


class ETIMSClient:
    """
    Async client for the KRA eTIMS API.

    Implements:
      - OAuth2 token management with caching
      - Sending sales transactions (invoices)

    Usage:
        etims = ETIMSClient()
        result = await etims.submit_invoice(tenant_tin, branch_id, invoice_number, items)
    """

    def __init__(self) -> None:
        self.base_url = settings.KRA_ETIMS_BASE_URL
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._timeout = httpx.Timeout(30.0)

    async def get_access_token(self) -> str:
        """
        Returns a valid KRA eTIMS access token, fetching a new one if expired.
        Uses Basic Auth with consumer key and secret.
        """
        # If mocking is enabled, don't actually hit the external API
        if settings.KRA_ETIMS_MOCK:
            return "mock_etims_token"

        now = datetime.now(timezone.utc)
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token

        if not settings.KRA_ETIMS_USERNAME or not settings.KRA_ETIMS_PASSWORD:
            raise ETIMSError("KRA eTIMS credentials are not configured.")

        logger.info("eTIMS: fetching new access token")

        credentials = f"{settings.KRA_ETIMS_USERNAME}:{settings.KRA_ETIMS_PASSWORD}"
        encoded = base64.b64encode(credentials.encode()).decode()

        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout) as client:
            response = await client.post(
                "/oauth2/v1/generate",
                params={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {encoded}"},
            )

        if not response.is_success:
            raise ETIMSError(
                f"Failed to get eTIMS access token: {response.status_code} {response.text}"
            )

        data = response.json()
        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))

        if not token:
            raise ETIMSError(f"eTIMS token response missing access_token: {data}")

        self._token = token
        self._token_expires_at = now + timedelta(seconds=expires_in - 60)
        logger.info(f"eTIMS: new token cached, expires in {expires_in - 60}s")
        
        return token

    async def submit_invoice(
        self,
        tin: str,
        bhf_id: str,
        invoice_number: int,
        amount: int,
        package_name: str,
    ) -> Dict[str, Any]:
        """
        Submits a sales transaction to KRA eTIMS.

        Args:
            tin: Taxpayer Identification Number
            bhf_id: Branch ID
            invoice_number: The sequential invoice number
            amount: The total payment amount
            package_name: Name of the package being billed

        Returns:
            Dict containing the eTIMS response, specifically the QR code URL
            and signature to print on the invoice.
        """
        # --- Mock Flow ---
        if settings.KRA_ETIMS_MOCK:
            logger.info(f"eTIMS (MOCK): Generating mock invoice for {tin} inv_no {invoice_number}")
            return {
                "success": True,
                "rcptSign": f"MOCK-SIGN-{uuid.uuid4().hex[:8].upper()}",
                "intrlData": "MOCK-INTERNAL-DATA",
                "rcptNo": invoice_number,
                "qrCodeUrl": f"https://itax.kra.go.ke/KRA-Portal/receipt?invoice={invoice_number}&mock=true"
            }
        
        # --- Real Flow ---
        token = await self.get_access_token()
        
        # Build the payload according to KRA specifications
        # The tax is typically 16% VAT, assuming amount is inclusive of VAT
        # For ISPs, usually it's VAT applicable.
        vat_rate = 16.0
        taxable_amount = amount / (1 + (vat_rate / 100))
        tax_amount = amount - taxable_amount

        payload = {
            "tin": tin,
            "bhfId": bhf_id,
            "invcNo": str(invoice_number),
            "salesTrnsItems": [
                {
                    "itemCd": "WIFI_SUBSCRIPTION",
                    "itemNm": package_name,
                    "qty": 1,
                    "prc": amount,
                    "splyAmt": round(taxable_amount, 2),
                    "dcRt": 0,
                    "dcAmt": 0,
                    "taxTyCd": "V",  # Standard VAT
                    "taxAmt": round(tax_amount, 2)
                }
            ]
        }

        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout) as client:
            response = await client.post(
                "/etims-oscu/v1/sendSalesTrns",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )

        if not response.is_success:
            raise ETIMSError(
                f"eTIMS sales submission failed: {response.status_code} {response.text}"
            )

        result = response.json()
        logger.info(f"eTIMS: Submitted invoice {invoice_number} for {tin}")
        
        # We need to extract the compliance QR Code/URL and signature from KRA's response
        return {
            "success": True,
            "rcptSign": result.get("rcptSign", ""),
            "intrlData": result.get("intrlData", ""),
            "rcptNo": result.get("rcptNo", invoice_number),
            "qrCodeUrl": result.get("qrCodeUrl", "")
        }

etims_client = ETIMSClient()
