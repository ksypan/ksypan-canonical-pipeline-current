import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from pipeline.llm_client import LLMClientError
from pipeline.processor import process_epicrisis
from .schemas import DocumentResponse, DocumentSummary, EpicrisisRequest, EpicrisisResponse

router = APIRouter()


@router.post("/extract", response_model=EpicrisisResponse)
def extract(request: EpicrisisRequest) -> EpicrisisResponse:
    try:
        return EpicrisisResponse(result=process_epicrisis(request.text))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _data_dirs() -> tuple[Path, Path, Path]:
    return (
        Path(os.getenv("EPICRISIS_SOURCE_DIR", "input")),
        Path(os.getenv("EPICRISIS_RESULT_DIR", "result__test")),
        Path(os.getenv("EPICRISIS_EVIDENCE_DIR", "evidence__test")),
    )


@router.get("/documents", response_model=list[DocumentSummary])
def documents() -> list[DocumentSummary]:
    _, result_dir, evidence_dir = _data_dirs()
    stems = {path.stem for path in result_dir.glob("*.json") if path.is_file()}
    stems &= {path.name.removesuffix(".evidence__test") for path in evidence_dir.glob("*.evidence__test.json") if path.is_file()}
    return [DocumentSummary(document=stem) for stem in sorted(stems)]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def document(document_id: str) -> DocumentResponse:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", document_id):
        raise HTTPException(status_code=400, detail="invalid document id")
    source_dir, result_dir, evidence_dir = _data_dirs()
    result_path = result_dir / f"{document_id}.json"
    evidence_path = evidence_dir / f"{document_id}.evidence__test.json"
    text_path = evidence_dir / "text" / f"{document_id}.md"
    if not result_path.is_file() or not evidence_path.is_file() or not text_path.is_file():
        raise HTTPException(status_code=404, detail="document not found")
    return DocumentResponse(
        document=document_id,
        text=text_path.read_text(encoding="utf-8"),
        result=json.loads(result_path.read_text(encoding="utf-8")),
        evidence=json.loads(evidence_path.read_text(encoding="utf-8")),
    )
