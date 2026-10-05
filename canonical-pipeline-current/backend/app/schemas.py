from pydantic import BaseModel, Field


class EpicrisisRequest(BaseModel):
    text: str = Field(min_length=1)


class EpicrisisResponse(BaseModel):
    result: dict


class DocumentSummary(BaseModel):
    document: str


class DocumentResponse(BaseModel):
    document: str
    text: str
    result: dict
    evidence: dict
