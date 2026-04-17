from __future__ import annotations

import json

try:
    from google import genai  # type: ignore
except ImportError:  # pragma: no cover
    genai = None  # type: ignore

from .base import Model, ModelResponseType
from ..token_usage_tracker import TokenUsageTracker


def _normalize_gemini_tool_choice(tool_choice: str | dict | None) -> dict | None:
    if tool_choice is None:
        return None
    if isinstance(tool_choice, dict):
        return tool_choice

    normalized = tool_choice.strip().lower()
    if normalized == "auto":
        return {"function_calling_config": {"mode": "AUTO"}}
    if normalized == "required":
        return {"function_calling_config": {"mode": "ANY"}}
    if normalized == "none":
        return {"function_calling_config": {"mode": "NONE"}}
    raise ValueError("Gemini tool_choice must be 'auto', 'required', 'none', or a provider-native dict.")


def _normalize_gemini_tool_response(content: object) -> dict:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        return {"result": content}
    return {"result": content}


class GeminiModel(Model):
    """Gemini chat model adapter using the `google-genai` SDK."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str | None = None,
        invoke_settings: dict | None = None,
        **kwargs,
    ):
        """Create a Gemini model adapter."""
        super().__init__(model_name, invoke_settings, **kwargs)

        if model_name is None or model_name == "":
            raise ValueError("Gemini model_name is required.")
        if api_key is None or api_key == "":
            raise ValueError("Gemini api_key is required.")
        if genai is None:
            raise ImportError(
                "Gemini support requires the 'google-genai' package. "
                "Please install it with: pip install google-genai"
            )

        kwargs.pop("api_key", None)
        kwargs.pop("http_options", None)

        http_options = None
        if base_url:
            from google.genai import types

            http_options = types.HttpOptions(base_url=base_url)

        self._client = genai.Client(api_key=api_key, http_options=http_options, **kwargs)
        self._model_name = model_name
        self._token_tracker = TokenUsageTracker(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
        )
        try:
            model_info = self._client.models.get(model=model_name)
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
                "name": "max_output_tokens",
                "type": int,
            },
            "top_p": {
                "name": "top_p",
                "type": float,
                "section": [0.0, 1.0],
            },
            "stop": {
                "name": "stop_sequences",
                "type": list[str],
            },
            "tool_choice": {
                "name": "tool_choice",
                "type": (str, dict),
            },
        }

    def _parse_response(self, response) -> dict:
        result: dict = {}

        tool_calls: list[dict] = []
        followup_parts: list[dict] = []
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                function_call = getattr(part, "function_call", None)
                if function_call:
                    args = getattr(function_call, "args", None) or {}
                    tool_calls.append(
                        {
                            "id": getattr(function_call, "id", None),
                            "name": getattr(function_call, "name", None),
                            "arguments": args,
                        }
                    )
                    followup_parts.append(
                        {
                            "function_call": {
                                "name": getattr(function_call, "name", None),
                                "args": args,
                            }
                        }
                    )
                    continue

                text = getattr(part, "text", None)
                if text:
                    followup_parts.append({"text": text})

        if tool_calls:
            result["type"] = ModelResponseType.TOOL_CALL
            result["content"] = tool_calls
            result["followup_messages"] = [{"role": "model", "parts": followup_parts}]
        elif hasattr(response, "text") and response.text is not None:
            result["type"] = ModelResponseType.CONTENT
            result["content"] = response.text
        else:
            raise ValueError("Response is not valid or contains unsupported content")

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            self._token_tracker.accumulate(
                input_usage=response.usage_metadata.prompt_token_count,
                output_usage=response.usage_metadata.candidates_token_count,
            )

        return result

    def invoke(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        settings: dict | None = None,
        **kwargs,
    ) -> dict:
        """Invoke the Gemini generate_content API."""
        from google.genai import types

        if kwargs:
            print(f"[GeminiModel.invoke] Ignoring unexpected kwargs: {list(kwargs.keys())}")

        system_parts: list[str] = []
        contents: list[types.Content] = []

        for message in messages:
            role = message.get("role")
            content = message.get("content")

            if role == "system":
                if content is not None:
                    system_parts.append(str(content))
                continue

            if role == "tool":
                tool_name = message.get("name") or "tool"
                tool_response = _normalize_gemini_tool_response(content)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=tool_name,
                                response=tool_response,
                            )
                        ],
                    )
                )
                continue

            if role == "model" and isinstance(message.get("parts"), list):
                parts_payload = []
                for part in message["parts"]:
                    function_call = part.get("function_call") if isinstance(part, dict) else None
                    if function_call:
                        parts_payload.append(
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=function_call.get("name"),
                                    args=function_call.get("args") or {},
                                )
                            )
                        )
                contents.append(types.Content(role="model", parts=parts_payload))
                continue

            if content is None:
                text = ""
            elif isinstance(content, str):
                text = content
            else:
                try:
                    text = json.dumps(content, ensure_ascii=False)
                except Exception:
                    text = str(content)

            if role == "assistant":
                role = "model"

            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

        function_declarations: list[types.FunctionDeclaration] = []
        if tools:
            for tool in tools:
                function_declarations.append(
                    types.FunctionDeclaration(
                        name=tool.get("name"),
                        description=tool.get("description", ""),
                        parameters_json_schema=tool.get("parameters"),
                    )
                )

        config_kwargs = self._parse_settings(settings)
        tool_choice = _normalize_gemini_tool_choice(config_kwargs.pop("tool_choice", None))
        if system_parts:
            config_kwargs["system_instruction"] = "\n\n".join(system_parts)
        if function_declarations:
            config_kwargs["tools"] = [types.Tool(function_declarations=function_declarations)]
            if tool_choice is not None:
                config_kwargs["tool_config"] = tool_choice

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
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
        """Generate images using Google Imagen via the Gemini SDK."""
        size_mapping = {
            "256x256": "1K",
            "512x512": "1K",
            "1024x1024": "1K",
            "1792x1024": "2K",
            "1024x1792": "2K",
            "2048x2048": "2K",
        }
        imagen_size = size_mapping.get(size, "1K")
        imagen_model = model if model is not None else "imagen-3.0-generate-002"

        config = {
            "number_of_images": n,
            "image_size": imagen_size,
        }

        imagen_specific_params = [
            "aspect_ratio",
            "person_generation",
            "safety_filter_level",
            "negative_prompt",
            "language",
            "include_rai_reason",
            "output_mime_type",
            "compression_quality",
        ]
        for param in imagen_specific_params:
            if param in kwargs:
                config[param] = kwargs.pop(param)

        try:
            from google.genai import types
            import base64

            if "compression_quality" in config:
                config["output_compression_quality"] = config.pop("compression_quality")

            if kwargs:
                print(f"[GeminiModel.generate_images] Ignoring unexpected kwargs: {list(kwargs.keys())}")

            generation_config = types.GenerateImagesConfig(**config)
            response = self._client.models.generate_images(
                model=imagen_model,
                prompt=prompt,
                config=generation_config,
            )

            images = []
            for generated_image in response.generated_images:
                img_dict = {}
                if hasattr(generated_image, "image") and hasattr(generated_image.image, "image_bytes"):
                    img_dict["b64_json"] = base64.b64encode(generated_image.image.image_bytes).decode("utf-8")
                if hasattr(generated_image, "image") and hasattr(generated_image.image, "mime_type"):
                    img_dict["mime_type"] = generated_image.image.mime_type
                if hasattr(generated_image, "rai_filtered_reason") and generated_image.rai_filtered_reason:
                    img_dict["rai_filtered_reason"] = generated_image.rai_filtered_reason
                images.append(img_dict)

            return images
        except ImportError:
            raise ImportError(
                "Google GenAI library is required for image generation. "
                "Please install it with: pip install google-genai"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to generate images with Gemini Imagen: {str(e)}")


__all__ = ["GeminiModel"]
