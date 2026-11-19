"""Additive product composition. Start with uvicorn ... --factory."""
from .main import create_app
from .product_api import router
from .task_api import router as task_router
from .database import Database
from .product_runtime_validation import validate_product_runtime
from .task_service import SQLTaskStore
from .execution_service import ExecutionService
from jous_supply.hugging_face import HuggingFaceAdapter


def create_product_app(settings=None):
    app = create_app(settings, database_factory=lambda settings: Database(settings, validator=validate_product_runtime))
    app.include_router(router)
    app.include_router(task_router)
    app.state.task_execution = ExecutionService(SQLTaskStore(app.state.database), HuggingFaceAdapter())

    @app.middleware("http")
    async def private_product_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    return app
