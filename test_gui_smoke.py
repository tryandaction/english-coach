from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gui.server import create_app


class GuiSmokeTests(unittest.TestCase):
    def test_static_page_modules_are_served(self) -> None:
        client = TestClient(create_app())
        page_dir = Path("gui/static/pages")
        for path in page_dir.glob("*.js"):
            response = client.get(f"/static/pages/{path.name}")
            self.assertEqual(response.status_code, 200, path.name)
            self.assertTrue(response.text.strip(), path.name)

    def test_empty_state_core_routes_return_200(self) -> None:
        components = (None, None, None, None, None)
        with patch("gui.api.progress.get_components", return_value=components), patch(
            "gui.api.coach.get_components",
            return_value=components,
        ), patch(
            "gui.api.history.get_components",
            return_value=components,
        ):
            client = TestClient(create_app())
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/api/progress").status_code, 200)
            self.assertEqual(client.get("/api/coach/status").status_code, 200)
            self.assertEqual(client.get("/api/history/daily").status_code, 200)


if __name__ == "__main__":
    unittest.main()
