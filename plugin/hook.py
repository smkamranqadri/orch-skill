#!/usr/bin/env python3
"""Route Herdr pane lifecycle events to the owning orch."""
from __future__ import annotations

import json
import os
import sys
import time

import orchlib


NOTIFY_STATUSES = {"done", "idle", "blocked"}
QUIET_FLIP = {"done", "idle"}


def event_payload():
    event = os.environ.get("HERDR_PLUGIN_EVENT", "")
    raw = os.environ.get("HERDR_PLUGIN_EVENT_JSON", "")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid HERDR_PLUGIN_EVENT_JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("HERDR_PLUGIN_EVENT_JSON must be an object")
    if isinstance(payload.get("data"), dict):
        payload = payload["data"]
    if not event:
        event = payload.get("type", "")
        event = event.replace("_", ".") if event else ""
    return event, payload


def live_status(pane):
    response = orchlib.herdr("agent", "get", pane, check=False, return_errors=True)
    if response is None:
        return None
    error = orchlib.result(response, "error")
    if error:
        if error.get("code") in {"agent_not_found", "agent_not_running", "pane_not_found", "not_found"}:
            return None
        raise RuntimeError(f"herdr agent get failed: {error.get('message') or error.get('code') or 'unknown error'}")
    agent = orchlib.result(response, "result", "agent")
    if not agent:
        return None
    return agent.get("agent_status") or agent.get("status") or "unknown"


def notification(name, status, pane):
    return f"[orch] {name} {status} · pane {pane} · read: herdr agent read {name}"


def queue_notice(registry, orch_key, message):
    if orch_key in registry["orchs"]:
        queue = registry["orchs"][orch_key].setdefault("queue", [])
        queue[:] = orchlib.unique_messages(queue)
        if message not in queue:
            queue.append(message)


def close_agent(registry, agent, pane, *, pane_closed):
    already_closed = agent.get("agent_closed", False)
    agent.setdefault("closed_at", time.time())
    agent["status"] = "closed"
    agent["state"] = "cleanup"
    agent["agent_closed"] = True
    if pane_closed:
        agent["pane_closed"] = True
        pane_resource = f"pane:{pane}"
        if pane_resource in agent.get("created", []):
            agent["created"].remove(pane_resource)
    if not already_closed:
        queue_notice(registry, agent.get("orch"), notification(agent["name"], "closed", pane))
    orchlib.deliver(registry)


def process_event(event, payload):
    session = os.environ.get("HERDR_SESSION")
    if not session:
        raise ValueError("HERDR_SESSION is required")
    pane = payload.get("pane_id")
    if not isinstance(pane, str) or not pane:
        raise ValueError("event pane_id is required")

    prefix = session + "/"
    orch_key = prefix + pane
    with orchlib.locked() as registry:
        if event not in ("pane.agent_status_changed", "pane.closed"):
            return

        agent_key = next((key for key, agent in registry["agents"].items()
                          if key.startswith(prefix) and agent.get("pane") == pane), None)
        agent = registry["agents"].get(agent_key) if agent_key else None
        orch = registry["orchs"].get(orch_key)

        if agent and agent.get("agent_closed"):
            if event != "pane.closed" or agent.get("pane_closed"):
                return
        if agent and agent.get("state") == "closed":
            return
        if orch and orch.get("gone"):
            return
        if not agent and not orch:
            return

        if event == "pane.closed" and orch:
            orch["gone"] = True
            return

        status = None if event == "pane.closed" else live_status(pane)
        if status is None:
            if agent:
                close_agent(registry, agent, pane, pane_closed=event == "pane.closed")
            elif orch:
                orch["gone"] = True
            return

        if agent:
            previous = agent.get("status", "unknown")
            if status != previous and status in NOTIFY_STATUSES:
                if not ({previous, status} <= QUIET_FLIP):
                    queue_notice(registry, agent.get("orch"), notification(agent["name"], status, pane))
            agent["status"] = status
        elif orch:
            orch["status"] = status

        orchlib.deliver(registry)


def main():
    try:
        if not os.environ.get("HERDR_ENV"):
            raise ValueError("must run inside Herdr (HERDR_ENV is unset)")
        event, payload = event_payload()
        process_event(event, payload)
    except (OSError, ValueError, SystemExit) as exc:
        message = str(exc).strip() or exc.__class__.__name__
        print(f"orch hook: {message}", file=sys.stderr)
        return 1
    except Exception as exc:  # Herdr hooks must fail closed without a traceback.
        print(f"orch hook: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
