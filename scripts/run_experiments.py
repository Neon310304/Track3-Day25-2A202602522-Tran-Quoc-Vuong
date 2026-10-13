"""Reproduce the report's ablations without changing production code or tapes.

All durations and costs are simulator outputs, not measurements of a live API.
Run from the repository root: python scripts/run_experiments.py
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameday_lab.cache import CachingClient, SemanticCache
from gameday_lab.client import ResilientClient
from gameday_lab.sim.config import LabConfig, load_config
from gameday_lab.sim.engine import evaluate_checks, run_scenario


class UnfilteredClient(ResilientClient):
    """Deliberately unsafe control for the capability-filter ablation only."""

    name = "unfiltered_experiment"

    def ladder(self, task: str) -> list[str]:
        return list(self.order)


def replay(cfg: LabConfig, key: str, seed: int, *, unfiltered: bool = False,
           cached: bool = False) -> dict:
    cls = UnfilteredClient if unfiltered else ResilientClient
    inner = cls(cfg.provider_infos(), cfg.fallback_order, cfg.client, seed=1)
    client = CachingClient(inner, SemanticCache(**cfg.cache)) if cached else inner
    metrics = run_scenario(cfg, key, client, seed).metrics()
    checks = evaluate_checks(metrics, cfg.scenarios[key].checks)
    return {"seed": seed, "metrics": metrics, "checks": checks, "pass": all(checks.values())}


def main() -> None:
    core = load_config()
    cache = load_config(scenarios_path="configs/scenarios_cache.yaml")
    records = []

    def record(label: str, cfg: LabConfig, keys: list[str], *, cached: bool = False,
               unfiltered: bool = False, seeds: tuple[int, ...] = (25,)) -> None:
        runs = [replay(cfg, key, seed, cached=cached, unfiltered=unfiltered)
                for seed in seeds for key in keys]
        records.append({"experiment": label, "client_settings": cfg.client,
                        "cache_settings": cfg.cache if cached else None,
                        "unfiltered_ladder": unfiltered, "runs": runs})
        for run in runs:
            m = run["metrics"]
            print(f"{label:30s} {m['scenario']:27s} avail={m['availability']} "
                  f"p95={m['latency_p95_s']} ampl={m['amplification']} "
                  f"retry={m['retry_ratio']} wrong={m.get('wrong_answers', 0)} "
                  f"outdated={m.get('outdated_answers', 0)}")

    original = deepcopy(core.client)
    original["attempt_timeout_s"] = 8.0
    original["breaker"]["slow_call_s"] = 5.0
    record("starter_client_settings", replace(core, client=original), list(core.scenarios))
    intermediate = deepcopy(core.client)
    intermediate["breaker"]["slow_call_s"] = 5.0
    record("timeout_4s_slow_5s", replace(core, client=intermediate), ["G2_overload_storm"])

    for faulty in (False, True):
        for budget_off in (False, True):
            settings = deepcopy(core.client)
            if faulty:
                settings["breaker"]["min_calls"] = 1_000_000_000
                settings["max_attempts_per_provider"] = 5
            if budget_off:
                settings.update(retry_budget_ratio=100, retry_budget_max_tokens=1e9,
                                retry_budget_min_per_s=1e6)
            label = ("broken" if faulty else "healthy") + "_breaker_budget_" + ("off" if budget_off else "on")
            record(label, replace(core, client=settings), ["G2_overload_storm", "G3_brownout"])
    settings = deepcopy(core.client)
    settings["attempt_timeout_s"] = 30.0
    record("timeout_30s", replace(core, client=settings), ["G4_slow_region", "G6_provider_outage"])
    record("without_tool_filter", core, ["G6_provider_outage"], unfiltered=True)

    for threshold in (0.8, 0.9, 0.97):
        record(f"cache_threshold_{threshold}", replace(cache, cache={**cache.cache,
               "similarity_threshold": threshold}), ["C1_faq_outage"], cached=True)
    for ttl in (30, 60, 300):
        record(f"cache_ttl_{ttl}s", replace(cache, cache={**cache.cache, "ttl_s": ttl}),
               ["C1_faq_outage"], cached=True)
    record("cache_without_stale", replace(cache, cache={**cache.cache, "max_stale_s": 0}),
           ["C1_faq_outage"], cached=True)
    record("cache_starter_settings", replace(cache, cache={"similarity_threshold": 0.8,
           "ttl_s": 600, "max_stale_s": 0, "max_entries": 500}), ["C1_faq_outage"], cached=True)

    # Public tapes, additional independent traffic seeds. Not instructor hidden data.
    record("public_multiseed", core, list(core.scenarios), seeds=(25, 26, 27))
    record("cache_public_multiseed", cache, ["C1_faq_outage"], cached=True, seeds=(25, 26, 27))

    out = Path("reports/experiments.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"kind": "simulation", "experiments": records}, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
