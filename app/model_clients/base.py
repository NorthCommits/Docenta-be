from abc import ABC, abstractmethod


class LLMClient(ABC):
	@abstractmethod
	def complete(
		self,
		*,
		system: str,
		user: str,
		temperature: float = 0.7,
		max_tokens: int = 4096
	) -> str:
		raise NotImplementedError
