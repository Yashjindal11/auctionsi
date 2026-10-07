"""In-memory store with the same interface as the SQLite store (useful for tests)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from auctionsi.market.events import Event
from auctionsi.reputation.base import Observation


class InMemoryStore:
    def __init__(self) -> None:
        self.agents: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self.auctions: dict[str, dict[str, Any]] = {}
        self.event_log: list[Event] = []
        self.observation_log: list[Observation] = []

    def record_event(self, event: Event) -> None:
        self.event_log.append(event)

    def save_agent(self, profile: Mapping[str, Any], spec: Mapping[str, Any] | None = None) -> None:
        self.agents[profile["agent_id"]] = {**profile, "spec": dict(spec) if spec else None}

    def delete_agent(self, agent_id: str) -> bool:
        return self.agents.pop(agent_id, None) is not None

    def save_task(self, task: Mapping[str, Any]) -> None:
        self.tasks[task["task_id"]] = dict(task)

    def save_auction(self, record: Mapping[str, Any]) -> None:
        self.auctions[record["auction_id"]] = dict(record)

    def save_observation(self, observation: Observation) -> None:
        self.observation_log.append(observation)

    def events(self, auction_id: str | None = None) -> list[Event]:
        return [e for e in self.event_log if auction_id is None or e.auction_id == auction_id]

    def get_auction(self, auction_id: str) -> dict[str, Any] | None:
        return self.auctions.get(auction_id)

    def observations(self, agent_id: str | None = None) -> list[Observation]:
        return [o for o in self.observation_log if agent_id is None or o.agent_id == agent_id]
