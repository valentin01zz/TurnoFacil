"""Small helpers to read configuration from the environment, without extra dependencies."""

import os
from urllib.parse import unquote, urlparse


def load_env_file(path):
    """Load KEY=VALUE lines from a local .env file without overriding real env vars."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def env_bool(name, default):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def database_from_url(url):
    """Django DATABASES entry from a postgres:// URL, as hosting providers hand them out."""
    parts = urlparse(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise ValueError(f"Unsupported database URL scheme: {parts.scheme!r}")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or "5432"),
    }
