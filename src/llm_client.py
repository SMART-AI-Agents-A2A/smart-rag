import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post_json(base_url: str, endpoint: str, payload: dict[str, Any], timeout: int,
              *, api_key: str) -> dict[str, Any]:
    if not api_key.strip():
        raise ValueError("Configure OPENROUTER_API_KEY no .env para acessar a API")
    request = Request(
        base_url.rstrip("/") + endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as exc:
        hints = {
            401: "verifique OPENROUTER_API_KEY",
            402: "créditos insuficientes na OpenRouter",
            403: "acesso negado ao modelo ou à API",
            429: "limite de requisições atingido; tente novamente mais tarde",
        }
        hint = hints.get(exc.code, "verifique o modelo, os parâmetros e a disponibilidade da API")
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {hint}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("OpenRouter indisponível ou timeout; verifique OPENROUTER_BASE_URL") from exc
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("OpenRouter retornou JSON inválido") from exc
    if not isinstance(result, dict) or result.get("error"):
        raise RuntimeError("OpenRouter retornou uma resposta inválida ou erro")
    return result
