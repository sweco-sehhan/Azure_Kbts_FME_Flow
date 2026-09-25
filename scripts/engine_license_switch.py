"""Prototype pre-script for switching REMS Standard Engine allocation.

This script is intended to run before selected workspaces and talk to
FME Flow Core through REST API v4. It updates the configured number of
Standard Engines on a Remote Engine Services connection and polls until
the expected state is reached.

Required environment variables:
  FME_FLOW_BASE_URL
  FME_FLOW_API_TOKEN
  REMS_CONNECTION_NAME or REMS_CONNECTION_ID
  TARGET_REMOTE_STANDARD_ENGINES

Recommended baseline:
    TARGET_REMOTE_STANDARD_ENGINES=1

Use TARGET_REMOTE_STANDARD_ENGINES=0 only when explicitly switching to a
temporary `2+0` mode where AKS reclaims the REMS Standard Engine allocation.

Optional environment variables:
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
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, Optional


class ConfigError(RuntimeError):
    pass


class ApiError(RuntimeError):
    pass


def parse_runtime_config() -> Dict[str, Any]:
    base_url = get_required_env("FME_FLOW_BASE_URL")
    token = get_required_env("FME_FLOW_API_TOKEN")
    connection_id = os.getenv("REMS_CONNECTION_ID")
    connection_name = os.getenv("REMS_CONNECTION_NAME")
    target_standard = get_int("TARGET_REMOTE_STANDARD_ENGINES")
    if target_standard is None:
        raise ConfigError("TARGET_REMOTE_STANDARD_ENGINES must be set")

    return {
        "base_url": base_url,
        "token": token,
        "connection_id": connection_id,
        "connection_name": connection_name,
        "target_standard": target_standard,
        "target_dynamic": get_int("TARGET_REMOTE_DYNAMIC_ENGINES"),
        "expected_status": os.getenv("EXPECTED_REMS_STATUS"),
        "expected_ready": get_optional_bool("EXPECTED_REMS_READY"),
        "timeout_seconds": get_int("SWITCH_TIMEOUT_SECONDS", 180) or 180,
        "poll_interval_seconds": get_int("POLL_INTERVAL_SECONDS", 5) or 5,
        "dry_run": get_optional_bool("DRY_RUN") or False,
    }


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def get_optional_bool(name: str) -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return None
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_int(name: str, default: Optional[int] = None) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc


def join_url(base_url: str, path: str, query: Optional[Dict[str, Any]] = None) -> str:
    normalized = base_url.rstrip("/") + "/" + path.lstrip("/")
    if query:
        normalized += "?" + urllib.parse.urlencode(query)
    return normalized


def api_request(
    base_url: str,
    token: str,
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
) -> Any:
    url = join_url(base_url, path, query=query)
    data = None
    headers = {
        "Authorization": f"fmetoken token={token}",
        "Accept": "application/json",
    }

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=UTF-8"

    request = urllib.request.Request(url=url, data=data, method=method.upper(), headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            if not payload:
                return None
            return json.loads(payload.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"API {method} {path} failed with {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"API {method} {path} failed to reach FME Flow Core: {exc}") from exc


def iter_results(page: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for key in ("items", "results"):
        value = page.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item


def get_remote_engine_connection(
    base_url: str,
    token: str,
    connection_id: Optional[str],
    connection_name: Optional[str],
) -> Dict[str, Any]:
    if connection_id:
        response = api_request(base_url, token, "GET", f"/fmeapiv4/remoteengines/{connection_id}")
        if not isinstance(response, dict):
            raise ApiError("Unexpected response while reading REMS connection by ID")
        return response

    if not connection_name:
        raise ConfigError("Either REMS_CONNECTION_ID or REMS_CONNECTION_NAME must be set")

    page = api_request(base_url, token, "GET", "/fmeapiv4/remoteengines", query={"limit": 1000, "offset": 0})
    if not isinstance(page, dict):
        raise ApiError("Unexpected response while listing REMS connections")

    for item in iter_results(page):
        if item.get("name") == connection_name:
            return item

    raise ApiError(f"Could not find REMS connection named {connection_name}")


def build_update_payload(connection: Dict[str, Any], target_standard: int, target_dynamic: Optional[int]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": connection.get("type", "standard"),
        "name": connection["name"],
        "url": connection["url"],
        "username": connection["username"],
        "queues": connection.get("queues", []),
        "numStandardEngines": target_standard,
        "numDynamicEngines": target_dynamic if target_dynamic is not None else connection.get("numDynamicEngines", 0),
    }

    proxy_configuration = connection.get("proxyConfiguration")
    if proxy_configuration:
        payload["proxyConfiguration"] = proxy_configuration

    return payload


def desired_state_reached(connection: Dict[str, Any], target_standard: int, expected_status: Optional[str], expected_ready: Optional[bool]) -> bool:
    if connection.get("numStandardEngines") != target_standard:
        return False

    if expected_status and connection.get("status") != expected_status:
        return False

    if expected_ready is not None and connection.get("ready") != expected_ready:
        return False

    return True


def log_connection_state(prefix: str, connection: Dict[str, Any]) -> None:
    print(
        json.dumps(
            {
                "message": prefix,
                "id": connection.get("id"),
                "name": connection.get("name"),
                "status": connection.get("status"),
                "ready": connection.get("ready"),
                "numStandardEngines": connection.get("numStandardEngines"),
                "numDynamicEngines": connection.get("numDynamicEngines"),
            },
            sort_keys=True,
        )
    )


def switch_remote_standard_engines(config: Dict[str, Any]) -> Dict[str, Any]:
    base_url = config["base_url"]
    token = config["token"]
    target_standard = config["target_standard"]
    target_dynamic = config.get("target_dynamic")
    expected_status = config.get("expected_status")
    expected_ready = config.get("expected_ready")
    timeout_seconds = config.get("timeout_seconds", 180)
    poll_interval_seconds = config.get("poll_interval_seconds", 5)
    dry_run = config.get("dry_run", False)

    connection = get_remote_engine_connection(
        base_url,
        token,
        config.get("connection_id"),
        config.get("connection_name"),
    )
    connection_id = connection.get("id")
    if not connection_id:
        raise ApiError("REMS connection does not contain an id")

    log_connection_state("current REMS connection state", connection)

    if desired_state_reached(connection, target_standard, expected_status, expected_ready):
        print("Requested REMS state is already active; no update required.")
        return connection

    payload = build_update_payload(connection, target_standard, target_dynamic)

    if dry_run:
        print(json.dumps({"message": "dry-run only", "payload": payload}, sort_keys=True))
        return connection

    api_request(base_url, token, "PUT", f"/fmeapiv4/remoteengines/{connection_id}", body=payload)

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        current = get_remote_engine_connection(base_url, token, connection_id, None)
        log_connection_state("polled REMS connection state", current)
        if desired_state_reached(current, target_standard, expected_status, expected_ready):
            print("Requested REMS state reached.")
            return current
        time.sleep(poll_interval_seconds)

    raise ApiError(
        "Timed out waiting for REMS connection to reach the requested state. "
        f"Expected numStandardEngines={target_standard}, status={expected_status!r}, ready={expected_ready!r}."
    )


def main() -> int:
    try:
        config = parse_runtime_config()
        switch_remote_standard_engines(config)
        return 0
    except (ConfigError, ApiError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())