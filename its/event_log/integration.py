from fastapi import FastAPI

from its.event_log.middleware import EventLogMiddleware
from its.event_log.storage import ensure_event_log_schema


def install_event_log(app: FastAPI, *, service_name: str) -> None:
    app.router.add_event_handler("startup", ensure_event_log_schema)
    app.add_middleware(EventLogMiddleware, service_name=service_name)
