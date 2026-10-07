# REST/WebSocket API and dashboard

```bash
pip install "auctionsi[api]"
auctionsi --db market.db serve --port 8000   # dashboard at http://127.0.0.1:8000
```

`create_app(db_path, config=..., api_key=...)` returns the FastAPI app if you want to
mount it yourself. Interactive OpenAPI docs are at `/docs`.

## Security

- Set `AUCTIONSI_API_KEY` (or pass `api_key`) to require an `X-API-Key` header on
  every `/api/*` route except `/api/health`. Keys are compared in constant time.
  WebSocket clients send the key as an `X-API-Key` upgrade header or, from a
  browser (which cannot set headers), as a first message
  `{"type": "auth", "key": "..."}` within 5 seconds; the server closes with code
  4401 otherwise. The key never appears in a URL. `serve` warns when binding beyond
  localhost without a key.
- Request bodies over 1 MB are refused (413); bodies are validated against strict
  schemas (unknown fields are errors). Simulations are capped at 2,000 agents and
  20,000 tasks per request.
- One market per process, guarded by a lock; this is a single-tenant service.

## Endpoints

| method | path | purpose |
|---|---|---|
| GET | `/api/health` | liveness and version (no key needed) |
| GET | `/api/status` | store counts, counters, mechanism and policy |
| POST/GET | `/api/agents` | register (`kind: simulated` or `http` spec) / list |
| GET | `/api/agents/{id}` | agent, reputation, bids, fulfilled contracts |
| DELETE | `/api/agents/{id}` | remove from future auctions (204); history is kept |
| GET | `/api/agents/{id}/reputation` | overall and per task type |
| POST/GET | `/api/tasks` | run a full auction for a task / list tasks |
| POST | `/api/auctions?solicit=true` | open a staged auction (optionally ask registered agents) |
| POST | `/api/auctions/{id}/bids` | submit an external bid (422 with reasons if rejected) |
| POST | `/api/auctions/{id}/close` | select, award, execute, verify, settle |
| POST | `/api/auctions/{id}/cancel` | cancel an open auction |
| GET | `/api/auctions`, `/api/auctions/{id}` | list / detail with events and trace |
| GET | `/api/auctions/{id}/replay` | re-derive the recorded decision |
| POST | `/api/simulate` | run a simulated market and return metrics and chart data |
| GET | `/api/calibration` | claimed vs delivered quality/latency, reliability bins |
| GET | `/api/experiments` | experiments saved with `--save-db` |
| GET | `/api/plugins` | registered mechanisms, policies, verifiers, settlements, strategies |
| WS | `/api/events` | live market events as JSON; a client that falls more than 10,000 events behind loses the oldest |

Errors: 404 for unknown ids, 409 for invalid state transitions, 422 for validation
errors.

## Signed bids

`Marketplace(bid_keys={"agent-a": key}, require_signatures=True)` accepts a bid
only if `signature` is the HMAC-SHA256 from `auctionsi.security.signing.sign_proposal`,
bound to the agent, auction and task ids, so a captured signature cannot be
replayed in another auction or for another agent. Unsigned or wrongly signed bids
are rejected with `BAD_SIGNATURE`.

## Dashboard

The dashboard (React, in `web/`) is built into the wheel. Pages: overview
(counters, recent auctions), agents (reputation, bids, contracts), auctions (bids,
rejections, scores, trace, replay), and research (live events, simulation,
calibration, experiments). The live view reconnects with exponential backoff (up to
30 s) and stops if the key is rejected. To develop it: `cd web && npm ci && npm run dev`
(proxying `/api` to a running `auctionsi serve`), `npm test` for the Vitest suite,
and `npm run build` to write the assets into `src/auctionsi/api/static`.
