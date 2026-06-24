"""
GitHub webhook signature verification.

Without this, ANYONE who finds your /webhook URL can POST a fake
"PR opened" payload and make your bot review/comment on arbitrary repos,
burn your Groq/Gemini quota, or spam PRs with junk comments.

GitHub signs every webhook delivery with HMAC-SHA256 using a secret you
set when creating the webhook. We recompute that signature server-side
and reject anything that doesn't match — same pattern Stripe/GitHub/etc.
all use for webhook auth.
"""

import hmac
import hashlib
import os


class InvalidSignatureError(Exception):
    pass


def verify_github_signature(payload_body: bytes, signature_header: str | None) -> None:
    """
    Verifies the X-Hub-Signature-256 header GitHub sends with every webhook.

    Raises InvalidSignatureError if the signature is missing, malformed,
    or doesn't match — caller should respond 401/403 and NOT process the payload.
    """
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        # Fail closed, not open — refuse to run an unauthenticated webhook
        # in anything that isn't explicit local dev.
        raise InvalidSignatureError(
            "GITHUB_WEBHOOK_SECRET is not set on the server — refusing webhook"
        )

    if not signature_header:
        raise InvalidSignatureError("Missing X-Hub-Signature-256 header")

    if not signature_header.startswith("sha256="):
        raise InvalidSignatureError("Malformed signature header")

    expected_signature = signature_header.removeprefix("sha256=")

    computed = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    # constant-time comparison — prevents timing attacks
    if not hmac.compare_digest(computed, expected_signature):
        raise InvalidSignatureError("Signature mismatch")
