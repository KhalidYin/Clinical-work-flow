from __future__ import annotations

from dataclasses import dataclass

from review_panel.contracts import ReviewPanelErrorCode


@dataclass
class ReviewPanelServiceError(Exception):
    code: ReviewPanelErrorCode
    message: str
    status_code: int = 400

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


class ReviewNotFoundError(ReviewPanelServiceError):
    def __init__(self, message: str = "Review not found.") -> None:
        super().__init__(ReviewPanelErrorCode.REVIEW_NOT_FOUND, message, 404)


class QueueNotFoundError(ReviewPanelServiceError):
    def __init__(self, message: str = "Queue not found.") -> None:
        super().__init__(ReviewPanelErrorCode.QUEUE_NOT_FOUND, message, 404)


class ReviewConflictError(ReviewPanelServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(ReviewPanelErrorCode.PACKET_CHANGED, message, 409)


class ReceiptExistsError(ReviewPanelServiceError):
    def __init__(self, message: str = "DecisionReceipt already exists.") -> None:
        super().__init__(ReviewPanelErrorCode.RECEIPT_EXISTS, message, 409)


class ReviewValidationError(ReviewPanelServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(ReviewPanelErrorCode.REVIEW_INVALID, message, 422)


class PathForbiddenError(ReviewPanelServiceError):
    def __init__(self, message: str = "Path is not allowed.") -> None:
        super().__init__(ReviewPanelErrorCode.PATH_FORBIDDEN, message, 403)

