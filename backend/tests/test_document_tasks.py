from app.tasks.document_tasks import process_document_task


def test_document_task_contract():
    assert process_document_task.name == "documents.process"
    assert process_document_task.max_retries == 3
