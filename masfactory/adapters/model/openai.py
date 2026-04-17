from __future__ import annotations

import json
import time

from openai import OpenAI

from .base import Model, ModelResponseType
from ..token_usage_tracker import TokenUsageTracker


def _normalize_openai_tool_choice(tool_choice: str | dict | None) -> tuple[str | dict | None, bool]:
    if tool_choice is None:
        return None, False
    if isinstance(tool_choice, dict):
        return tool_choice, False

    normalized = tool_choice.strip().lower()
    if normalized in {"auto", "required"}:
        return normalized, False
    if normalized == "none":
        return None, True
    raise ValueError("OpenAI tool_choice must be 'auto', 'required', 'none', or a provider-native dict.")


def _normalize_openai_tool_message(message: dict) -> dict:
    normalized = dict(message)
    content = normalized.get("content")
    if isinstance(content, str) or content is None:
        return normalized
    try:
        normalized["content"] = json.dumps(content, ensure_ascii=False)
    except Exception:
        normalized["content"] = str(content)
    return normalized


class OpenAIModel(Model):
    """OpenAI chat model adapter using the official OpenAI SDK."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str | None = None,
        invoke_settings: dict | None = None,
        **kwargs,
    ):
        """Create an OpenAI model adapter.

        Args:
            model_name: OpenAI model name.
            api_key: OpenAI API key.
            base_url: Optional custom API base URL (OpenAI-compatible).
            invoke_settings: Default settings merged into every invoke call.
            **kwargs: Forwarded to the OpenAI SDK client constructor.
        """
        super().__init__(model_name, invoke_settings, **kwargs)

        if api_key is None or api_key == "":
            raise ValueError("OpenAI api_key is required.")
        if model_name is None or model_name == "":
            raise ValueError("OpenAI model_name is required.")

        client_kwargs = dict(kwargs)
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = OpenAI(api_key=api_key, **client_kwargs)
        self._model_name = model_name
        self._token_tracker = TokenUsageTracker(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
        )
        try:
            model_info = self._client.models.retrieve(model_name)
            if hasattr(model_info, "model_dump"):
                self._description = model_info.model_dump()
            elif hasattr(model_info, "dict"):
                self._description = model_info.dict()
            else:
                self._description = dict(model_info)
        except Exception:
            self._description = {"id": model_name, "object": "model"}
        self._settings_mapping = {
            "temperature": {
                "name": "temperature",
                "type": float,
                "section": [0.0, 2.0],
            },
            "max_tokens": {
                "name": "max_tokens",
                "type": int,
            },
            "top_p": {
                "name": "top_p",
                "type": float,
                "section": [0.0, 1.0],
            },
            "stop": {
                "name": "stop",
                "type": list[str],
            },
            "tool_choice": {
                "name": "tool_choice",
                "type": (str, dict),
            },
        }

    def _parse_response(self, response) -> dict:
        result = {}
        if response.choices[0].message.tool_calls:
            result["type"] = ModelResponseType.TOOL_CALL
            result["content"] = []
            for tool_call in response.choices[0].message.tool_calls:
                result["content"].append(
                    {
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments),
                    }
                )
            result["followup_messages"] = [response.choices[0].message.model_dump(exclude_none=True)]
        elif response.choices[0].message.content:
            result["type"] = ModelResponseType.CONTENT
            result["content"] = response.choices[0].message.content
        else:
            raise ValueError("Response is not valid")

        if hasattr(response, "usage") and response.usage:
            self._token_tracker.accumulate(
                input_usage=response.usage.prompt_tokens,
                output_usage=response.usage.completion_tokens,
            )

        return result

    def invoke(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        settings: dict | None = None,
        **kwargs,
    ) -> dict:
        """Invoke the OpenAI chat completions API.

        Args:
            messages: Chat messages.
            tools: Tool schemas (converted into OpenAI function tools).
            settings: Per-call override settings merged with defaults.
            **kwargs: Additional OpenAI SDK parameters. Supports:
                - max_retries: retry count for transient errors
                - retry_base_delay: base delay for exponential backoff

        Returns:
            Parsed model response dict.
        """
        tools_dict = [{"type": "function", "function": tool} for tool in tools] if tools else None
        normalized_messages = [
            _normalize_openai_tool_message(message) if isinstance(message, dict) and message.get("role") == "tool" else message
            for message in messages
        ]
        parsed_settings = self._parse_settings(settings)
        tool_choice, disable_tools = _normalize_openai_tool_choice(parsed_settings.pop("tool_choice", None))
        if disable_tools:
            tools_dict = None
        elif tool_choice is not None and tools_dict:
            parsed_settings["tool_choice"] = tool_choice
        max_retries = kwargs.pop("max_retries", 3)
        base_delay = kwargs.pop("retry_base_delay", 1.0)

        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=normalized_messages,
                    tools=tools_dict,
                    **parsed_settings,
                    **kwargs,
                )
                return self._parse_response(response)
            except Exception as e:  # noqa: BLE001
                last_exc = e

                status_code = getattr(e, "status_code", None)
                if status_code is None and hasattr(e, "response"):
                    status_code = getattr(getattr(e, "response", None), "status_code", None)

                retryable_status = {429, 500, 502, 503, 504}
                if status_code not in retryable_status and status_code is not None:
                    raise

                if attempt == max_retries - 1:
                    raise

                sleep_seconds = base_delay * (2**attempt)
                time.sleep(sleep_seconds)

        if last_exc:
            raise last_exc

        raise RuntimeError("OpenAIModel.invoke failed without specific exception")

    def generate_images(
        self,
        prompt: str,
        model: str = None,
        n: int = 1,
        quality: str = "standard",
        response_format: str = "url",
        size: str = "1024x1024",
        style: str = "vivid",
        user: str = None,
        **kwargs,
    ) -> list[dict]:
        """Generate images using the OpenAI Images API."""
        api_params = {
            "prompt": prompt,
            "n": n,
            "size": size,
        }

        if model is not None:
            api_params["model"] = model
        if quality != "standard":
            api_params["quality"] = quality
        if response_format != "url":
            api_params["response_format"] = response_format
        if style != "vivid":
            api_params["style"] = style
        if user is not None:
            api_params["user"] = user

        api_params.update(kwargs)
        response = self._client.images.generate(**api_params)

        images = []
        for img_data in response.data:
            img_dict = {}
            if hasattr(img_data, "url") and img_data.url:
                img_dict["url"] = img_data.url
            if hasattr(img_data, "b64_json") and img_data.b64_json:
                img_dict["b64_json"] = img_data.b64_json
            if hasattr(img_data, "revised_prompt") and img_data.revised_prompt:
                img_dict["revised_prompt"] = img_data.revised_prompt
            images.append(img_dict)

        return images


__all__ = ["OpenAIModel"]
