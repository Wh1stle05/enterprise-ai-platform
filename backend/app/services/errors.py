"""Standardized error envelope shared by FastAPI exception handlers."""

# HTTP 状态码到标准错误码的映射（与 vllm-aichatsystem 对齐）。
# 422 属于请求校验失败，与 400 一样归为 invalid_request；
# 未覆盖的状态码兜底 internal_error。
STATUS_CODE_TO_ERROR_CODE: dict[int, str] = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "invalid_request",
    429: "rate_limit_exceeded",
    500: "internal_error",
    502: "upstream_error",
    503: "service_unavailable",
}


def error_code_for_status(status_code: int, code: str | None = None) -> str:
    """显式 code 优先：有些错误码无法仅凭状态码推断，必须由调用方显式传入。"""
    if code:
        return code
    return STATUS_CODE_TO_ERROR_CODE.get(status_code, "internal_error")


def build_error_payload(
    status_code: int,
    message: str,
    request_id: str | None,
    code: str | None = None,
) -> dict[str, object]:
    return {
        "error": {
            "code": error_code_for_status(status_code, code),
            "message": message,
            "request_id": request_id,
        }
    }
