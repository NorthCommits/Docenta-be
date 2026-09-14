from app.extraction.orchestrator import run_extraction
from app.schemas.pipeline import ExtractedDocument


def extract(file_path: str, filename: str) -> ExtractedDocument:
    return run_extraction(file_path, filename)