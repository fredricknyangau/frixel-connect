import functools
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.database import get_db


def audit(action: str, target_type: str) -> Callable:
    """
    Decorator for FastAPI endpoints to automatically log administrative mutations.
    It expects the route handler to have a parameter named `user` or `current_user`
    (which is the injected dict from `require_role`).
    It also attempts to extract a `target_id` from any kwargs ending in '_id'.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1. Execute the actual endpoint logic first.
            # If it raises an exception (e.g. 404, validation error), we don't log.
            result = await func(*args, **kwargs)

            # 2. Extract context for logging
            user_dict = kwargs.get("user") or kwargs.get("current_user")

            target_id = None
            for key, val in kwargs.items():
                if key.endswith("_id") and val:
                    # Attempt to parse as UUID if it's not already
                    try:
                        target_id = UUID(str(val))
                        break
                    except ValueError:
                        pass

            if user_dict and "tenant_id" in user_dict and "user_id" in user_dict:
                tenant_id = UUID(str(user_dict["tenant_id"]))
                actor_id = UUID(str(user_dict["user_id"]))

                # We do this in the background / asynchronously so it doesn't block the
                #  response.
                # Actually, await get_db() is fast enough, but we could use
                # BackgroundTasks.
                # For simplicity and guarantee of write, we just write it.
                async with get_db() as conn:
                    await conn.execute("""
                        INSERT INTO audit_log (tenant_id, actor_user_id, action, target_type, target_id, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """, tenant_id, actor_id, action, target_type, target_id, json.dumps({}))

            return result
        return wrapper
    return decorator
