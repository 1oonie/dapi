import asyncio
import json as jsonlib
from typing import Any, Dict, Final, List, Optional

import aiohttp
import attr

from .. import __version__
from .errors import HTTPException, TooManyRetries
from .response import Response
from .route import Route

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

    buckets: Dict[str, asyncio.Lock] = attr.field(init=False)
    global_ratelimit: asyncio.Event = attr.field(init=False)

    def __attrs_post_init__(self):
        self.buckets: Dict[str, asyncio.Lock] = {}

        self.global_ratelimit: asyncio.Event = asyncio.Event()
        self.global_ratelimit.set()

    async def request(
        self,
        *,
        route: Route,
        json: Optional[Dict[str, Any]] = None,
        form: Optional[List[Dict[str, Any]]] = None,
        params: Optional[Dict[str, str]] = None,
        reason: Optional[str] = None,
    ) -> Response:
        """Makes a request to the provided `Route`. Provides
        the following parameters:

            `route` - the `Route` that you want to send a request
                      to.

            `json` - a dictionary of the json that you want to POST
                     to that endpoint.

            `form` - an iterable of dictionaries denoting the form
                     data (if applicable)

            `params` - the parameters to put on the end of the URL

            `reason` - the optional reason (will show up in the audit
                       log) (if the endpoint supports the `X-Audit-Log-Reason`
                       header).
        """

        def form_factory() -> aiohttp.FormData:
            assert form is not None
            # should always be true, just for the typechecker

            new = aiohttp.FormData()
            for field in form:
                new.add_field(**field)
            return new

        headers: Dict[str, str] = {
            "Authorization": "Bot " + self.token,
            "User-Agent": self.user_agent,
        }

        if form is not None:
            headers["Content-Type"] = "multipart/form-data"

            if json is not None:
                form.append({"name": "payload_json", "value": jsonlib.dumps(json)})
            json = None

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
            if form is not None:
                real_form = form_factory()
            else:
                real_form = None

            async with self.session.request(
                route.method,
                route.url,
                headers=headers,
                data=real_form,
                json=json,
                params=params,
            ) as response:
                text = await response.text(encoding="utf-8")

                if response.status == 429:
                    try:
                        data = jsonlib.loads(text)
                    except jsonlib.JSONDecodeError:
                        lock.release()
                        # TODO: raise error here
                        break

                    if data.get("global", False):
                        self.global_ratelimit.clear()

                    await asyncio.sleep(data["retry_after"])

                    if data.get("global", False):
                        self.global_ratelimit.set()
                    continue

                ratelimit_remaining = response.headers.get("X-Ratelimit-Remaining")
                if ratelimit_remaining == "0":
                    reset_after = float(response.headers.get("X-Ratelimit-Reset-After"))  # type: ignore
                    asyncio.get_event_loop().call_later(reset_after, lock.release)
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
