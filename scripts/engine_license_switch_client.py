"""Minimal client for calling the internal engine-license switch control service.

This script is intended to be the lightweight part that a workspace pre-script
can run. It does not talk to FME Flow Core directly. Instead, it calls the
internal control service and waits for a success/failure response.

Required environment variables:
  CONTROL_SERVICE_BASE_URL
  REMS_CONNECTION_NAME
  TARGET_REMOTE_STANDARD_ENGINES

Optional environment variables:
  CONTROL_SERVICE_SHARED_TOKEN
  TARGET_REMOTE_DYNAMIC_ENGINES
  EXPECTED_REMS_STATUS
  EXPECTED_REMS_READY
  SWITCH_TIMEOUT_SECONDS
  POLL_INTERVAL_SECONDS
  DRY_RUN
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


class ClientConfigError(RuntimeError):
    pass


class ControlServiceError(RuntimeError):
    pass


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ClientConfigError(f"Missing required environment variable: {name}")
    return value


def get_int(name: str, default: Optional[int] = None) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ClientConfigError(f"Environment variable {name} must be an integer") from exc


def get_optional_bool(name: str) -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return None
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def build_request_payload() -> Dict[str, Any]:
    target_standard = get_int("TARGET_REMOTE_STANDARD_ENGINES")
    if target_standard is None:
        raise ClientConfigError("TARGET_REMOTE_STANDARD_ENGINES must be set")

    payload: Dict[str, Any] = {
        "connectionName": get_required_env("REMS_CONNECTION_NAME"),
        "targetRemoteStandardEngines": target_standard,
        "timeoutSeconds": get_int("SWITCH_TIMEOUT_SECONDS", 180) or 180,
        "pollIntervalSeconds": get_int("POLL_INTERVAL_SECONDS", 5) or 5,
    }

    target_dynamic = get_int("TARGET_REMOTE_DYNAMIC_ENGINES")
    if target_dynamic is not None:
        payload["targetRemoteDynamicEngines"] = target_dynamic

    expected_status = os.getenv("EXPECTED_REMS_STATUS")
    if expected_status:
        payload["expectedStatus"] = expected_status

    expected_ready = get_optional_bool("EXPECTED_REMS_READY")
    if expected_ready is not None:
        payload["expectedReady"] = expected_ready

    dry_run = get_optional_bool("DRY_RUN")
    if dry_run is not None:
        payload["dryRun"] = dry_run

    return payload


def call_control_service(base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/switch"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json",
    }

    shared_token = os.getenv("CONTROL_SERVICE_SHARED_TOKEN")
    if shared_token:
        headers["Authorization"] = f"Bearer {shared_token}"

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, method="POST", headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            if not body:
                return {"ok": True}
            parsed = json.loads(body.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ControlServiceError("Unexpected non-object JSON response from control service")
            return parsed
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ControlServiceError(f"Control service returned {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise ControlServiceError(f"Failed to reach control service: {exc}") from exc


def main() -> int:
    try:
        base_url = get_required_env("CONTROL_SERVICE_BASE_URL")
        payload = build_request_payload()
        result = call_control_service(base_url, payload)
        print(json.dumps(result, sort_keys=True))
        if not result.get("ok", False):
            raise ControlServiceError(result.get("message", "Control service reported failure"))
        return 0
    except (ClientConfigError, ControlServiceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())