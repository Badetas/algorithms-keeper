import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, MutableMapping

from aiohttp import ClientSession, web
from cachetools import LRUCache
from gidgethub.sansio import Event
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from algorithms_keeper.api import GitHubAPI
from algorithms_keeper.constants import SOURCE_CODE_URL
from algorithms_keeper.event import main_router

cache: MutableMapping[Any, Any] = LRUCache(maxsize=500)

sentry_init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[AioHttpIntegration(transaction_style="method_and_path_pattern")],
)

logging.basicConfig(
    format="[%(levelname)s] %(message)s",
    level=os.environ.get("LOG_LEVEL", "INFO"),
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__package__)

routes = web.RouteTableDef()


@routes.get("/")
async def index(_: web.Request) -> web.Response:
    return web.HTTPFound(location=SOURCE_CODE_URL)


@routes.get("/health")
async def health(_: web.Request) -> web.Response:
    return web.Response(status=200, text="OK")


@routes.post("/")
async def main(request: web.Request) -> web.Response:
    try:
        body = await request.read()
        secret = os.environ.get("GITHUB_SECRET")
        event = Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            return web.Response(status=200)
        logger.info(
            "event=%s delivery_id=%s",
            f"{event.event}:{event.data['action']}",
            event.delivery_id,
        )
        async with ClientSession() as session:
            gh = GitHubAPI(
                event.data["installation"]["id"],
                session,
                "dhruvmanila/algorithms-keeper",
                cache=cache,
            )
            # Give GitHub some time to reach internal consistency.
            await asyncio.sleep(1)
            await main_router.dispatch(event, gh)
        if gh.rate_limit is not None:  # pragma: no cover
            logger.info(
                "ratelimit=%s, time_remaining=%s",
                f"{gh.rate_limit.remaining}/{gh.rate_limit.limit}",
                gh.rate_limit.reset_datetime - datetime.now(timezone.utc),
            )
        return web.Response(status=200)
    except Exception as err:
        logger.exception(err)
        return web.Response(status=500, text=str(err))


if __name__ == "__main__":  # pragma: no cover
    app = web.Application()
    app.add_routes(routes)
    # Heroku dynamically assigns the app a port, so we can't set the port to a fixed
    # number. Heroku adds the port to the env, so we need to pull it from there.
    web.run_app(app, port=int(os.environ.get("PORT", 5000)))
