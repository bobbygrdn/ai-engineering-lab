class BenchmarkError(Exception):
    """Base class for benchmark and service-layer processing errors."""


class EmptyPromptError(ValueError, BenchmarkError):
    """Raised when an email prompt is empty or whitespace-only."""


class RateLimitExceededError(BenchmarkError):
    """Raised when the OpenAI API rate limits a request."""


class RefusalError(BenchmarkError):
    """Raised when the model refuses to answer."""