import json
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationCase(BaseModel):
    question: str = Field(min_length=1)
    knowledge_base_id: UUID
    expected_chunk_ids: list[UUID] = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1)


@dataclass(frozen=True)
class EvaluationResult:
    expected: set[str]
    retrieved: list[str]
    cited: set[str]
    no_evidence: bool


@dataclass(frozen=True)
class EvaluationSummary:
    query_count: int
    recall_at_k: float
    citation_coverage: float
    no_evidence_rate: float


def load_cases(path: Path) -> list[EvaluationCase]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(EvaluationCase.model_validate(json.loads(line)))
    return cases


def summarize(cases: list[EvaluationResult], k: int) -> EvaluationSummary:
    if not cases:
        return EvaluationSummary(0, 0.0, 0.0, 0.0)
    recalls = [len(case.expected & set(case.retrieved[:k])) / len(case.expected) for case in cases]
    answered = [case for case in cases if not case.no_evidence]
    covered = [case for case in answered if case.cited & case.expected]
    return EvaluationSummary(
        len(cases), sum(recalls) / len(recalls), len(covered) / len(answered) if answered else 0.0,
        sum(case.no_evidence for case in cases) / len(cases),
    )


async def evaluate(cases, *, searcher: Callable[..., Awaitable], answerer: Callable[..., Awaitable], top_k: int) -> list[EvaluationResult]:
    results = []
    for case in cases:
        retrieved = await searcher(case, top_k=case.top_k or top_k)
        answer = await answerer(case, top_k=case.top_k or top_k)
        results.append(EvaluationResult(
            expected={str(item) for item in case.expected_chunk_ids},
            retrieved=[str(item.chunk_id) for item in retrieved],
            cited={str(item.chunk_id) for item in answer.citations},
            no_evidence=answer.no_evidence,
        ))
    return results
