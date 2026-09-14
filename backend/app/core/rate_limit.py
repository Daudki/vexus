"""
Shared slowapi Limiter instance.

Originally created inline in app/auth/router.py; extracted here so any
router needing rate limiting (auth login, threat-intel CVE sync, ...)
shares one Limiter rather than each creating its own independent
instance with its own separate counters (VEXUS v2 Development Rules,
"do not introduce a second implementation of the same subsystem" —
applies to infrastructure singletons like this one too).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
