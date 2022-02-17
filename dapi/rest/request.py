from typing import Any, Awaitable, Callable, Mapping

import attr

from .response import Response

__all__ = ("Request",)


@attr.define
class Request:
    """Represents a HTTP request that has not been sent
    yet. Can be used with `await` statements.
    """

    coro: Callable[..., Awaitable[Response]] = attr.field()
    """ The inner coroutine that we call """

    arguments: Mapping[str, Any] = attr.field()
    """ Arguments to pass to the coroutine """

    def __call__(self) -> Awaitable[Response]:
        return self.coro(**self.arguments)
