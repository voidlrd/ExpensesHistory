import base64
from contextlib import contextmanager

import anthropic
import httpx2
from google import genai
from google.genai import errors as genai_errors, types as genai_types

TIMEOUT_SECONDS = 180
MAX_TOKENS = 16000
GEMINI_REQUEST_LIMIT = 20 * 1024 * 1024
SETTINGS_HINT = "Data Manager → AI & Phone"


class AIError(Exception):
    pass


def _key_rejected(name):
    return AIError(f"{name} didn't accept the API key. Check it in {SETTINGS_HINT}.")


def _unknown_model(name, model):
    return AIError(f"{name} doesn't know the model \"{model}\". Pick another one in {SETTINGS_HINT}.")


def _busy(name):
    return AIError(f"{name} is busy, or the key's usage limit was reached. Wait a minute and try again.")


def _down(name):
    return AIError(f"{name} is having problems right now. Try again in a few minutes.")


def _offline(name):
    return AIError(f"Couldn't reach {name}. Check the internet connection.")


class Claude:
    name = "Claude"
    key_page = "https://platform.claude.com/settings/keys"
    models = ("claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5")
    # if the model declines, the API retries on this one, never on something stronger
    fallbacks = {"claude-sonnet-5-5": "claude-sonnet-5"}

    def __init__(self, api_key, http_client=None):
        self.client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS, http_client=http_client)

    @contextmanager
    def _errors(self, model):
        try:
            yield
        except anthropic.AuthenticationError:
            raise _key_rejected(self.name) from None
        except anthropic.NotFoundError:
            raise _unknown_model(self.name, model) from None
        except anthropic.RateLimitError:
            raise _busy(self.name) from None
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise _down(self.name) from None
            error = e.body.get("error") if isinstance(e.body, dict) else None
            detail = error.get("message") if isinstance(error, dict) else e.message
            raise AIError(f"{self.name} refused the request: {detail}") from None
        except anthropic.APIConnectionError:
            raise _offline(self.name) from None

    def check(self, model):
        with self._errors(model):
            self.client.models.retrieve(model)

    def ask(self, model, prompt, images):
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(image).decode("ascii")}}
            for image in images
        ]
        content.append({"type": "text", "text": prompt})
        request = {"model": model, "max_tokens": MAX_TOKENS, "messages": [{"role": "user", "content": content}]}

        with self._errors(model):
            if model in self.fallbacks:
                response = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks=[{"model": self.fallbacks[model]}], **request)
            else:
                response = self.client.messages.create(**request)

        if response.stop_reason == "refusal":
            raise AIError(f"{self.name} declined to read this. Try again, or use Copy Prompt instead.")
        if response.stop_reason == "max_tokens":
            raise AIError(f"{self.name}'s reply was cut off. Try sending fewer photos at once.")
        return "".join(block.text for block in response.content if block.type == "text")


class Gemini:
    name = "Gemini"
    key_page = "https://aistudio.google.com/apikey"
    models = ("gemini-4-hydrogen", "gemini-4-argon", "gemini-4-carbon", "gemini-3.5-flash-lite")

    def __init__(self, api_key, http_client=None):
        options = genai_types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000, httpx_client=http_client)
        self.client = genai.Client(api_key=api_key, http_options=options)

    @contextmanager
    def _errors(self, model):
        try:
            yield
        except genai_errors.ClientError as e:
            if e.code in (401, 403):
                raise _key_rejected(self.name) from None
            if e.code == 404:
                raise _unknown_model(self.name, model) from None
            if e.code == 429:
                raise _busy(self.name) from None
            raise AIError(f"{self.name} refused the request: {e.message}") from None
        except genai_errors.ServerError:
            raise _down(self.name) from None
        except httpx2.RequestError:
            raise _offline(self.name) from None

    def check(self, model):
        with self._errors(model):
            self.client.models.get(model=model)

    def ask(self, model, prompt, images):
        # base64 grows the photos by a third
        if sum(len(image) for image in images) * 4 // 3 + len(prompt) > GEMINI_REQUEST_LIMIT:
            raise AIError("These photos are too large to send to Gemini together. Send fewer at once.")

        parts = [genai_types.Part.from_bytes(data=image, mime_type="image/jpeg") for image in images]
        config = genai_types.GenerateContentConfig(
            max_output_tokens=MAX_TOKENS,
            media_resolution=genai_types.MediaResolution.MEDIA_RESOLUTION_HIGH,
        )
        with self._errors(model):
            response = self.client.models.generate_content(model=model, contents=parts + [prompt], config=config)

        if not response.text:
            candidate = response.candidates[0] if response.candidates else None
            reason = candidate.finish_reason if candidate else response.prompt_feedback
            raise AIError(f"{self.name} sent back no answer ({reason}). Try again, or use Copy Prompt instead.")
        return response.text


PROVIDERS = {"claude": Claude, "gemini": Gemini}
