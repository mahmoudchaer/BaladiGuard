from __future__ import annotations


class ContentSafetyReviewError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ContentSafetyReviewConflictError(ContentSafetyReviewError):
    def __init__(self) -> None:
        super().__init__(
            "CONTENT_SAFETY_REVIEW_CONFLICT",
            "A newer content-safety decision already exists for this generation.",
        )
