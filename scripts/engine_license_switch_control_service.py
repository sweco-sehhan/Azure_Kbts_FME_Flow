"""Prototype internal control service for REMS engine-license switching.

This service keeps the FME Flow Core API token out of general engine pods and
offers a narrow internal API for switching REMS Standard Engine allocation.

Environment variables:
  FME_FLOW_BASE_URL
  FME_FLOW_API_TOKEN

Optional environment variables:
  CONTROL_SERVICE_BIND_HOST      default: 0.0.0.0
  CONTROL_SERVICE_BIND_PORT      default: 8081
  CONTROL_SERVICE_SHARED_TOKEN   shared bearer token for callers
  SWITCH_TIMEOUT_SECONDS         default: 180
  POLL_INTERVAL_SECONDS          default: 5
  EXPECTED_REMS_STATUS           optional default expected status
  EXPECTED_REMS_READY            optional default expected ready flag
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from engine_license_switch import (
    ApiError,
    ConfigError,
    get_int,
    get_optional_bool,
    get_required_env,
    switch_remote_standard_engines,
)


def build_service_config() -> Dict[str, Any]:
    return {
        "base_url": get_required_env("FME_FLOW_BASE_URL"),
        "token": get_required_env("FME_FLOW_API_TOKEN"),
        "timeout_seconds": get_int("SWITCH_TIMEOUT_SECONDS", 180) or 180,
        "poll_interval_seconds": get_int("POLL_INTERVAL_SECONDS", 5) or 5,
        "expected_status": os.getenv("EXPECTED_REMS_STATUS"),
        "expected_ready": get_optional_bool("EXPECTED_REMS_READY"),
        "shared_token": os.getenv("CONTROL_SERVICE_SHARED_TOKEN"),
        "bind_host": os.getenv("CONTROL_SERVICE_BIND_HOST", "0.0.0.0"),
        "bind_port": get_int("CONTROL_SERVICE_BIND_PORT", 8081) or 8081,
    }


SERVICE_CONFIG = build_service_config()


class Handler(BaseHTTPRequestHandler):
    server_version = "EngineLicenseSwitchControlService/0.1"

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON body: {exc}") from exc
        if not isinstance(body, dict):
            raise ConfigError("JSON body must be an object")
        return body

    def _authorize(self) -> Optional[Dict[str, Any]]:
        shared_token = SERVICE_CONFIG.get("shared_token")
        if not shared_token:
            return None
        authorization = self.headers.get("Authorization", "")
        expected = f"Bearer {shared_token}"
        if authorization != expected:
            return {
                "ok": False,
                "message": "Unauthorized",
            }
        return None

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"ok": True, "status": "healthy"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        auth_error = self._authorize()
        if auth_error is not None:
            self._send_json(HTTPStatus.UNAUTHORIZED, auth_error)
            return

        if self.path != "/switch":
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})
            return

        try:
            body = self._read_json_body()
            config = {
                "base_url": SERVICE_CONFIG["base_url"],
                "token": SERVICE_CONFIG["token"],
                "connection_id": body.get("connectionId"),
                "connection_name": body.get("connectionName"),
                "target_standard": body.get("targetRemoteStandardEngines"),
                "target_dynamic": body.get("targetRemoteDynamicEngines"),
                "expected_status": body.get("expectedStatus", SERVICE_CONFIG.get("expected_status")),
                "expected_ready": body.get("expectedReady", SERVICE_CONFIG.get("expected_ready")),
                "timeout_seconds": body.get("timeoutSeconds", SERVICE_CONFIG["timeout_seconds"]),
                "poll_interval_seconds": body.get("pollIntervalSeconds", SERVICE_CONFIG["poll_interval_seconds"]),
                "dry_run": bool(body.get("dryRun", False)),
            }

            if not config["connection_id"] and not config["connection_name"]:
                raise ConfigError("connectionId or connectionName must be supplied")
            if config["target_standard"] is None:
                raise ConfigError("targetRemoteStandardEngines must be supplied")

            result = switch_remote_standard_engines(config)
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "connectionId": result.get("id"),
                    "connectionName": result.get("name"),
                    "status": result.get("status"),
                    "ready": result.get("ready"),
                    "numStandardEngines": result.get("numStandardEngines"),
                    "numDynamicEngines": result.get("numDynamicEngines"),
                },
            )
        except (ConfigError, ApiError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": str(exc)})


def main() -> int:
    bind_host = SERVICE_CONFIG["bind_host"]
    bind_port = SERVICE_CONFIG["bind_port"]
    server = ThreadingHTTPServer((bind_host, bind_port), Handler)
    print(f"Listening on http://{bind_host}:{bind_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())