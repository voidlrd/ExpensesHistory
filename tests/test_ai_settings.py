import pytest

import app_settings
from conftest import wait_until
from receipt_ai import AIError, Claude, Gemini


@pytest.fixture
def panel(qt_env):
    from ui.views.ai_panel import AIPanel
    return AIPanel()


@pytest.fixture
def checks(monkeypatch):
    """Records key checks instead of calling the providers; set .error to make them fail."""
    class Checks:
        calls = []
        error = None

    def check(self, model):
        Checks.calls.append((self.name, model))
        if Checks.error:
            raise Checks.error

    Checks.calls = []
    monkeypatch.setattr(Claude, "check", check)
    monkeypatch.setattr(Gemini, "check", check)
    return Checks


# ---------- settings ----------

def test_defaults_are_claude_with_sonnet(qt_env):
    assert app_settings.ai_provider() == "claude"
    assert app_settings.ai_model("claude") == "claude-sonnet-5-5"
    assert app_settings.ai_model("gemini") == Gemini.models[0]


def test_provider_and_model_are_remembered(qt_env):
    app_settings.set_ai_provider("gemini")
    app_settings.set_ai_model("gemini", " gemini-4-argon ")

    assert app_settings.ai_provider() == "gemini"
    assert app_settings.ai_model("gemini") == "gemini-4-argon"
    assert app_settings.ai_model("claude") == "claude-sonnet-5-5"


def test_an_unknown_provider_falls_back_to_claude(qt_env):
    app_settings.set_ai_provider("something-old")
    assert app_settings.ai_provider() == "claude"


def test_keys_are_kept_per_provider_in_the_credential_store(fake_keyring):
    app_settings.save_api_key("claude", "sk-ant-1234")

    assert app_settings.api_key("claude") == "sk-ant-1234"
    assert app_settings.api_key("gemini") is None
    assert fake_keyring.passwords == {(app_settings.KEYRING_SERVICE, "claude"): "sk-ant-1234"}

    app_settings.remove_api_key("claude")
    app_settings.remove_api_key("claude")  # already gone: no error
    assert app_settings.api_key("claude") is None


# ---------- AI & Phone tab ----------

def test_without_a_key_the_tab_says_where_to_get_one(panel):
    assert "No Claude key saved yet" in panel.key_status.text()
    assert Claude.key_page in panel.key_status.text()
    assert not panel.test_btn.isEnabled()
    assert panel.model_input.currentText() == "claude-sonnet-5-5"


def test_saving_a_key_stores_it_hides_it_and_tests_it(panel, checks):
    panel.key_input.setText("  sk-ant-secret-wxyz  ")
    panel.save_key()

    assert app_settings.api_key("claude") == "sk-ant-secret-wxyz"
    assert panel.key_input.text() == ""
    assert "ending in …wxyz" in panel.key_status.text()
    wait_until(lambda: "key works" in panel.status_label.text())
    assert checks.calls == [("Claude", "claude-sonnet-5-5")]
    assert panel.test_btn.isEnabled()


def test_a_rejected_key_is_explained(panel, checks):
    checks.error = AIError("Claude didn't accept the API key.")
    panel.key_input.setText("sk-ant-wrong")
    panel.save_key()

    wait_until(lambda: "didn't accept" in panel.status_label.text())
    assert panel.test_btn.isEnabled()


def test_an_unexpected_failure_is_shown_not_swallowed(panel, checks):
    checks.error = RuntimeError("boom")
    app_settings.save_api_key("claude", "sk-ant-1")
    panel.load()
    panel.test_key()

    wait_until(lambda: "Something went wrong: boom" in panel.status_label.text())


def test_saving_an_empty_key_asks_for_one(panel, checks):
    panel.save_key()

    assert "Paste the key" in panel.status_label.text()
    assert app_settings.api_key("claude") is None
    assert checks.calls == []


def test_switching_provider_is_remembered_with_its_own_models_and_key(panel):
    app_settings.save_api_key("gemini", "AIza-gem-1234")

    panel.provider_input.setCurrentIndex(panel.provider_input.findData("gemini"))

    assert app_settings.ai_provider() == "gemini"
    assert panel.model_input.itemText(0) == Gemini.models[0]
    assert "Gemini key ending in …1234" in panel.key_status.text()

    panel.model_input.setCurrentText("gemini-4-carbon")
    assert app_settings.ai_model("gemini") == "gemini-4-carbon"
    assert app_settings.ai_model("claude") == "claude-sonnet-5-5"


def test_remove_key_after_confirming(panel, popups):
    app_settings.save_api_key("claude", "sk-ant-1")
    panel.load()

    panel.remove_key()

    assert app_settings.api_key("claude") is None
    assert "No Claude key saved yet" in panel.key_status.text()


def test_data_manager_has_the_ai_tab(qt_env):
    from ui.views.data_manager import DataManagerView

    view = DataManagerView()
    titles = [view.tabs.tabText(i) for i in range(view.tabs.count())]
    assert "AI & Phone" in titles
