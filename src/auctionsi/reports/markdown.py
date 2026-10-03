"""Markdown reports for experiments and individual auctions.

Conclusions are generated conservatively: they describe what was observed in the
simulated environment, state uncertainty, and never generalise beyond it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from auctionsi.statistics.summary import Comparison

if TYPE_CHECKING:
    from auctionsi.experiments.runner import ExperimentResult
    from auctionsi.market.result import AuctionResult

STANDARD_LIMITATIONS = [
    "Results come from a synthetic market; agent costs, quality and reliability are "
    "drawn from the configured distributions, not measured from real agents.",
    "Agents follow fixed (or simple adaptive) bidding strategies; real strategic "
    "agents may respond to the mechanism differently.",
    "A non-significant difference is not evidence of equivalence.",
    "P-values are Holm-adjusted across the comparisons in this report only.",
]


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}g}"


def experiment_report(result: ExperimentResult) -> str:
    cfg = result.config
    m = result.manifest
    lines = [f"# Experiment report: {cfg.name}", ""]
    if cfg.description:
        lines += [cfg.description, ""]
    lines += ["## Hypothesis", "", cfg.hypothesis or "_No hypothesis was stated._", ""]
    lines += [
        "## Experimental setup",
        "",
        f"- Replications: {cfg.replications} per arm (common random numbers across arms)",
        f"- Seed: {cfg.seed}",
        f"- AuctionSI {m.get('auctionsi_version')}, Python {m.get('python_version')}, "
        f"git commit {m.get('git_commit') or 'unknown'}",
        f"- Baseline arm: `{cfg.baseline_arm()}`",
        f"- Confidence level: {cfg.confidence:.0%}; alpha: {cfg.alpha}",
        "",
        "### Parameters",
        "",
        f"- Agents: {cfg.environment.agents.model_dump()}",
        f"- Tasks: {cfg.environment.tasks.model_dump()}",
        f"- Defaults: mechanism={cfg.mechanism}, policy={cfg.policy}, "
        f"reputation={cfg.reputation}, settlement={cfg.settlement}",
        "",
        "### Arms",
        "",
    ]
    for arm in cfg.resolved_arms():
        parts = {
            k: v for k, v in arm.model_dump().items() if k != "name" and v not in (None, {}, [])
        }
        lines.append(f"- `{arm.name}`: {parts or 'experiment defaults'}")
    lines += ["", "## Results", ""]
    summary = result.summary()
    for metric in cfg.metrics:
        lines += [
            f"### {metric}",
            "",
            f"| arm | n | mean | {cfg.confidence:.0%} CI | sd | median |",
            "|---|---|---|---|---|---|",
        ]
        for arm_name in result.arms:
            s = summary.get(arm_name, {}).get(metric)
            if s is None:
                lines.append(f"| {arm_name} | 0 | n/a | n/a | n/a | n/a |")
                continue
            lines.append(
                f"| {arm_name} | {s.n} | {_fmt(s.mean)} | [{_fmt(s.ci_low)}, {_fmt(s.ci_high)}] "
                f"| {_fmt(s.sd)} | {_fmt(s.median)} |"
            )
        lines.append("")
    comparisons = result.comparisons()
    lines += ["## Statistical tests", ""]
    if comparisons:
        lines += [
            "Paired t-tests on per-replication differences (treatment - baseline). "
            "Effect size is Cohen's d_z.",
            "",
            "| metric | treatment | mean diff | CI | relative | d_z | p | p (Holm) |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for c in comparisons:
            rel = "n/a" if c.relative_diff is None else f"{c.relative_diff:+.1%}"
            lines.append(
                f"| {c.metric} | {c.treatment} | {_fmt(c.mean_diff)} | "
                f"[{_fmt(c.ci_low)}, {_fmt(c.ci_high)}] | {rel} | {_fmt(c.effect_size, 3)} | "
                f"{_fmt(c.p_value, 3)} | {_fmt(c.p_adjusted, 3)} |"
            )
    else:
        lines.append("_Only one arm (or too few replications): no comparisons were made._")
    lines += ["", "## Limitations", ""]
    lines += [f"- {x}" for x in [*cfg.limitations, *STANDARD_LIMITATIONS]]
    lines += ["", "## Conclusion", ""]
    lines += conclusions(comparisons, cfg.alpha, cfg.confidence)
    lines.append("")
    return "\n".join(lines)


def conclusions(comparisons: list[Comparison], alpha: float, confidence: float) -> list[str]:
    if not comparisons:
        return ["No comparison was run, so no conclusion is drawn."]
    out = []
    for c in comparisons:
        ci = f"{confidence:.0%} CI [{_fmt(c.ci_low)}, {_fmt(c.ci_high)}]"
        if c.significant(alpha):
            direction = "higher" if c.mean_diff > 0 else "lower"
            out.append(
                f"- In this simulated environment, `{c.treatment}` produced {direction} "
                f"`{c.metric}` than `{c.baseline}` (mean difference {_fmt(c.mean_diff)}, {ci})."
            )
        else:
            out.append(
                f"- No difference in `{c.metric}` between `{c.treatment}` and `{c.baseline}` "
                f"was detected at alpha={alpha} after Holm adjustment ({ci})."
            )
    return out


def auction_report(result: AuctionResult) -> str:
    """Everything about one auction: task, bids, rejections, scoring, contract,
    verification, settlement and trace."""
    a = result.auction
    t = a.task
    lines = [
        f"# Auction {a.auction_id}",
        "",
        f"- Task: `{t.task_id}` ({t.task_type}) budget={_fmt(t.budget)} "
        f"deadline={_fmt(t.deadline)} min_quality={_fmt(t.min_quality)} unit={t.unit}",
        f"- Mechanism: {a.mechanism}",
        f"- Final status: {result.final.status.value}",
        f"- Participants: {', '.join(a.participants) or 'none'}",
        "",
    ]
    if a.excluded:
        lines += ["## Excluded at discovery", ""]
        lines += [f"- {agent}: {'; '.join(r)}" for agent, r in a.excluded.items()]
        lines.append("")
    lines += [
        "## Valid bids",
        "",
        "| agent | price | latency | quality (claimed) | confidence | revision |",
        "|---|---|---|---|---|---|",
    ]
    for bid in a.valid_bids:
        lines.append(
            f"| {bid.agent_id} | {_fmt(bid.price)} | {_fmt(bid.estimated_latency)} | "
            f"{_fmt(bid.estimated_quality)} | {_fmt(bid.confidence)} | {bid.revision} |"
        )
    if a.rejected:
        lines += ["", "## Rejected bids", ""]
        for r in a.rejected:
            reasons = "; ".join(f"{x.code.value}: {x.message}" for x in r.reasons)
            lines.append(f"- {r.agent_id}: {reasons}")
    if result.outcome is not None:
        lines += ["", "## Selection", "", "```", result.explain(), "```"]
    for c in result.contracts:
        lines += [
            "",
            f"## Contract {c.contract.contract_id}",
            "",
            f"- Agent {c.contract.agent_id}, attempt {c.contract.attempt}, "
            f"agreed {_fmt(c.contract.agreed_price)}, payment price {_fmt(c.contract.payment_price)}",
            f"- Execution: success={c.execution.success} latency={_fmt(c.execution.latency)} "
            f"error={c.execution.error or '-'}",
            f"- Verification ({c.verification.verifier}): passed={c.verification.passed} "
            f"quality={_fmt(c.verification.quality_score)}",
        ]
        for check in c.verification.checks:
            lines.append(f"  - {check.name}: {'pass' if check.passed else 'FAIL'} ({check.detail})")
        s = c.settlement
        lines.append(
            f"- Settlement ({s.policy}): payment {_fmt(s.payment)}, bonus {_fmt(s.bonus)}, "
            f"penalty {_fmt(s.penalty)}, refund {_fmt(s.refund)} {s.unit} - {s.reason}"
        )
    trace = result.trace()
    if trace:
        lines += ["", "## Trace", "", "```", *trace, "```"]
    lines.append("")
    return "\n".join(lines)
