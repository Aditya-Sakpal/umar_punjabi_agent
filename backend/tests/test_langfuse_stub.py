"""LangFuse stub must satisfy LangChain callback protocol."""
from app.observability.langfuse import langfuse_handler


def test_langfuse_handler_has_run_inline():
    handler = langfuse_handler("run-1", "BTCUSDT", "user")
    assert hasattr(handler, "run_inline")
    assert handler.run_inline is False
