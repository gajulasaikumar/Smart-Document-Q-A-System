from enum import Enum


class DocumentStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(str, Enum):
    COMPLETED = "completed"
    ERROR = "error"


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
