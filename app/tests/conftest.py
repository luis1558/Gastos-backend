import os

# Settings are read at import time; give tests harmless defaults so no real config is needed.
for _key, _value in {
    "DATABASE_URL": "sqlite://",
    "JWT_SECRET_KEY": "test-secret",
    "JWT_REFRESH_SECRET_KEY": "test-refresh-secret",
    "SMTP_USER": "test@example.com",
    "SMTP_PASSWORD": "test",
    "SMTP_FROM_EMAIL": "test@example.com",
}.items():
    os.environ.setdefault(_key, _value)
