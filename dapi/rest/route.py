from typing import Any, Dict, Final, final

import attr

__all__ = ("Route",)

BASE_URL: Final[str] = "https://discord.com/api/v10"


@final
@attr.define(init=False)
class Route:
    """Container class for routes that the http client will interact with
    contains data about the path, major parameters and the interpolated
    route.
    """

    method: str = attr.field()
    """ HTTP method the request will take """

    path: str = attr.field()
    """ The path of the Route (not interpolated with the parameters) """

    params: Dict[str, Any] = attr.field()
    """ The parameters that the route will take """

    def __init__(self, method: str, path: str, **params: Any):
        self.method = method
        self.path = path

        self.params = dict(sorted(params.items()))

    @property
    def url(self) -> str:
        """The interpolated URL of the route"""
        return BASE_URL + self.path.format_map(self.params)

    @property
    def bucket(self) -> str:
        """The ratelimit bucket that the route would fall into, as per the
        discord api docs (https://discord.com/developers/docs/topics/rate-limits)
        """
        return ":".join(map(str, self.params.values())) + ":" + self.path
