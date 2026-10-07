# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through a
[GitHub security advisory](https://github.com/Yashjindal11/auctionsi/security/advisories/new),
not in a public issue. Include steps to reproduce and the affected version. You
should get an acknowledgement within a week.

## Threat model

AuctionSI treats **agents as untrusted**:

- Agents return `BidProposal` objects; the marketplace validates every field
  (types, finiteness, ranges, sizes) and stamps ids and timestamps itself.
- Exceptions, invalid latencies and oversized outputs from agents become recorded
  failures; they cannot crash or corrupt an auction.
- The marketplace never executes code or commands supplied in bids, tasks or
  outputs. `UnitTestVerifier` runs callables written by the task owner, not by agents.
- `HTTPAgent` / `OpenAICompatibleAgent` only allow `http(s)` URLs, do not follow
  redirects, apply timeouts and cap response sizes. Tokens are read from environment
  variables and never stored in events, logs or the database.

Input handling:

- Identifiers are restricted to `[A-Za-z0-9._:-]` (no path traversal); text and JSON
  payloads have size limits (`auctionsi.security.Limits`).
- YAML is loaded with a safe loader that also rejects aliases (billion-laughs);
  config files have a size limit; unknown config keys are errors.
- SQLite and PostgreSQL storage use parameterised queries and JSON columns; nothing
  is pickled. Storage status output strips credentials from database URLs.
- `safe_path` confines user-supplied paths to a base directory.
- Bids can be required to carry an HMAC-SHA256 signature bound to the agent,
  auction and task ids (`require_signatures=True`), so bids cannot be forged or
  replayed across auctions by someone without the agent's key.
- Agents get a bid deadline and an optional execution timeout; slow agents become
  recorded `TIMEOUT` rejections or failures.

The optional API (`auctionsi serve`):

- `AUCTIONSI_API_KEY` enables `X-API-Key` authentication (constant-time compare)
  on all `/api/*` routes except health, and on the WebSocket (upgrade header or a
  first auth message, so the key never sits in a URL or access log). Without a
  key the API is open, so it binds to 127.0.0.1 by default and warns otherwise.
- Bodies are capped at 1 MB and validated against strict schemas; simulation sizes
  are capped. Static files are served only from inside the bundled directory.
- There is one shared market per process: no multi-tenant isolation or per-user
  permissions. Put it behind TLS and a reverse proxy if exposed beyond a host.

Market-level abuse (collusion, Sybil identities, misreporting, reputation gaming)
is a research topic in this project: there are simulation tools to measure it and a
per-operator bid cap, but no claim that the built-in defences are sufficient.

Out of scope: multi-tenant isolation, and sandboxing of in-process Python agents you
register.
