from app.services.document_processing_service import _safe_error


def test_processing_errors_are_redacted_and_bounded():
    assert "/secret/" not in _safe_error(RuntimeError("/secret/private/file failed"))
    assert len(_safe_error(RuntimeError("x" * 1000))) == 500
