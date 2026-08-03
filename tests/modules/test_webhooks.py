"""
tests/modules/test_webhooks.py
===============================
Integration and pipeline tests for the Safaricom Daraja webhooks endpoint.
"""

from unittest.mock import patch
from uuid import UUID

import asyncpg
from fastapi.testclient import TestClient

DEFAULT_TENANT_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")


class MockArqRedis:
    def __init__(self):
        self.enqueued_jobs = []

    async def enqueue_job(self, job_name, *args, **kwargs):
        self.enqueued_jobs.append((job_name, args, kwargs))




async def get_test_customer_and_package_ids(conn: asyncpg.Connection):
    """Utility to retrieve seeded customer and package IDs."""
    customer_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", "customer@Frixel Connect.dev")
    package_id = await conn.fetchval("SELECT id FROM packages WHERE name = $1", "Daily 10Mbps")
    return customer_id, package_id


@patch("app.modules.webhooks.service.get_redis_pool")
async def test_webhook_successful_payment(mock_get_redis, client: TestClient, conn: asyncpg.Connection):
    """
    Asserts that a successful M-Pesa STK push callback (ResultCode=0):
      1. Confirms the pending payment.
      2. Records the M-Pesa receipt number.
      3. Enqueues the durable voucher generation task.
    """
    # Configure mock Redis
    mock_redis = MockArqRedis()
    mock_get_redis.return_value = mock_redis

    customer_id, package_id = await get_test_customer_and_package_ids(conn)

    # 1. Insert a pending payment record under the default tenant
    checkout_id = "ws_CO_SUCCESS_TEST"
    payment_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id)
        VALUES ($1, $2, 50.00, 'pending', '254708374149', $3, 'aaaaaaaa-0000-0000-0000-000000000001')
        RETURNING id
        """,
        customer_id, package_id, checkout_id
    )

    # 2. Fire the webhook callback payload
    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "test-merchant-id",
                "CheckoutRequestID": checkout_id,
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 50},
                        {"Name": "MpesaReceiptNumber", "Value": "RCTSUCCESS99"},
                        {"Name": "TransactionDate", "Value": 20260617120000},
                        {"Name": "PhoneNumber", "Value": 254708374149}
                    ]
                }
            }
        }
    }

    response = client.post("/api/v1/webhooks/daraja", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ResultCode": 0, "ResultDesc": "Accepted"}

    # 3. Assert the payment was updated to confirmed
    payment = await conn.fetchrow("SELECT status, mpesa_receipt_number FROM payments WHERE id = $1", payment_id)
    assert payment["status"] == "confirmed"
    assert payment["mpesa_receipt_number"] == "RCTSUCCESS99"

    # 4. Assert the task was enqueued to Redis
    assert len(mock_redis.enqueued_jobs) == 1
    assert mock_redis.enqueued_jobs[0][0] == "generate_voucher_task"
    assert mock_redis.enqueued_jobs[0][1][0] == str(payment_id)
    assert mock_redis.enqueued_jobs[0][1][1] == str(DEFAULT_TENANT_ID)

    # 5. Execute generate_voucher synchronously within the test loop context
    from app.modules.vouchers.service import generate_voucher
    await generate_voucher(conn, str(payment_id), DEFAULT_TENANT_ID, is_final_attempt=True)

    # 6. Assert the voucher and RADIUS credentials were created
    voucher = await conn.fetchrow("SELECT code, status FROM vouchers WHERE payment_id = $1", payment_id)
    assert voucher is not None
    assert voucher["status"] == "active"
    radcheck_count = await conn.fetchval(
        "SELECT COUNT(*) FROM radcheck WHERE username = $1",
        voucher["code"],
    )
    assert radcheck_count == 1


@patch("app.modules.webhooks.service.get_redis_pool")
async def test_webhook_idempotency(mock_get_redis, client: TestClient, conn: asyncpg.Connection):
    """
    Asserts that duplicate webhook hits for the same transaction:
      1. Are absorbed gracefully at the database layer.
      2. Return 200 OK without triggering multiple voucher generation background runs.
    """
    # Configure mock Redis
    mock_redis = MockArqRedis()
    mock_get_redis.return_value = mock_redis

    customer_id, package_id = await get_test_customer_and_package_ids(conn)

    # 1. Insert a pending payment record under the default tenant
    checkout_id = "ws_CO_IDEMPOTENT_TEST"
    payment_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id)
        VALUES ($1, $2, 50.00, 'pending', '254708374149', $3, 'aaaaaaaa-0000-0000-0000-000000000001')
        RETURNING id
        """,
        customer_id, package_id, checkout_id
    )

    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "test-merchant-id",
                "CheckoutRequestID": checkout_id,
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 50},
                        {"Name": "MpesaReceiptNumber", "Value": "RCTIDEMPOTENT"},
                        {"Name": "TransactionDate", "Value": 20260617120000},
                        {"Name": "PhoneNumber", "Value": 254708374149}
                    ]
                }
            }
        }
    }

    # First callback delivery
    response1 = client.post("/api/v1/webhooks/daraja", json=payload)
    assert response1.status_code == 200

    # Second callback delivery (duplicate)
    response2 = client.post("/api/v1/webhooks/daraja", json=payload)
    assert response2.status_code == 200

    # Verify that only ONE confirmed payment exists and job was enqueued once
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM payments WHERE mpesa_receipt_number = 'RCTIDEMPOTENT' AND status = 'confirmed'"
    )
    assert count == 1
    assert len(mock_redis.enqueued_jobs) == 1
    assert mock_redis.enqueued_jobs[0][0] == "generate_voucher_task"

    # Call generate_voucher manually to verify it provisions RADIUS once
    from app.modules.vouchers.service import generate_voucher
    code = await generate_voucher(conn, str(payment_id), DEFAULT_TENANT_ID, is_final_attempt=True)
    radcheck_count = await conn.fetchval("SELECT COUNT(*) FROM radcheck WHERE username = $1", code)
    assert radcheck_count == 1


async def test_webhook_failed_payment(client: TestClient, conn: asyncpg.Connection):
    """
    Asserts that a failed payment callback (ResultCode != 0):
      1. Marks the payment as 'failed' in the database.
      2. Records the failure description.
      3. Does NOT create RADIUS credentials.
    """
    customer_id, package_id = await get_test_customer_and_package_ids(conn)

    checkout_id = "ws_CO_FAILED_TEST"
    payment_id = await conn.fetchval(
        """
        INSERT INTO payments (customer_id, package_id, amount_kes, status, phone_number, mpesa_checkout_id, tenant_id)
        VALUES ($1, $2, 50.00, 'pending', '254708374149', $3, 'aaaaaaaa-0000-0000-0000-000000000001')
        RETURNING id
        """,
        customer_id, package_id, checkout_id
    )

    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "test-merchant-id",
                "CheckoutRequestID": checkout_id,
                "ResultCode": 1032,
                "ResultDesc": "Request cancelled by user."
            }
        }
    }

    response = client.post("/api/v1/webhooks/daraja", json=payload)
    assert response.status_code == 200

    # Verify status is failed and reason is populated
    payment = await conn.fetchrow("SELECT status, failure_reason FROM payments WHERE id = $1", payment_id)
    assert payment["status"] == "failed"
    assert payment["failure_reason"] == "Request cancelled by user."

    # Verify no voucher was generated
    voucher = await conn.fetchrow("SELECT id FROM vouchers WHERE payment_id = $1", payment_id)
    assert voucher is None
    radcheck_count = await conn.fetchval("SELECT COUNT(*) FROM radcheck")
    assert radcheck_count == 0


async def test_webhook_unknown_checkout_id(client: TestClient, conn: asyncpg.Connection):
    """
    Asserts that receiving a callback for an unknown CheckoutRequestID:
      1. Returns 200 OK to stop Daraja retries.
      2. Makes no modifications to database records.
    """
    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "test-merchant-id",
                "CheckoutRequestID": "ws_CO_UNKNOWN_ID",
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 50},
                        {"Name": "MpesaReceiptNumber", "Value": "RCTUNKNOWN"},
                        {"Name": "TransactionDate", "Value": 20260617120000},
                        {"Name": "PhoneNumber", "Value": 254708374149}
                    ]
                }
            }
        }
    }

    response = client.post("/api/v1/webhooks/daraja", json=payload)
    assert response.status_code == 200

    # Ensure no confirmed payments were saved
    count = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE mpesa_receipt_number = 'RCTUNKNOWN'")
    assert count == 0
    radcheck_count = await conn.fetchval("SELECT COUNT(*) FROM radcheck")
    assert radcheck_count == 0
