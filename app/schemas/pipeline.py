from enum import Enum

from pydantic import BaseModel, Field

class ContentType(str, Enum):
    DEFINITION = "definition"
    PROCESS = "process"
    STORY = "story"
    DATA = "data"
    SUMMARY = "summary"

class ExtractionRegion(BaseModel):
    type: str = Field(description="title, heading, body, table, image, caption, etc.")
    text: str
    sequence: int

class ExtractedPage(BaseModel):
    page_number: int
    layout_type: str
    regions: list[ExtractionRegion]
    full_text: str

class ExtractedDocument(BaseModel):
    source_filename: str
    format: str
    page_count: int
    pages: list[ExtractedPage]
    text: str

class Scene(BaseModel):
    narration: str = Field(description="What the voice-over says for this scene.")
    visual: str = Field(description="What should be shown on screen.")
    content_type: ContentType = ContentType.SUMMARY
class Script(BaseModel):
    title: str
    scenes: list[Scene]