import argparse
import json
import platform
import sys
import time

import urllib.error
import urllib.request

SAFE_ACTIONS = {"status_check", "inventory_sync"}


def _post(base_url, path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url}{path}", data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def _get(base_url, path, token):
    request = urllib.request.Request(
        f"{base_url}{path}", headers={"Authorization": f"Bearer {token}"}, method="GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def enroll(base_url, enrollment_token):
    result = _post(
        base_url,
        "/api/v1/agent/enroll",
        {
            "enrollment_token": enrollment_token,
            "agent_version": "reference-1.0",
            "reported_os": platform.platform(),
        },
    )
    return result["agent_token"], result["device_id"]


def execute(action_type, params):
    if action_type in SAFE_ACTIONS:
        return True, json.dumps({"platform": platform.platform(), "python": sys.version}), ""
    return True, f"Simulated '{action_type}' -- reference agent never performs destructive actions.", ""


def run_once(base_url, agent_token):
    task = _get(base_url, "/api/v1/agent/tasks/next", agent_token)
    if task is None:
        return False

    success, result, error = execute(task["action_type"], json.loads(task.get("params", "{}") or "{}"))
    _post(
        base_url,
        f"/api/v1/agent/tasks/{task['id']}/result",
        {"success": success, "result": result, "error_message": error},
        token=agent_token,
    )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--enrollment-token")
    parser.add_argument("--agent-token")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()

    agent_token = args.agent_token
    if agent_token is None:
        if not args.enrollment_token:
            print("Provide --enrollment-token (first run) or --agent-token (subsequent runs).")
            raise SystemExit(1)
        agent_token, device_id = enroll(args.base_url, args.enrollment_token)
        print(f"Enrolled. device_id={device_id}")
        print(f"agent_token={agent_token}")
        print("Save this token -- it is not retrievable again.")

    if args.once:
        found = run_once(args.base_url, agent_token)
        print("Task executed." if found else "No pending task.")
        return

    while True:
        run_once(args.base_url, agent_token)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
