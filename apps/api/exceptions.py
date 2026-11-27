from typing import Any


class StructuredHTTPException(Exception):
    """HTTP exception whose JSON body is returned verbatim at top level."""

    def __init__(self, status_code: int, content: dict[str, Any]) -> None:
        super().__init__(content.get("detail", "HTTP Error"))
        self.status_code = status_code
        self.content = content
