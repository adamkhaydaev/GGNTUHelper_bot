import uuid
import httpx

from app.config import settings

GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
GIGACHAT_MODEL = "GigaChat"


# Кэш токена
_access_token: str | None = None


async def _get_access_token() -> str:
    """Получить Access token GigaChat (OAuth 2.0)."""
    global _access_token

    if _access_token:
        return _access_token

    rquid = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": rquid,
        "Authorization": f"Basic {settings.gigachat_auth_key}",
    }

    data = {"scope": "GIGACHAT_API_PERS"}

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        response = await client.post(
            GIGACHAT_AUTH_URL,
            headers=headers,
            data=data,
        )
        response.raise_for_status()
        result = response.json()

    _access_token = result["access_token"]
    return _access_token


async def ask_llm(question: str, context: str = "") -> str:
    """Отправить вопрос в GigaChat с контекстом."""
    token = await _get_access_token()

    system_prompt = (
        "Ты — помощник ректора ГГНТУ (Грозненский государственный "
        "нефтяной технический университет). Отвечай кратко, по делу, "
        "на русском языке. Помогай с вопросами управления вузом, "
        "аналитикой, стратегией, документами."
    )

    if context:
        system_prompt += (
            f"\n\nАКТУАЛЬНЫЕ ДАННЫЕ ВУЗА (свежие на момент запроса):\n"
            f"{context}\n\n"
            f"Используй эти данные при ответе. Если вопрос про цифры — "
            f"отвечай по этим данным. Не говори, что у тебя нет данных."
        )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    payload = {
        "model": GIGACHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
        "max_tokens": 1000,
    }

    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        response = await client.post(
            GIGACHAT_API_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        result = response.json()

    return result["choices"][0]["message"]["content"]
