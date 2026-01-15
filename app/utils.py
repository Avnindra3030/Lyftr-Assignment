"""
Utility functions for the Webhook API.
"""

import hmac
import hashlib


def verify_hmac_signature(body: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC-SHA256 signature.
    
    Args:
        body: Raw request body bytes
        signature: Hex-encoded signature from X-Signature header
        secret: WEBHOOK_SECRET
    
    Returns:
        True if signature is valid, False otherwise
    """
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, signature)
