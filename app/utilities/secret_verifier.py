import hmac

from app.interfaces.utilities import ISecretVerifier


class SharedSecretVerifier(ISecretVerifier):
    """Checks the shared secret Vapi sends with each webhook, in constant time."""

    def __init__(self, expected: str) -> None:
        self._expected = expected

    def is_valid(self, provided: str | None) -> bool:
        if not self._expected:
            # No secret configured: verification is disabled (local development only).
            return True
        return hmac.compare_digest(self._expected.encode(), (provided or "").encode())
