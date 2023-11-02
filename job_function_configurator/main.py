# SPDX-FileCopyrightText: 2023 Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
import structlog
from structlog.contextvars import bound_contextvars
from fastapi import APIRouter
from fastapi import FastAPI
from fastramqpi.main import FastRAMQPI
from ramqp.depends import RateLimit
from ramqp.mo import MORouter
from ramqp.mo import PayloadUUID

from job_function_configurator.autogenerated_graphql_client import GraphQLClient
from job_function_configurator import depends
from job_function_configurator.config import get_settings
from job_function_configurator.log import setup_logging
from job_function_configurator.process_events import process_engagement_events

amqp_router = MORouter()
fastapi_router = APIRouter()

logger = structlog.get_logger(__name__)


@amqp_router.register("engagement")
async def listener(
    engagement_uuid: PayloadUUID, _: RateLimit, mo: depends.GraphQLClient
) -> None:
    """
    This function listens on changes made to:
    ServiceType - engagements
    ObjectType - job function

    We receive a payload, of type PayloadUUID, with content of:
    engagement_uuid - UUID of the engagement.

    Args:
        engagement_uuid: UUID of the engagement
        mo: A GraphQL client to perform the various queries
        _: A dependency injected rate limiter
    """
    with bound_contextvars(engagement_uuid=engagement_uuid):
        await process_engagement_events(mo, engagement_uuid)


def create_fastramqpi(**kwargs) -> FastRAMQPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    fastramqpi = FastRAMQPI(
        application_name="os2mo-job-function-configurator",
        settings=settings,
        graphql_client_cls=GraphQLClient,
    )

    amqpsystem = fastramqpi.get_amqpsystem()
    amqpsystem.router.registry.update(amqp_router.registry)

    app = fastramqpi.get_app()
    app.include_router(fastapi_router)

    return fastramqpi


def create_app(**kwargs) -> FastAPI:
    fastramqpi = create_fastramqpi(**kwargs)
    return fastramqpi.get_app()
