"""Offline application lifecycle smoke test; no service or database required."""

import unittest

from jous_api.config import Settings
from jous_api.main import create_app


class ApplicationFoundationTests(unittest.IsolatedAsyncioTestCase):
    async def test_application_lifespan(self):
        app = create_app(Settings(environment="test", service_name="Jous_API"))
        async with app.router.lifespan_context(app):
            self.assertEqual(app.title, "Jous_API")
            self.assertEqual([route.path for route in app.routes], ["/health/live"])
