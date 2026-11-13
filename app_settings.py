import secrets

import keyring
from keyring.errors import PasswordDeleteError
from PyQt6.QtCore import QSettings

from receipt_ai import PROVIDERS

ORGANIZATION = "ExpensesHistory"
APPLICATION = "ExpenseTracker"
# API keys live in Windows Credential Manager, never in the database or its backups
KEYRING_SERVICE = "ExpensesHistory AI"
DEFAULT_PROVIDER = "claude"
DEFAULT_PHONE_PORT = 8765


def app_settings():
    """Remembered settings; honours QSettings.setDefaultFormat so tests can redirect them."""
    return QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, ORGANIZATION, APPLICATION)


def ai_provider():
    name = app_settings().value("ai/provider", DEFAULT_PROVIDER)
    return name if name in PROVIDERS else DEFAULT_PROVIDER


def set_ai_provider(name):
    app_settings().setValue("ai/provider", name)


def ai_model(provider):
    return app_settings().value(f"ai/{provider}/model", "") or PROVIDERS[provider].models[0]


def set_ai_model(provider, model):
    app_settings().setValue(f"ai/{provider}/model", model.strip())


def api_key(provider):
    return keyring.get_password(KEYRING_SERVICE, provider)


def save_api_key(provider, key):
    keyring.set_password(KEYRING_SERVICE, provider, key)


def remove_api_key(provider):
    try:
        keyring.delete_password(KEYRING_SERVICE, provider)
    except PasswordDeleteError:
        pass


def phone_enabled():
    return app_settings().value("phone/enabled", False, type=bool)


def set_phone_enabled(enabled):
    app_settings().setValue("phone/enabled", enabled)


def phone_port():
    return app_settings().value("phone/port", DEFAULT_PHONE_PORT, type=int)


def set_phone_port(port):
    app_settings().setValue("phone/port", port)


def phone_token():
    """The secret part of the phone page's address; kept so a bookmark keeps working."""
    token = app_settings().value("phone/token", "")
    return token or new_phone_token()


def new_phone_token():
    token = secrets.token_urlsafe(12)
    app_settings().setValue("phone/token", token)
    return token
