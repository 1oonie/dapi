import asyncio
import functools
import json as jsonlib
from typing import Any, Final, Mapping, MutableMapping, Optional

import aiohttp
import attr

from .. import __version__
from .errors import HTTPException, TooManyRetries
from .response import Response
from .route import Route
from .builders import FormBuilder, JSONBuilder, ParamsBuilder
from .request import Request

__all__ = ("RESTClient",)

USER_AGENT: Final[
    str
] = f"DiscordBot (https://github.com/AnimateShadows/dapi, {__version__})"


@attr.define(kw_only=True)
class RESTClient:
    """Client that handles HTTP request to discord's REST API,
    this does not create a session itself and needs one passed to
    it.
    """

    session: aiohttp.ClientSession = attr.field()
    """ The actual session that the client uses for its HTTP 
    requests, try not to use directly as that may mess up the
    ratelimit handling :)
    """

    token: str = attr.field()
    """ The token that the client will use for authorization, 
    it is important to note that you should not share this with
    anyone!
    """

    user_agent: str = attr.field(default=USER_AGENT)
    """ The user agent that you want to use for your HTTP client
    (recommended to use this format `DiscordBot ($url, $versionNumber)`)
    """

    buckets: MutableMapping[str, asyncio.Lock] = attr.field(init=False)
    global_ratelimit: asyncio.Event = attr.field(init=False)

    def __attrs_post_init__(self):
        self.buckets = {}

        self.global_ratelimit = asyncio.Event()

    async def request(
        self,
        *,
        route: Route,
        json: Optional[JSONBuilder] = None,
        form: Optional[FormBuilder] = None,
        params: Optional[ParamsBuilder] = None,
        reason: Optional[str] = None,
        headers: Optional[Mapping[str, Any]] = None,  # type: ignore
    ) -> Response:
        """Makes a HTTP request to the provided `Route`.

        Parameters
        ----------
        route : dapi.rest.routes.Route
            The route to request to.
        json : typing.Optional[dapi.rest.builders.JSONBuilder]
            JSON body of the request.
        form : typing.Optional[dapi.rest.builders.FormBuilder]
            The form to attach to the request.
        params : typing.Optional[dapi.rest.builders.ParamsBuilder]
            The request parameters.
        reason : typing.Optional[str]
            The reason for the request - if the endpoint supports the
            `X-Audit-Log-Reason` header.
        headers : typing.Optional[typing.Dict[builtins.str, typing.Any]]
            The headers you want to add to the request (not really
            that useful since the function will overwrite them anyway).

        Raises
        ------
        dapi.rest.errors.HTTPException
            Oh no! Something went wrong with the request, the
            exception may provide some (slightly) useful
            information as to why.
        dapi.rest.errors.TooManyRetries
            The maximum retry limit (5) has been reached.

        Returns
        -------
        dapi.rest.response.Response
            The corresponding response object denoting what
            discord sent back to us.
        """

        if headers is not None:
            headers: Mapping[str, str] = {**headers}
        else:
            headers: Mapping[str, str] = {}

        headers["Authorization"] = "Bot " + self.token
        headers["User-Agent"] = self.user_agent

        if form is not None:
            headers["Content-Type"] = "multipart/form-data"

        elif json is not None:
            headers["Content-Type"] = "application/json"

        if reason is not None:
            headers["X-Audit-Log-Reason"] = reason

        if route.bucket not in self.buckets:
            self.buckets[route.bucket] = asyncio.Lock()

        lock = self.buckets[route.bucket]
        await lock.acquire()

        await self.global_ratelimit.wait()

        for _ in range(5):
            kwargs: MutableMapping[str, Any] = {"headers": headers}
            if form is not None:
                kwargs["data"] = form.build()
            if json is not None:
                kwargs["json"] = json.build()
            if params is not None:
                kwargs["params"] = params.build()

            async with self.session.request(
                route.method, route.url, **kwargs
            ) as response:
                text = await response.text(encoding="utf-8")

                if response.status == 429:
                    try:
                        data = jsonlib.loads(text)
                    except jsonlib.JSONDecodeError:
                        lock.release()
                        raise HTTPException(response.status, text)

                    if data.get("global", False):
                        self.global_ratelimit.clear()

                    await asyncio.sleep(data["retry_after"])

                    if data.get("global", False):
                        self.global_ratelimit.set()
                    continue

                ratelimit_remaining = response.headers.get(
                    "X-Ratelimit-Remaining"
                )
                if ratelimit_remaining == "0":
                    reset_after = float(response.headers.get("X-Ratelimit-Reset-After"))  # type: ignore
                    asyncio.get_event_loop().call_later(
                        reset_after, lock.release
                    )
                else:
                    lock.release()

                if 200 <= response.status < 300:
                    return Response(
                        response.status,
                        data=text,
                        content_type=response.headers["Content-Type"],
                    )
                else:
                    try:
                        data = jsonlib.loads(text)
                    except jsonlib.JSONDecodeError:
                        data = text

                    exc = HTTPException(code=response.status, data=data)
                    raise exc

        raise TooManyRetries("maximum retry limit reached")

    def build_request(
        self,
        *,
        route: Route,
        json: Optional[JSONBuilder] = None,
        form: Optional[FormBuilder] = None,
        params: Optional[ParamsBuilder] = None,
        reason: Optional[str] = None,
        headers: Optional[Mapping[str, Any]] = None,
    ) -> Request:
        """ See the documentation for dapi.rest.client.RESTClient.request
        for information on the parameters.

        Returns
        -------
        dapi.rest.request.Request
            A request object that can be awaited later (and inspect
            the parameters).
        """

        return Request(
            self.request,
            {
                "route": route,
                "json": json,
                "form": form,
                "params": params,
                "reason": reason,
                "headers": headers,
            },
        )
