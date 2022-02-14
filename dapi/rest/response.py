import json as jsonlib
from typing import Any, Mapping, final

import attr

__all__ = ("Response",)


@final
@attr.define
class Response:
    """The object that represents the response that discord
    sends back after a HTTP request.
    """

    code: int = attr.field()
    """ The status code of the response """

    data: str = attr.field()
    """ The raw data of the response, probably should not be used
    directly, rather call a helper method to get the parsed data.
    """

    content_type: str = attr.field()
    """ The content-type of the respons eof the request, most
    likely application/json but could be something else.
    """

    def json(self) -> Mapping[str, Any]:
        """Returns the parsed JSON data of the response, will
        raise a `ValueError` if the content type is incorrect.
        """

        if self.content_type == "application/json":
            return jsonlib.loads(self.data)
        else:
            raise ValueError(
                f"content-type must be `application/json` not `{self.content_type}`"
            )
