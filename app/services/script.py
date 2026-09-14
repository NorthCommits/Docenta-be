from app.model_clients.base import LLMClient
from app.schemas.pipeline import ExtractedDocument, Script


def generate_script(document: ExtractedDocument, client: LLMClient) -> Script:
    raise NotImplementedError("Implemented in the script-generation step")
