from urllib.parse import urlsplit


def get_cors_allowed_origins(next_public_url: str | None) -> list[str]:
    if not next_public_url:
        return []

    value = next_public_url.strip()

    if not value or value == "*":
        return []

    try:
        parsed = urlsplit(value)

        if parsed.scheme not in ("http", "https"):
            return []

        if not parsed.hostname or parsed.username or parsed.password:
            return []

        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            return []

        # Accessing port also validates its numeric range.
        parsed.port

        return [f"{parsed.scheme}://{parsed.netloc}"]

    except ValueError:
        return []