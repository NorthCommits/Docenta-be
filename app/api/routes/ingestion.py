import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.extraction.orchestrator import SUPPORTED_FORMATS
from app.schemas.pipeline import ExtractedDocument
from app.services.ingestion import extract

logger = logging.getLogger("docenta.api.ingestion")

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def _extension(filename: str) -> str:
    ext = os.path.splitext(filename)[-1].lower().lstrip(".")
    return "html" if ext == "htm" else ext


@router.post("/extract", response_model=ExtractedDocument)
async def extract_document(file: UploadFile = File(...)) -> ExtractedDocument:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = _extension(file.filename)
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: .{ext}. Supported: {', '.join(SUPPORTED_FORMATS)}",
        )

    tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.{ext}")

    try:
        size = 0
        with open(tmp_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File too large. Maximum {MAX_FILE_SIZE_MB} MB.",
                    )
                out.write(chunk)

        return extract(tmp_path, file.filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extraction failed for {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Extraction failed.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)