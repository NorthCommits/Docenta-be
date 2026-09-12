from app.schemas.pipeline import ExtractedDocument

def extract(file_path: str) -> ExtractedDocument:
    raise NotImplementedError("Implemented in ingestion step")
