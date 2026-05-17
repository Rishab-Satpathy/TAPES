"""AITAPES Dashboard Server.

Simple HTTP server that serves the web dashboard.
Uses only Python stdlib (http.server).
"""

from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

from ..ledger import get_entries_by_type, get_recent_entries


class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for the dashboard."""

    ledger_path: str = "tapes-ledger.jsonl"

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/" or self.path == "/index.html":
            self._serve_template("index.html")
        elif self.path == "/contract":
            self._serve_contract()
        elif self.path.startswith("/api/"):
            self._handle_api()
        else:
            self._serve_static()

    def _serve_template(self, name: str) -> None:
        """Serve an HTML template."""
        template_dir = Path(__file__).parent / "templates"
        file_path = template_dir / name
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            self._send_html(content)
        else:
            self._send_error(404, f"Template not found: {name}")

    def _serve_static(self) -> None:
        """Serve static files (CSS, JS)."""
        static_dir = Path(__file__).parent / "static"
        file_path = static_dir / self.path.lstrip("/")
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            if self.path.endswith(".css"):
                self._send_response(200, content, "text/css")
            elif self.path.endswith(".js"):
                self._send_response(200, content, "application/javascript")
            else:
                self._send_response(200, content, "text/plain")
        else:
            self._send_error(404, f"File not found: {self.path}")

    def _serve_contract(self) -> None:
        """Serve the current contract as JSON."""
        contract_path = Path("tapes-contract.json")
        if contract_path.exists():
            content = contract_path.read_text(encoding="utf-8")
            self._send_response(200, content, "application/json")
        else:
            self._send_response(200, "{}", "application/json")

    def _handle_api(self) -> None:
        """Handle API requests."""
        if self.path == "/api/ledger":
            self._api_ledger()
        elif self.path == "/api/stats":
            self._api_stats()
        elif self.path.startswith("/api/ledger/"):
            entry_type = self.path.split("/")[-1]
            self._api_ledger_type(entry_type)
        else:
            self._send_error(404, "API endpoint not found")

    def _api_ledger(self) -> None:
        """Return recent ledger entries."""
        entries = get_recent_entries(self.ledger_path, 50)
        data = [
            {
                "entry_type": e.entry_type,
                "command": e.command,
                "input_hash": e.input_hash,
                "output_summary": e.output_summary,
                "timestamp": e.timestamp,
                "details": e.details or {},
            }
            for e in entries
        ]
        self._send_response(200, json.dumps(data), "application/json")

    def _api_ledger_type(self, entry_type: str) -> None:
        """Return ledger entries filtered by type."""
        entries = get_entries_by_type(self.ledger_path, entry_type)
        data = [
            {
                "entry_type": e.entry_type,
                "command": e.command,
                "input_hash": e.input_hash,
                "output_summary": e.output_summary,
                "timestamp": e.timestamp,
                "details": e.details or {},
            }
            for e in entries[-20:]
        ]
        self._send_response(200, json.dumps(data), "application/json")

    def _api_stats(self) -> None:
        """Return dashboard statistics."""
        plan_entries = get_entries_by_type(self.ledger_path, "plan")
        build_entries = get_entries_by_type(self.ledger_path, "build")
        check_entries = get_entries_by_type(self.ledger_path, "check")

        stats = {
            "total_plans": len(plan_entries),
            "total_builds": len(build_entries),
            "total_checks": len(check_entries),
            "pass_rate": 0.0,
            "avg_score": 0.0,
        }

        if check_entries:
            pass_count = sum(1 for e in check_entries if (e.details or {}).get("overall") == "pass")
            stats["pass_rate"] = pass_count / len(check_entries)
            scores = [(e.details or {}).get("score", 0) for e in check_entries]
            stats["avg_score"] = sum(scores) / len(scores) if scores else 0.0

        self._send_response(200, json.dumps(stats), "application/json")

    def _send_html(self, content: str) -> None:
        """Send HTML response."""
        self._send_response(200, content, "text/html")

    def _send_response(self, code: int, content: str, content_type: str) -> None:
        """Send a response."""
        encoded = content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_error(self, code: int, message: str) -> None:
        """Send an error response."""
        self._send_response(code, json.dumps({"error": message}), "application/json")

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass


def run_dashboard(port: int = 8501, ledger_path: str = "tapes-ledger.jsonl") -> None:
    """Run the dashboard server."""
    DashboardHandler.ledger_path = ledger_path

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"\n  AITAPES Dashboard running at http://localhost:{port}")
    print(f"  Ledger: {ledger_path}")
    print(f"  Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Dashboard stopped.")
        server.shutdown()


if __name__ == "__main__":
    run_dashboard()
