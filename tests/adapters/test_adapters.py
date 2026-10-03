from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import yaml

from auctionsi.adapters import (
    HTTPAdapterError,
    HTTPAgent,
    HumanAgent,
    OpenAICompatibleAgent,
    PythonFunctionAgent,
)
from auctionsi.adapters.http_client import post_json
from auctionsi.adapters.specs import agent_spec, build_agent
from auctionsi.cli.main import main
from auctionsi.core import BidContext, Contract, Task
from auctionsi.errors import ValidationError
from auctionsi.verification import ExactMatchVerifier, SchemaVerifier
from conftest import MarketFactory, task

STATE: dict[str, Any] = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        return None

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        STATE.setdefault("requests", []).append((self.path, body, dict(self.headers)))
        if self.path == "/redirect/bid":
            self.send_response(302)
            self.send_header("Location", "http://example.invalid/")
            self.end_headers()
            return
        if self.path == "/big/bid":
            reply: Any = {"price": 1, "padding": "x" * 5000}
        elif self.path.endswith("/bid"):
            reply = {"price": 0.04, "estimated_latency": 2, "estimated_quality": 0.9, "evil": "x"}
        elif self.path.endswith("/execute"):
            reply = {"success": True, "output": {"answer": 42}, "actual_cost": 0.01}
        elif self.path.endswith("/chat/completions"):
            reply = {
                "choices": [{"message": {"content": "SELECT 1;"}}],
                "usage": {"total_tokens": 7},
            }
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def server() -> Iterator[str]:
    STATE.clear()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


CTX = BidContext("a", "first_price_reverse", 0.0, True, "credits")


def test_specs_build_http_and_simulated_agents(
    server: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = {"kind": "http", "agent_id": "remote", "base_url": server, "capabilities": ["analysis"]}
    agent = build_agent(spec)
    assert isinstance(agent, HTTPAgent)
    assert build_agent(agent_spec(agent)).describe() == agent.describe()
    sim = build_agent({"agent_id": "s", "capabilities": ["x"], "cost_model": {"fixed_cost": 0.1}})
    assert agent_spec(sim)["kind"] == "simulated"
    for bad in ({"kind": "rpc"}, {"kind": "http", "agent_id": "x"}, {"kind": "http", "evil": 1}):
        with pytest.raises(ValidationError):
            build_agent(bad)
    with pytest.raises(ValidationError):
        agent_spec(HumanAgent("h", capabilities=["x"]))

    monkeypatch.chdir(tmp_path)
    (tmp_path / "agents.yaml").write_text(yaml.safe_dump({"agents": [spec]}), encoding="utf-8")
    (tmp_path / "auctionsi.yaml").write_text(
        "verification: {verifier: {name: exact_match, expected: 42, key: answer}}\n",
        encoding="utf-8",
    )
    assert main(["agent", "register", "agents.yaml"]) == 0
    assert main(["auction", "run", "--type", "analysis", "--budget", "1"]) == 0
    assert "Winner: remote" in capsys.readouterr().out


def test_http_agent_end_to_end(
    server: str, market_factory: MarketFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "s3cret")
    agent = HTTPAgent("remote", server + "/", capabilities=["analysis"], token_env="AGENT_TOKEN")
    market = market_factory(verifier=ExactMatchVerifier(42, key="answer"))
    market.register(agent)
    result = market.submit_task(task())
    assert result.succeeded
    assert result.contracts[0].execution.actual_cost == 0.01
    paths = [r[0] for r in STATE["requests"]]
    assert paths == ["/bid", "/execute"]
    assert STATE["requests"][0][2]["Authorization"] == "Bearer s3cret"
    assert "s3cret" not in json.dumps([e.to_dict() for e in result.events])
    assert agent.describe()["endpoint"] == server


def test_http_hardening(server: str) -> None:
    with pytest.raises(ValidationError):
        HTTPAgent("x", "file:///etc/passwd", capabilities=["a"])
    with pytest.raises(ValidationError):
        HTTPAgent("x", "ftp://host", capabilities=["a"])
    with pytest.raises(HTTPAdapterError, match="redirects"):
        HTTPAgent("x", server + "/redirect", capabilities=["a"]).bid(
            Task(task_id="t", task_type="a"), CTX
        )
    with pytest.raises(HTTPAdapterError, match="exceeds"):
        HTTPAgent("x", server + "/big", capabilities=["a"], max_response_bytes=100).bid(
            Task(task_id="t", task_type="a"), CTX
        )
    with pytest.raises(HTTPAdapterError, match="HTTP 404"):
        post_json(server + "/nothing", {}, timeout=5, max_bytes=1000)
    with pytest.raises(HTTPAdapterError, match="unreachable"):
        post_json("http://127.0.0.1:9/x", {}, timeout=1, max_bytes=1000)


def test_unreachable_execution_is_a_failure(market_factory: MarketFactory) -> None:
    agent = HTTPAgent("down", "http://127.0.0.1:9", capabilities=["analysis"], timeout=1)
    contract = Contract("c", "a", "t", "down", "b", 1, 1, "credits", 0)
    result = agent.execute(task(), contract)
    assert not result.success
    assert "unreachable" in (result.error or "")


def test_openai_compatible_agent(server: str, market_factory: MarketFactory) -> None:
    agent = OpenAICompatibleAgent(
        "llm",
        base_url=server + "/v1",
        model="local-model",
        capabilities=["analysis"],
        price=lambda t: 0.02 if t.budget else None,
    )
    market = market_factory(verifier=SchemaVerifier({"type": "object", "required": ["text"]}))
    market.register(agent)
    result = market.submit_task(task(budget=1.0, description="Count rows"))
    assert result.succeeded
    assert result.contracts[0].execution.output == {"text": "SELECT 1;"}
    sent = STATE["requests"][-1][1]
    assert sent["model"] == "local-model"
    assert "Count rows" in sent["messages"][1]["content"]
    assert "Authorization" not in STATE["requests"][-1][2]
    assert agent.bid(Task(task_id="t2", task_type="analysis"), CTX) is None


def test_human_agent(market_factory: MarketFactory) -> None:
    answers = iter(["0.05", '{"answer": 42}'])
    human = HumanAgent("person", capabilities=["analysis"], ask=lambda prompt: next(answers))
    market = market_factory(verifier=ExactMatchVerifier(42, key="answer"))
    market.register(human)
    assert market.submit_task(task()).succeeded
    for answer in ("", "lots", "nan"):
        shy = HumanAgent("p", capabilities=["analysis"], ask=lambda prompt, a=answer: a)
        assert shy.bid(task("x"), CTX) is None
    texty = HumanAgent("t", capabilities=["analysis"], ask=lambda prompt: "plain text")
    contract = Contract("c", "a", "t", "t", "b", 1, 1, "credits", 0)
    assert texty.execute(task(), contract).output == "plain text"


def test_python_function_agent(market_factory: MarketFactory) -> None:
    agent = PythonFunctionAgent(
        "fn",
        lambda t, c: {"answer": 6 * 7},
        capabilities=["analysis"],
        price=lambda t: None if t.budget is None else t.budget / 2,
        estimated_quality=0.99,
    )
    market = market_factory(verifier=ExactMatchVerifier(42, key="answer"))
    market.register(agent)
    assert market.submit_task(task("a", budget=1.0)).buyer_cost == 0.5
    assert market.submit_task(task("b")).status.value == "no_bids"
