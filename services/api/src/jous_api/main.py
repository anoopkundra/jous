"""Application boundary only; transport and domain behavior arrive later."""

from fastapi import FastAPI

app = FastAPI(
    title="Jous API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
