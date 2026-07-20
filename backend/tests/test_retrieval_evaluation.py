import pytest

from app.evaluation.retrieval import EvaluationResult, summarize


def test_evaluation_metrics_and_zero_denominators():
    cases = [
        EvaluationResult(expected={"a", "b"}, retrieved=["a", "x"], cited={"a"}, no_evidence=False),
        EvaluationResult(expected={"c"}, retrieved=["x"], cited=set(), no_evidence=True),
    ]
    summary = summarize(cases, k=2)
    assert summary.recall_at_k == pytest.approx(0.25)
    assert summary.citation_coverage == 1.0
    assert summary.no_evidence_rate == 0.5
    assert summarize([], 2).citation_coverage == 0.0
