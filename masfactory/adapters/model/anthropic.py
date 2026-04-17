from __future__ import annotations

import json

try:
    from anthropic import Anthropic  # type: ignore
except ImportError:  # pragma: no cover
    Anthropic = None  # type: ignore

from .base import Model, ModelResponseType
from ..token_usage_tracker import TokenUsageTracker


def _normalize_anthropic_tool_choice(tool_choice: str | dict | None) -> dict | None:
    if tool_choice is None:
        return None
    if isinstance(tool_choice, dict):
        return tool_choice

    normalized = tool_choice.strip().lower()
    if normalized == "auto":
        return {"type": "auto"}
    if normalized == "required":
        return {"type": "any"}
    if normalized == "none":
        return {"type": "none"}
    raise ValueError("Anthropic tool_choice must be 'auto', 'required', 'none', or a provider-native dict.")


def _normalize_anthropic_tool_result(content: object) -> object:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)


class AnthropicModel(Model):
    """Anthropic chat model adapter using the official Anthropic SDK."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str | None = None,
        invoke_settings: dict | None = None,
        **kwargs,
    ):
        """Create an Anthropic model adapter."""
        super().__init__(model_name, invoke_settings, **kwargs)

        if model_name is None or model_name == "":
            raise ValueError("Anthropic model_name is required.")
        if api_key is None or api_key == "":
            raise ValueError("Anthropic api_key is required.")
        if Anthropic is None:
            raise ImportError(
                "Anthropic support requires the 'anthropic' package. "
                "Please install it with: pip install anthropic"
            )
        self._client = Anthropic(
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
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
                "section": [0.0, 1.0],
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
        if hasattr(response, "content") and any(getattr(block, "type", None) == "tool_use" for block in response.content):
            result["type"] = ModelResponseType.TOOL_CALL
            tool_calls: list[dict] = []
            followup_content: list[dict] = []
            for block in response.content:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    followup_content.append({"type": "text", "text": getattr(block, "text", "")})
                    continue
                if block_type != "tool_use":
                    continue
                args = getattr(block, "input", None)
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"input": args}
                tool_calls.append(
                    {
                        "id": getattr(block, "id", None),
                        "name": getattr(block, "name", None),
                        "arguments": args if args is not None else {},
                    }
                )
                followup_content.append(
                    {
                        "type": "tool_use",
                        "id": getattr(block, "id", None),
                        "name": getattr(block, "name", None),
                        "input": args if args is not None else {},
                    }
                )
            result["content"] = tool_calls
            result["followup_messages"] = [{"role": "assistant", "content": followup_content}]
        elif hasattr(response, "content") and any(getattr(block, "type", None) == "text" for block in response.content):
            result["type"] = ModelResponseType.CONTENT
            text_content = ""
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    text_content += getattr(block, "text", "")
            result["content"] = text_content
        else:
            raise ValueError("Response is not valid or contains unsupported content")

        if hasattr(response, "usage") and response.usage:
            self._token_tracker.accumulate(
                input_usage=response.usage.input_tokens,
                output_usage=response.usage.output_tokens,
            )

        return result

    def invoke(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        settings: dict | None = None,
        invoke_settings: dict | None = None,
        **kwargs,
    ) -> dict:
        """Invoke the Anthropic messages API."""
        system_message = None
        anthropic_messages = []

        for message in messages:
            if message["role"] == "system":
                system_message = message["content"]
            elif message["role"] == "tool":
                tool_call_id = message.get("tool_call_id")
                tool_result_content = _normalize_anthropic_tool_result(message.get("content"))
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call_id,
                                "content": tool_result_content,
                            }
                        ],
                    }
                )
            else:
                anthropic_messages.append(
                    {
                        "role": message["role"],
                        "content": message["content"],
                    }
                )

        anthropic_tools = []
        if tools:
            for tool in tools:
                anthropic_tools.append(
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "input_schema": tool["parameters"],
                    }
                )

        parsed_settings = self._parse_settings(settings)
        tool_choice = _normalize_anthropic_tool_choice(parsed_settings.pop("tool_choice", None))
        if tool_choice is not None and anthropic_tools:
            parsed_settings["tool_choice"] = tool_choice

        response = self._client.messages.create(
            model=self.model_name,
            messages=anthropic_messages,
            system=system_message,
            tools=anthropic_tools if anthropic_tools else None,
            **parsed_settings,
            **kwargs,
        )

        return self._parse_response(response)

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
        """Image generation is not supported for Anthropic models."""
        raise NotImplementedError(
            "Anthropic models do not support image generation. "
            "Please use OpenAI (DALL-E) or Google (Imagen) for image generation."
        )


__all__ = ["AnthropicModel"]
