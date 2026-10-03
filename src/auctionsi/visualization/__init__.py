"""Optional Plotly figures (``pip install "auctionsi[plotly]"``).

Each function returns a ``plotly.graph_objects.Figure``; nothing is shown or written
unless you call ``fig.show()`` / ``fig.write_html(...)``.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from auctionsi.errors import OptionalDependencyError
from auctionsi.market.events import EventType

if TYPE_CHECKING:
    from auctionsi.experiments.runner import ExperimentResult
    from auctionsi.market.result import AuctionResult
    from auctionsi.reputation.base import ReputationSystem
    from auctionsi.simulation.market import SimulationResult


def _go() -> Any:
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise OptionalDependencyError(
            'plotting needs plotly: pip install "auctionsi[plotly]"'
        ) from exc
    return go


def bid_distribution(result: AuctionResult) -> Any:
    """Price per agent for one auction; winners highlighted, rejected bids omitted."""
    go = _go()
    winners = {a.agent_id for a in result.outcome.awards} if result.outcome else set()
    bids = sorted(result.auction.valid_bids, key=lambda b: b.price)
    fig = go.Figure(
        go.Bar(
            x=[b.agent_id for b in bids],
            y=[b.price for b in bids],
            marker_color=["#1b6e3a" if b.agent_id in winners else "#8a8a8a" for b in bids],
        )
    )
    fig.update_layout(
        title=f"Bids in {result.auction_id}", xaxis_title="agent", yaxis_title="price"
    )
    return fig


def auction_timeline(result: AuctionResult) -> Any:
    """Event timeline of one auction (simulated or wall-clock timestamps)."""
    go = _go()
    events = [e for r in result.chain() for e in r.events]
    fig = go.Figure(
        go.Scatter(
            x=[e.timestamp for e in events],
            y=[e.type.value for e in events],
            mode="markers",
            text=[e.agent_id or "" for e in events],
        )
    )
    fig.update_layout(title=f"Timeline of {result.auction_id}", xaxis_title="time")
    return fig


def market_share(sim: SimulationResult, top: int = 20) -> Any:
    go = _go()
    wins = Counter(sim.metrics.agent_wins).most_common(top)
    fig = go.Figure(go.Bar(x=[a for a, _ in wins], y=[n for _, n in wins]))
    fig.update_layout(title="Tasks won by agent", xaxis_title="agent", yaxis_title="wins")
    return fig


def price_distribution(sim: SimulationResult) -> Any:
    go = _go()
    prices = [r.awarded_price for r in sim.records if r.awarded_price is not None]
    fig = go.Figure(go.Histogram(x=prices))
    fig.update_layout(title="Winning bid prices", xaxis_title="price", yaxis_title="auctions")
    return fig


def quality_vs_price(sim: SimulationResult) -> Any:
    go = _go()
    rows = [(r.buyer_cost, r.quality) for r in sim.records if r.quality is not None]
    fig = go.Figure(go.Scatter(x=[p for p, _ in rows], y=[q for _, q in rows], mode="markers"))
    fig.update_layout(
        title="Verified quality vs buyer cost", xaxis_title="cost", yaxis_title="quality"
    )
    return fig


def reputation_vs_win_rate(
    sim: SimulationResult, reputation: ReputationSystem | None = None
) -> Any:
    go = _go()
    rep = reputation or sim.market.reputation
    bids: Counter[str] = Counter()
    for r in sim.records:
        bids.update(r.bidders)
    wins = sim.metrics.agent_wins
    xs, ys, names = [], [], []
    for agent_id, n in bids.items():
        profile = rep.profile(agent_id)
        if profile is None or profile.success_estimate is None:
            continue
        xs.append(profile.success_estimate)
        ys.append(wins.get(agent_id, 0) / n)
        names.append(agent_id)
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode="markers", text=names))
    fig.update_layout(
        title="Reputation vs win rate", xaxis_title="success estimate", yaxis_title="win rate"
    )
    return fig


def concentration_over_time(sim: SimulationResult, window: int = 100) -> Any:
    from auctionsi.simulation.metrics import concentration_over_time as hhi_series

    go = _go()
    series = hhi_series(sim.records, window)
    fig = go.Figure(go.Scatter(x=[i * window for i in range(len(series))], y=series, mode="lines"))
    fig.update_layout(
        title=f"HHI of wins per {window} tasks", xaxis_title="task", yaxis_title="HHI"
    )
    return fig


def mechanism_comparison(result: ExperimentResult, metric: str) -> Any:
    """Mean and confidence interval of ``metric`` for every experiment arm."""
    go = _go()
    summary = result.summary()
    arms = [a for a in result.arms if metric in summary.get(a, {})]
    stats = [summary[a][metric] for a in arms]
    fig = go.Figure(
        go.Bar(
            x=arms,
            y=[s.mean for s in stats],
            error_y={
                "type": "data",
                "symmetric": False,
                "array": [s.ci_high - s.mean for s in stats],
                "arrayminus": [s.mean - s.ci_low for s in stats],
            },
        )
    )
    fig.update_layout(
        title=f"{metric} by arm ({result.config.confidence:.0%} CI)", yaxis_title=metric
    )
    return fig


def event_counts(result: AuctionResult) -> dict[str, int]:
    """Plain (non-plotting) helper: how many events of each type an auction produced."""
    counts: Counter[EventType] = Counter(e.type for e in result.events)
    return {k.value: v for k, v in counts.items()}
