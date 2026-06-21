# app/core/ip_context.py
from contextvars import ContextVar

# Thread/async-safe context variable to store client IP address for the current request.
client_ip_var: ContextVar[str] = ContextVar("client_ip_var", default="0.0.0.0")
