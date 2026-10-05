"""Offline application lifecycle smoke test; no service or database required."""

import unittest

from jous_api.main import app


class ApplicationFoundationTests(unittest.IsolatedAsyncioTestCase):
    async def test_application_lifespan(self):
        async with app.router.lifespan_context(app):
            self.assertEqual(app.title, "Jous API")
            self.assertEqual(app.routes, [])
