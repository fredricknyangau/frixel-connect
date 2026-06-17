"""
app/modules/wallets/service.py
===============================
Service layer for reseller wallet ledger entries and calculations.
Uses row-level locking on the users table to prevent concurrency race conditions.
"""

from decimal import Decimal
import logging
from uuid import UUID

import asyncpg

from app.core.exceptions import InsufficientBalanceException

logger = logging.getLogger(__name__)


async def get_wallet_balance(conn: asyncpg.Connection, reseller_id: UUID) -> Decimal:
    """
    Reads the balance_after of the most recent ledger row for the reseller.
    If no ledger entries exist, the balance defaults to 0.00.
    """
    balance = await conn.fetchval(
        """
        SELECT balance_after
        FROM wallet_transactions
        WHERE reseller_id = $1
        ORDER BY sequence_id DESC
        LIMIT 1
        """,
        reseller_id,
    )
    return Decimal(str(balance)) if balance is not None else Decimal("0.00")


async def get_wallet_transactions(
    conn: asyncpg.Connection,
    reseller_id: UUID,
    limit: int = 20,
) -> list[dict]:
    """Retrieves the last N ledger entries for a reseller, sorted by newest first."""
    rows = await conn.fetch(
        """
        SELECT id, tenant_id, reseller_id, type, amount_kes, balance_after, reference, created_at
        FROM wallet_transactions
        WHERE reseller_id = $1
        ORDER BY sequence_id DESC
        LIMIT $2
        """,
        reseller_id,
        limit,
    )
    return [dict(r) for r in rows]


async def topup_wallet(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    reseller_id: UUID,
    amount: Decimal,
    reference: str,
) -> dict:
    """
    Tops up the reseller's wallet.
    Acquires an exclusive lock on the reseller's user record in the users table
    before reading the current balance and inserting the new transaction.
    This strictly serializes all financial modifications for this reseller.
    """
    # 1. Lock the reseller user record to serialize reads/writes
    await conn.execute("SELECT id FROM users WHERE id = $1 FOR UPDATE", reseller_id)

    # 2. Derive balance and calculate new balance after topup
    current_balance = await get_wallet_balance(conn, reseller_id)
    new_balance = current_balance + amount

    logger.info(
        f"Wallet Topup: reseller {reseller_id}, amount KES {amount}, "
        f"old balance KES {current_balance}, new balance KES {new_balance}, reference '{reference}'"
    )

    # 3. Insert ledger entry (append-only)
    row = await conn.fetchrow(
        """
        INSERT INTO wallet_transactions
            (tenant_id, reseller_id, type, amount_kes, balance_after, reference)
        VALUES ($1, $2, 'topup', $3, $4, $5)
        RETURNING id, tenant_id, reseller_id, type, amount_kes, balance_after, reference, created_at
        """,
        tenant_id,
        reseller_id,
        amount,
        new_balance,
        reference,
    )
    return dict(row)


async def debit_wallet(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    reseller_id: UUID,
    amount: Decimal,
    reference: str,
) -> dict:
    """
    Debits the reseller's wallet.
    Acquires an exclusive lock on the reseller's user record in the users table
    before verifying balance and appending a new transaction.
    Raises InsufficientBalanceException if amount > current balance, with no row inserted.
    """
    # 1. Lock the reseller user record to serialize reads/writes
    await conn.execute("SELECT id FROM users WHERE id = $1 FOR UPDATE", reseller_id)

    # 2. Derive balance and verify
    current_balance = await get_wallet_balance(conn, reseller_id)

    if current_balance < amount:
        raise InsufficientBalanceException(
            f"Insufficient balance. Required: KES {amount}, Current: KES {current_balance}"
        )

    new_balance = current_balance - amount

    logger.info(
        f"Wallet Debit: reseller {reseller_id}, amount KES {amount}, "
        f"old balance KES {current_balance}, new balance KES {new_balance}, reference '{reference}'"
    )

    # 3. Insert ledger entry (append-only)
    row = await conn.fetchrow(
        """
        INSERT INTO wallet_transactions
            (tenant_id, reseller_id, type, amount_kes, balance_after, reference)
        VALUES ($1, $2, 'debit', $3, $4, $5)
        RETURNING id, tenant_id, reseller_id, type, amount_kes, balance_after, reference, created_at
        """,
        tenant_id,
        reseller_id,
        amount,
        new_balance,
        reference,
    )
    return dict(row)
