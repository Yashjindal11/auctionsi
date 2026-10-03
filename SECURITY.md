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
- SQLite storage uses parameterised queries and JSON columns; nothing is pickled.
- `safe_path` confines user-supplied paths to a base directory.

Market-level abuse (collusion, Sybil identities, misreporting, reputation gaming)
is a research topic in this project: there are simulation tools to measure it and a
per-operator bid cap, but no claim that the built-in defences are sufficient.

Out of scope for v0.1: authentication and multi-tenant isolation (the framework is
local and single-user), and sandboxing of in-process Python agents you register.
