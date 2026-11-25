"""Generate cryptographically secure random secrets for .env configuration."""

from __future__ import annotations

import secrets


def main() -> None:
    print(f"SECRET_KEY={secrets.token_hex(32)}")
    print(f"ML_API_KEY={secrets.token_urlsafe(24)}")
    print(f"MQTT_PASSWORD={secrets.token_urlsafe(18)}")
    print(f"TURN_CREDENTIAL={secrets.token_urlsafe(18)}")


if __name__ == "__main__":
    main()
