import logging
import re
import time

logger = logging.getLogger('safety')

MAX_MESSAGE_LENGTH = 500
MAX_REQUESTS_PER_HOUR = 20
RATE_LIMIT_WINDOW = 3600

_rate_limit_store: dict = {}

DANGEROUS_PATTERNS = [
    'ignore previous instructions',
    'ignore all instructions',
    'disregard your instructions',
    'you are now',
    'new instructions:',
    'system prompt:',
    'forget everything',
]


def check_message_length(message: str) -> tuple[bool, str]:
    if len(message) > MAX_MESSAGE_LENGTH:
        logger.warning(
            f"Message rejected — too long | "
            f"length={len(message)} | limit={MAX_MESSAGE_LENGTH}"
        )
        return False, (
            f"Your message is too long ({len(message)} characters).\n"
            f"Please keep your question under {MAX_MESSAGE_LENGTH} characters."
        )
    return True, ''


def sanitise_message(message: str) -> str:
    sanitised = message.strip()
    sanitised = ''.join(
        char for char in sanitised
        if ord(char) >= 32 or char in '\n\t'
    )
    message_lower = sanitised.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in message_lower:
            logger.warning(
                f"Prompt injection attempt detected | "
                f"pattern='{pattern}' | "
                f"message='{sanitised[:60]}'"
            )
            sanitised = re.sub(re.escape(pattern), '', sanitised, flags=re.IGNORECASE)
            message_lower = sanitised.lower()
    return sanitised.strip()


def check_rate_limit(phone_number: str) -> tuple[bool, str]:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Prune expired entries to prevent memory leak
    expired_keys = [
        key for key, ts in _rate_limit_store.items()
        if not ts or ts[-1] < window_start
    ]
    for key in expired_keys:
        del _rate_limit_store[key]

    timestamps = _rate_limit_store.get(phone_number, [])
    timestamps = [t for t in timestamps if t > window_start]

    if len(timestamps) >= MAX_REQUESTS_PER_HOUR:
        logger.warning(
            f"Rate limit exceeded | "
            f"phone={phone_number} | "
            f"requests={len(timestamps)} | "
            f"limit={MAX_REQUESTS_PER_HOUR}/hour"
        )
        return False, (
            "You have exceeded the message limit.\n"
            f"You have sent {MAX_REQUESTS_PER_HOUR} messages in the last hour.\n"
            "You can try again in about an hour.\n"
            "For urgent safety concerns, contact your HSE officer directly."
        )

    timestamps.append(now)
    _rate_limit_store[phone_number] = timestamps
    return True, ''


def run_security_checks(
    phone_number: str, message: str, *, skip_rate_limit: bool = False
) -> tuple[bool, str]:
    passed, reason = check_message_length(message)
    if not passed:
        return False, reason

    sanitised = sanitise_message(message)

    if not skip_rate_limit:
        passed, reason = check_rate_limit(phone_number)
        if not passed:
            return False, reason

    logger.info(f"Security checks passed | phone={phone_number}")
    return True, sanitised
