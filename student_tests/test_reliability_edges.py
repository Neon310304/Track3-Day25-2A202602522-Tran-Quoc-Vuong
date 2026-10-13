"""Additional boundary regressions; the provided tests remain unchanged."""

from gameday_lab.cache import CachingClient, SemanticCache
from gameday_lab.client import ResilientClient
from gameday_lab.sim.contracts import Answer, Attempt, BaseClient, CallContext, GiveUp, ProviderError, Request, Send
from gameday_lab.slo.alerting import AlertRule, BurnRateAlerter, error_budget_report
from gameday_lab.workflows.executor import WorkflowExecutor, idempotency_key
from gameday_lab.workflows.runner import RefundRequest
from gameday_lab.workflows.services import DurableStore, ServiceError, Services


def test_exact_burn_threshold_fires_and_exact_budget_exhaustion_freezes():
    rule = AlertRule("boundary", "page", 60, 5, 14.4)
    events = BurnRateAlerter(rules=(rule,)).evaluate([1000] * 60, [72] * 60)
    assert events and events[0].start_min == 0 and events[0].end_min == 60
    report = error_budget_report([1000], [5])
    assert report["budget_remaining"] == 0 and report["freeze_releases"] is True


def test_cache_does_not_accept_answer_from_another_prompt_scope():
    cache = SemanticCache()
    request = Request("FAQ", "u1", False, "v2", (1.0, 0.0))
    cache.store(request, Answer(1, "v1", ("doc",), 0), 0)
    assert cache.lookup(request, 1) is None


def test_invalidation_while_provider_call_is_pending_prevents_stale_fallback():
    class FailingClient(BaseClient):
        def start(self, call, now):
            return Send("test", 1)

        def on_error(self, attempt, err, now):
            return GiveUp("down")

    cache = SemanticCache(ttl_s=1, max_stale_s=300)
    request = Request("FAQ", "u1", False, "v1", (1.0, 0.0))
    cache.store(request, Answer(1, "v1", ("doc",), 0), 0)
    client = CachingClient(FailingClient(), cache)
    call = CallContext(1, 1, "chat", 10, 40, request=request)
    assert isinstance(client.start(call, 10), Send)
    client.on_content_update("doc", 10.5)
    action = client.on_error(Attempt(call, "test", 1, 10, None), ProviderError("test", 503, "down"), 11)
    assert isinstance(action, GiveUp)


def test_idempotency_identity_cannot_collide_through_delimiters():
    a = RefundRequest("a:b", "order", 1, "a@example.com")
    b = RefundRequest("a", "order", 1, "a@example.com")
    assert idempotency_key(a, "c") != idempotency_key(b, "b:c")


def test_failed_step_does_not_save_checkpoint():
    class BrokenExecutor(WorkflowExecutor):
        def _step(self, req, state, step):
            raise ServiceError("unavailable")

    store = DurableStore()
    executor = BrokenExecutor(Services.build(1), store)
    try:
        executor.run(RefundRequest("session", "order", 1, "a@example.com"))
    except ServiceError:
        pass
    else:
        raise AssertionError("failed step must propagate")
    assert store.keys() == []


def test_rate_limit_wait_is_bounded_and_quota_never_waits():
    from gameday_lab.sim.contracts import ProviderInfo

    providers = {"p": ProviderInfo("p", "family", "region", True, 1)}
    client = ResilientClient(providers, ["p"], {})
    call = CallContext(1, 1, "tool", 0, 30)
    send = client.start(call, 0)
    assert isinstance(send, Send)
    action = client.on_error(Attempt(call, "p", 1, 0, send.tag),
                             ProviderError("p", 429, "rate_limit_exceeded", retry_after=2), 0.1)
    assert isinstance(action, Send) and 2 <= action.delay_s <= 5
    client.on_cancel(call, action.tag, 0.2)
    client.cooldown_until["p"] = 0
    other = CallContext(2, 2, "tool", 0.3, 30)
    send = client.start(other, 0.3)
    action = client.on_error(Attempt(other, "p", 1, 0.3, send.tag),
                             ProviderError("p", 429, "insufficient_quota"), 0.4)
    assert isinstance(action, GiveUp)
