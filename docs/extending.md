# Writing custom agents, verifiers and plugins

## An agent

```python
from auctionsi import Agent, BidProposal, ExecutionResult, Marketplace, Task

class SummariserAgent(Agent):
    def bid(self, task, context):
        if len(task.description) > 5_000:
            return None                      # abstain
        return BidProposal(price=0.03, estimated_latency=2.0, estimated_quality=0.9)

    def execute(self, task, contract):
        summary = task.description[:100]
        return ExecutionResult(success=True, output={"summary": summary}, latency=0.1)

market = Marketplace()
market.register(SummariserAgent("summariser-1", capabilities=["summarization"]))
result = market.submit_task(Task(task_id="t1", task_type="summarization", description="..."))
print(result.explain())
```

Optional hooks: `revise_bid(task, view)` for open auctions and `observe(notice)` to
learn from outcomes. For one-off functions use `PythonFunctionAgent`.

Ready-made adapters: `HTTPAgent` (JSON `POST /bid` and `/execute`; no redirects,
timeouts, response size limit, bearer token read from an env var),
`OpenAICompatibleAgent` (any `/chat/completions` server, local or hosted; optional)
and `HumanAgent` (prompts a person).

**Security:** the marketplace never runs agent-supplied code. Agents run in your
process only if *you* wrote them; anything else should sit behind `HTTPAgent` or
your own sandboxed adapter.

## A verifier

```python
from auctionsi.verification import CheckResult, VerificationResult, Verifier

class WordLimit(Verifier):
    name = "word_limit"
    def __init__(self, limit): self.limit = limit
    def verify(self, output, contract, task):
        words = len(str(output.get("summary", "")).split())
        ok = words <= self.limit
        return VerificationResult.from_checks(
            [CheckResult("word_limit", ok, 1.0 if ok else 0.0, f"{words} words")], self.name
        )
```

## Plugins by name

Mechanisms, policies, verifiers and settlement policies can be registered so YAML
configs and replay can find them:

```py
market.register_auction_mechanism("my_mechanism", MyMechanism)
market.register_selection_policy("my_policy", MyPolicy)
market.register_verifier("word_limit", WordLimit)
market.register_settlement_policy("my_settlement", MySettlement)
```

Implement `to_spec()` (dataclasses get it for free) so the recorded spec can rebuild
the plugin during replay. Reputation systems subclass `ReputationSystem`; bid
strategies subclass `BidStrategy`; storage backends implement `MarketStore`.
