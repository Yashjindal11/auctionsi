"""Agent adapters: bridges from the Agent interface to concrete executors."""

from auctionsi.adapters.function import PythonFunctionAgent
from auctionsi.adapters.http import HTTPAgent
from auctionsi.adapters.http_client import HTTPAdapterError
from auctionsi.adapters.human import HumanAgent
from auctionsi.adapters.openai_compatible import OpenAICompatibleAgent

__all__ = [
    "HTTPAdapterError",
    "HTTPAgent",
    "HumanAgent",
    "OpenAICompatibleAgent",
    "PythonFunctionAgent",
]
