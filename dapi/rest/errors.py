from typing import Any, Dict, List, Optional, Tuple, Union

import attr

__all__ = ("ClientException", "HTTPException", "TooManyRetries")


class ItemsList(list):
    def items(self):
        for n, item in enumerate(self):
            yield str(n), item


def flatten(
    d: Union[Dict[str, Any], ItemsList], path: Optional[str] = None
) -> List[Tuple[str, Tuple[str, str]]]:
    if path is None:
        path = ""

    items: List[Tuple[str, Tuple[str, str]]] = []
    for k, v in d.items():
        if k == "_errors":
            for item in v:
                items.append((path[1:], (item["message"], item["code"])))
        if isinstance(v, dict):
            items.extend(flatten(v, path + ":" + k))
        elif isinstance(v, list):
            items.extend(flatten(ItemsList(v), path + ":" + k))
    return items


class ClientException(Exception):
    """Base class for HTTP client exceptions"""


@attr.define(init=False, repr=False)
class HTTPException(ClientException):
    """Base class for errors that were encountered when making
    a HTTP request through the client. The status code and response
    data is included.
    """

    code: int = attr.field()
    """ The HTTP status code """

    data: Union[str, Dict[str, Any]] = attr.field()
    """ The actual data of the request """

    def __init__(self, code: int, data: Union[str, Dict[str, Any]]):
        self.code = code
        self.data = data

        super().__init__(repr(self))

    @property
    def message(self) -> Optional[str]:
        """Error message sent by discord"""

        if isinstance(self.data, dict):
            return self.data.get("message")

    @property
    def errno(self) -> Optional[int]:
        """The error code (not actually that useful)"""

        if isinstance(self.data, dict):
            return self.data.get("code")

    @property
    def errors(self) -> Optional[str]:
        """Returns the prettified error messages (discord sends them
        very strangely for some reason.
        """

        if isinstance(self.data, dict):
            if "errors" not in self.data:
                return None

            text = "\n".join(
                f"{item} ({code}): {message}"
                for item, (message, code) in flatten(self.data["errors"])
            )
            return text.strip()
        else:
            return self.data

    def __repr__(self) -> str:
        return f"{self.message} ({self.errno})\n{self.errors}"


class TooManyRetries(Exception):
    """Raised when the maximum retry depth (5) is reached"""
