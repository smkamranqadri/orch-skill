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
DEBOUNCE_SECONDS = float(os.environ.get("ORCH_DEBOUNCE_SECONDS", "15"))


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


def live_agent(pane):
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
    return agent


def matching_agent(registry, prefix, pane):
    matches = [(key, agent) for key, agent in registry["agents"].items()
               if key.startswith(prefix) and agent.get("pane") == pane]
    active = [(key, agent) for key, agent in matches
              if agent.get("state") != "closed" and not agent.get("agent_closed")]
    candidates = active or matches
    return max(reversed(candidates), key=lambda item: item[1].get("since", 0), default=(None, None))


def notification(name, status, pane):
    return f"[orch] {name} {status} · pane {pane} · read: herdr agent read {name}"


def queue_notice(registry, orch_key, message):
    if orch_key in registry["orchs"]:
        queue = registry["orchs"][orch_key].setdefault("queue", [])
        queue[:] = orchlib.unique_messages(queue)
        if message not in queue:
            queue.append(message)


def sequence_value(info, key):
    value = info.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def queue_terminal_notice(registry, agent, status, pane):
    if not agent.get("turn_open"):
        return False
    queue_notice(registry, agent.get("orch"), notification(agent["name"], status, pane))
    agent["turn_open"] = False
    return True


def debounce_terminal_notice(agent_key, pane, snapshot_state_seq):
    time.sleep(DEBOUNCE_SECONDS)
    info = live_agent(pane)
    status = None if info is None else info.get("agent_status") or info.get("status")
    if status not in QUIET_FLIP:
        return
    completion_seq = sequence_value(info, "completion_seq")
    state_change_seq = sequence_value(info, "state_change_seq")
    with orchlib.locked() as registry:
        agent = registry["agents"].get(agent_key)
        if not agent or agent.get("pane") != pane or agent.get("state") == "closed" or agent.get("agent_closed"):
            return
        if not agent.get("sequence_capable"):
            return
        seen_state_seq = agent.get("seen_state_seq")
        if snapshot_state_seq is not None and seen_state_seq is not None and seen_state_seq > snapshot_state_seq:
            return
        observed_state = sequence_value(info, "state_change_seq")
        observed_completion = sequence_value(info, "completion_seq")
        if observed_state is not None and seen_state_seq is not None and observed_state < seen_state_seq:
            agent["seen_state_seq"] = observed_state
            agent["seen_completion_seq"] = observed_completion
        if observed_completion is not None and agent.get("seen_completion_seq") is not None and observed_completion < agent["seen_completion_seq"]:
            agent["seen_completion_seq"] = observed_completion
        elif observed_completion is not None and (agent.get("seen_completion_seq") is None or observed_completion > agent["seen_completion_seq"]):
            agent["seen_completion_seq"] = observed_completion
        if observed_state is not None:
            agent["seen_state_seq"] = observed_state
        agent["status"] = status
        queue_terminal_notice(registry, agent, status, pane)
        orchlib.deliver(registry)


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
    debounce_key = None
    debounce_state_seq = None
    with orchlib.locked() as registry:
        if event not in ("pane.agent_status_changed", "pane.closed"):
            return

        agent_key, agent = matching_agent(registry, prefix, pane)
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

        info = None if event == "pane.closed" else live_agent(pane)
        status = None if info is None else info.get("agent_status") or info.get("status") or "unknown"
        if status is None:
            if agent:
                close_agent(registry, agent, pane, pane_closed=event == "pane.closed")
            elif orch:
                orch["gone"] = True
            return

        if agent:
            previous = agent.get("status", "unknown")
            if info and any(field in info for field in ("state_change_seq", "completion_seq")):
                agent["sequence_capable"] = True
            completion_seq = sequence_value(info or {}, "completion_seq")
            state_change_seq = sequence_value(info or {}, "state_change_seq")
            if agent.get("sequence_capable"):
                agent.setdefault("turn_open", previous == "working")
                agent.setdefault("seen_state_seq", agent.get("state_change_seq"))
                agent.setdefault("seen_completion_seq", agent.get("completion_seq"))
                seen_state = agent.get("seen_state_seq")
                seen_completion = agent.get("seen_completion_seq")
                restarted = ((state_change_seq is not None and seen_state is not None and state_change_seq < seen_state)
                             or (completion_seq is not None and seen_completion is not None and completion_seq < seen_completion))
                rising_completion = completion_seq is not None and (seen_completion is None or completion_seq > seen_completion)
                if restarted:
                    agent["seen_state_seq"] = state_change_seq
                    agent["seen_completion_seq"] = completion_seq
                    rising_completion = False
                else:
                    if state_change_seq is not None:
                        agent["seen_state_seq"] = state_change_seq
                    if completion_seq is not None:
                        agent["seen_completion_seq"] = completion_seq
                if status == "working":
                    agent["turn_open"] = True
            if status in NOTIFY_STATUSES:
                if status == "blocked":
                    if status != previous:
                        queue_notice(registry, agent.get("orch"), notification(agent["name"], status, pane))
                elif agent.get("sequence_capable"):
                    if agent.get("turn_open") and rising_completion:
                        queue_terminal_notice(registry, agent, status, pane)
                    elif agent.get("turn_open"):
                        debounce_key = agent_key
                        debounce_state_seq = state_change_seq
                elif status != previous:
                    # Older Herdr and adopted agents without a sequence baseline keep the legacy status-change behavior.
                    if not ({previous, status} <= QUIET_FLIP):
                        queue_notice(registry, agent.get("orch"), notification(agent["name"], status, pane))
            if completion_seq is not None and (agent.get("completion_seq") is None or completion_seq < agent["completion_seq"] or completion_seq > agent["completion_seq"]):
                agent["completion_seq"] = completion_seq
            if state_change_seq is not None and (agent.get("state_change_seq") is None or state_change_seq < agent["state_change_seq"] or state_change_seq > agent["state_change_seq"]):
                agent["state_change_seq"] = state_change_seq
            agent["status"] = status
        elif orch:
            orch["status"] = status

        orchlib.deliver(registry)
    if debounce_key:
        debounce_terminal_notice(debounce_key, pane, debounce_state_seq)


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
