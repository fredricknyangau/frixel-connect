"""
app/modules/setup/__init__.py
==============================
Setup module — public endpoints for the Magic Command router onboarding.

These endpoints are PUBLIC (no JWT required). The setup token acts as
the authentication credential. It is a 43-character URL-safe random string
equivalent to 256 bits of entropy, single-use, and expires in 24 hours.
"""
