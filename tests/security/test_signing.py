from __future__ import annotations

from dataclasses import replace

from auctionsi.core import BidContext, BidProposal, RejectionCode, Task
from auctionsi.market import ManualClock, Marketplace
from auctionsi.security.signing import sign_proposal, verify_proposal
from conftest import ScriptedAgent, task

KEY = b"agent-a-secret"


class SigningAgent(ScriptedAgent):
    def __init__(self, *args: object, key: bytes, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.key = key

    def bid(self, task: Task, context: BidContext) -> BidProposal | None:
        proposal = super().bid(task, context)
        assert proposal is not None
        return sign_proposal(
            proposal,
            self.key,
            agent_id=self.agent_id,
            auction_id=context.auction_id,
            task_id=task.task_id,
        )


def test_sign_and_verify_bind_ids_and_fields() -> None:
    signed = sign_proposal(BidProposal(price=1.0), KEY, agent_id="a", auction_id="x", task_id="t")
    assert verify_proposal(signed, KEY, agent_id="a", auction_id="x", task_id="t")
    assert not verify_proposal(signed, KEY, agent_id="a", auction_id="other", task_id="t")
    assert not verify_proposal(
        replace(signed, price=0.5), KEY, agent_id="a", auction_id="x", task_id="t"
    )
    assert not verify_proposal(signed, b"wrong", agent_id="a", auction_id="x", task_id="t")
    assert not verify_proposal(
        BidProposal(price=1.0), KEY, agent_id="a", auction_id="x", task_id="t"
    )


def test_marketplace_enforces_signatures() -> None:
    market = Marketplace(
        clock=ManualClock(),
        bid_keys={"signed": KEY, "forger": b"real-key"},
        require_signatures=True,
    )
    market.register(SigningAgent("signed", 0.05, key=KEY))
    market.register(SigningAgent("forger", 0.01, key=b"guessed-key"))
    market.register(ScriptedAgent("unsigned", 0.02))
    result = market.submit_task(task())
    assert result.winner == "signed"
    codes = {r.agent_id: r.reasons[0].code for r in result.auction.rejected}
    assert codes == {"forger": RejectionCode.BAD_SIGNATURE, "unsigned": RejectionCode.BAD_SIGNATURE}
