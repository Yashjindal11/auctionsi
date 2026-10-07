---
description: >-
  Auction mechanisms in AuctionSI: first-price and second-price (Vickrey-style)
  reverse auctions, multi-winner, open descending, forward, bundle (combinatorial)
  and capacity auctions, with payment rules, assumptions and incentives.
---

# Auction mechanisms

A mechanism decides how bids are **collected** and how ranked bids become
**awards and payments**. Ranking is delegated to a [selection policy](selection.md).
All built-in mechanisms are *reverse* auctions (agents compete to sell work to a
buyer). Bids that fail validation (over budget, deadline infeasible, below the
required quality, malformed) never reach the mechanism.

Statements below about incentives hold only under the stated assumptions. AuctionSI
does not claim that any mechanism is truthful or optimal in general.

## `first_price_reverse` — sealed-bid, pay-as-bid

- **Rules:** every eligible agent is asked once, in agent-id order, and sees no other bid.
  The top-ranked valid bid wins.
- **Payment:** the winner's own price.
- **Inputs/outputs:** valid bids, policy, features → ranking, one award.
- **With `LowestPrice`:** the lowest valid bid wins (ties: earlier bid, then agent id).
- **Advantages:** simple, predictable buyer cost.
- **Limitations / strategy:** a profit-seeking bidder has an incentive to bid above
  its cost ("shading"); how much depends on what it believes about rivals.

## `second_price_reverse` — sealed-bid, critical-value payment

- **Rules:** as first-price.
- **Payment:** the winner's *critical value*: the highest price at which it would
  still rank first with all other bids fixed, capped at the task budget. With a
  price-only policy this is the runner-up's price. With other policies it is found
  by bisection, assuming the score never rises when only the price rises (true of
  every built-in policy). With one valid bid, `single_bid_payment="reserve"` pays the
  budget (if any), `"bid"` pays the bid. Payment is never below the winner's bid.
- **Incentives:** in the textbook setting (one task, one winner, price-only ranking,
  each bidder's cost private and independent, quasi-linear utility, a single
  one-shot sealed round, no effect of this auction on future auctions or
  reputation), bidding one's true cost is a weakly dominant strategy. In AuctionSI
  these conditions often fail: reputation links auctions together, failures are
  penalised, and multi-dimensional scores make the bid more than a price. Treat
  the property as a hypothesis to test, not a guarantee.
- **Limitations:** with bidders that do not adapt their strategy, buyers simply pay
  more (see `research/results/mechanisms`).

## `multi_winner_reverse` — k winners

- **Rules:** sealed; the top `winners` bids win, one award per agent.
- **Payment:** `pay_as_bid` (own price) or `uniform` (every winner gets the best
  *losing* price, i.e. the (k+1)-th price; the budget or own price if nobody lost).
  Uniform pricing is only allowed with price-only policies.
- **Incentives:** the uniform (k+1)-th-price rule is the multi-unit analogue of
  second price when each agent wants at most one unit; the same caveats apply.
- **Execution:** one contract per winner; recovery applies per slot.

## `open_reverse` — descending open auction

- **Rules:** after a sealed round 0, agents see the standing best price each round
  and may lower their own bid (`Agent.revise_bid`). Revisions must lower the price.
  Agents without a bid may enter late. Stops after a round with no accepted
  revision or after `max_rounds`. Every revision is recorded (`BidRevised` events,
  `Bid.revision`).
- **Payment:** pay-as-bid on final bids.
- **Strategy:** bidders learn about rivals during the auction; outcomes depend on
  revision strategies (`BidStrategy.revise` undercuts by 2% down to a floor).

## Writing a mechanism

```python
from dataclasses import dataclass
from auctionsi.mechanisms import AuctionMechanism, Award, MechanismOutcome

@dataclass(frozen=True)
class FirstPriceExample(AuctionMechanism):
    name = "my_mechanism"

    def determine_winners(self, bids, task, policy, features):
        ranking = policy.rank(bids, task, features)
        if not ranking:
            return MechanismOutcome([], [], ["no valid bids"])
        top = ranking[0]
        return MechanismOutcome(ranking, [Award(top, top.bid.price, 0, "pay-as-bid")])

from auctionsi import Marketplace
market = Marketplace()
market.register_auction_mechanism("my_mechanism", FirstPriceExample)
```

Rules for mechanisms: be deterministic given the inputs (replay depends on it),
never award an invalid bid, document payment rules in `payment_rule`, and override
`collect_bids` only if you need a different collection protocol.

## `forward` — agents bid to buy

- **Rules:** sealed; the task describes what is on offer and `Task.reserve_price` is
  the minimum acceptable bid (lower bids are rejected with `BELOW_RESERVE`). The
  highest bid wins. Ranking is by price only; the selection policy is not used.
- **Payment:** `pricing: first` charges the winner its bid; `pricing: second`
  charges the larger of the runner-up bid and the reserve (Vickrey for one item
  under private values, single shot).
- **Settlement:** contracts and settlements carry `direction: forward`; buyer cost
  is negative (the market receives money) and no refund applies.

## `bundle_reverse` — combinatorial procurement

- **Rules:** the task lists items in `requirements["items"]`; each bid covers the
  items in `terms["items"]` (all items when absent). Winner determination picks the
  non-overlapping set of bids that covers every item at the lowest total price,
  solved exactly by dynamic programming over item subsets (capped at `max_items`,
  default 12). Ties are broken by the policy ranking.
- **Payment:** pay-as-bid, one contract per winner.
- **Incentives:** pay-as-bid bundle auctions invite strategic bundle pricing; no
  incentive property is claimed.

## `capacity` — reserving future work

- **Rules:** the task asks for `requirements["units"]` units (e.g. 100 tasks next
  hour). A bid's `price` is per unit and `capacity` (or `terms["units"]`) is the
  units offered. Units are filled from the cheapest offers up; the last winner may
  be partially filled. `Award.quantity` records the units reserved.
- **Payment:** `pricing: pay_as_bid` (own unit price) or `uniform` (the first
  rejected unit price, or the budget per unit / own price when supply runs out).
