from __future__ import annotations

import random

import pytest

from auctionsi.bidding import BanditMarkup, BidInputs
from auctionsi.core import AuctionNotice, Task
from auctionsi.errors import ValidationError
from auctionsi.mechanisms import FirstPriceReverseAuction, SecondPriceReverseAuction
from auctionsi.simulation import generate_agents, generate_tasks, simulate_market
from auctionsi.simulation.agents import agent_from_spec


def inputs(task_id: str, rng: random.Random) -> BidInputs:
    task = Task(task_id=task_id, task_type="x", budget=10.0)
    return BidInputs(task=task, cost=1.0, quality=0.9, latency=1.0, reliability=1.0, rng=rng)


def test_ucb_tries_every_arm_then_exploits() -> None:
    bandit = BanditMarkup(markups=(0.0, 0.5, 1.0))
    rng = random.Random(0)
    prices = []
    for i in range(30):
        inp = inputs(f"t{i}", rng)
        price = bandit.price(inp)
        assert price is not None
        prices.append(price)
        # A buyer who accepts anything below 1.6: markup 0.5 is the best arm.
        won = price < 1.6
        bandit.observe(AuctionNotice("a", inp.task, None, won, price if won else None, None))
    assert prices[:3] == [1.0, 1.5, 2.0]
    assert bandit.preferred_markup() == 0.5
    assert prices[-5:].count(1.5) >= 4


def test_epsilon_greedy_is_seeded_and_validated() -> None:
    def run(seed: int) -> list[float]:
        bandit = BanditMarkup(algorithm="epsilon_greedy", epsilon=0.3)
        rng = random.Random(seed)
        out = []
        for i in range(20):
            inp = inputs(f"t{i}", rng)
            p = bandit.price(inp)
            assert p is not None
            out.append(p)
            bandit.observe(AuctionNotice("a", inp.task, None, True, p, None))
        return out

    assert run(1) == run(1)
    assert BanditMarkup().preferred_markup() is None
    with pytest.raises(ValidationError):
        BanditMarkup(markups=())
    with pytest.raises(ValidationError):
        BanditMarkup(algorithm="thompson")


def test_bandit_spec_round_trips_through_agent_specs() -> None:
    agent = generate_agents(1, seed=1, strategy={"name": "bandit", "markups": [0.1, 0.2]})[0]
    rebuilt = agent_from_spec(agent.spec())
    assert isinstance(rebuilt.strategy, BanditMarkup)
    assert rebuilt.strategy.markups == (0.1, 0.2)


@pytest.mark.integration
def test_learning_bidders_shade_less_under_second_price() -> None:
    """Under second price the payment does not depend on your own bid, so learners
    that only see profit should settle on lower markups than under first price."""

    def market(mechanism: object) -> float:
        opts = {
            "strategy": "bandit",
            "capability_distribution": "generalist",
            "capabilities": ["x"],
        }
        agents = generate_agents(8, seed=3, **opts)  # type: ignore[arg-type]
        tasks = generate_tasks(600, seed=3, task_types=["x"], budget_distribution=1.0)
        result = simulate_market(agents, tasks, mechanism=mechanism)  # type: ignore[arg-type]
        markup = result.metrics.average_winning_markup
        assert markup is not None
        return markup

    assert market(SecondPriceReverseAuction()) < market(FirstPriceReverseAuction())
