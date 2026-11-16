"""Additive product composition. Start with uvicorn ... --factory."""
from .main import create_app
from .product_api import router


def create_product_app(settings=None):
    app = create_app(settings)
    app.include_router(router)

    @app.middleware("http")
    async def private_product_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    return app
