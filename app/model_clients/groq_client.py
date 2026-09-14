from groq import Groq

from app.core.config import settings
from app.core.logging import get_logger
from app.model_clients.base import LLMClient


logger = get_logger(__name__)

class GroqClient(LLMClient):
	def __init__(self, api_key: str | None, model: str | None = None) -> None:
		self._client = Groq(api_key=api_key or settings.groq_api_key)
		self._model = model or settings.groq_model

	def complete(
		self,
		*,
		system: str,
		user: str,
		temperature: float = 0.7,
		max_tokens: int = 4096
	) -> str:
		response = self._client.chat.completions.create(
			model=self._model,
			messages=[
				{"role": "system", "content": system},
				{"role": "user", "content": user},
			],
			temperature=temperature,
			max_tokens=max_tokens,
		)
		return response.choices[0].message.content or ""
