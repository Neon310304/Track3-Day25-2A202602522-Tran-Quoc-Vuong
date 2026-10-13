"""Offline evidence/integrity checks. Does not replay simulations or change results."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import yaml


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    root = Path(__file__).resolve().parents[1]
    errors = []

    def check(condition, message):
        print(("PASS " if condition else "FAIL ") + message)
        if not condition:
            errors.append(message)

    manifest = read(root / "reports/evidence_manifest.json")
    mismatches = []
    for name, expected in manifest["sha256"].items():
        path = root / name
        data = path.read_bytes() if path.exists() else b""
        if path.suffix != ".png":
            data = data.replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != expected:
            mismatches.append(name)
    check(not mismatches, f"Manifest source/evidence hashes ({len(manifest['sha256'])} files): {mismatches}")

    board = read(root / "reports/scoreboard.json")
    multi = read(root / "reports/scoreboard_multiseed.json")
    check(board["summary"]["automatic"] == 84 and board["slo_hidden"]["pass"] is None,
          "84 public automatic points; hidden SLO is unclaimed")
    check(all(result["passed"] == result["total"] and result["total"] > 0
              for result in board["unit_tests"].values()), "All graded unit tests passed")
    check(all(result["pass"] for result in multi["gameday"].values()), "All six tapes passed on 25/26/27")
    check(all(result["pass"] for result in multi["cache_tape"].values()), "Cache passed on 25/26/27")
    check(multi["workflows"]["pass"] and multi["slo_public"]["pass"], "Workflows and public SLO passed")

    report = (root / "reports/REPORT.md").read_text(encoding="utf-8")
    check(all(f"## {n}." in report for n in range(1, 9)) and "…" not in report.replace("t=145…483", ""),
          "Report has all eight sections and no template placeholders")
    check(manifest["source_commit"] in report, "Report identifies source/evidence commit")
    protected = ["src/gameday_lab/sim", "src/gameday_lab/naive_client.py",
                 "src/gameday_lab/workflows/services.py", "src/gameday_lab/workflows/runner.py",
                 "src/gameday_lab/workflows/naive_executor.py", "src/gameday_lab/slo/data.py",
                 "src/gameday_lab/slo/scoring.py", "configs/scenarios.yaml", "configs/scenarios_cache.yaml",
                 "tests", "data"]
    original = "18cc181"
    changes = subprocess.check_output(["git", "diff", "--name-only", original, "--", *protected],
                                      cwd=root, text=True).strip()
    check(not changes, f"Provided simulator/tests/tapes/services/data unchanged: {changes}")
    original_cfg = yaml.safe_load(subprocess.check_output(["git", "show", f"{original}:configs/gameday.yaml"],
                                                         cwd=root, text=True, encoding="utf-8"))
    cfg = yaml.safe_load((root / "configs/gameday.yaml").read_text(encoding="utf-8"))
    check({k: v for k, v in cfg.items() if k not in ("client", "cache")}
          == {k: v for k, v in original_cfg.items() if k not in ("client", "cache")},
          "World configuration unchanged outside client/cache")
    unresolved = [str(path.relative_to(root)) for path in [
        root / "src/gameday_lab" / name for name in ("errors.py", "retry.py", "breaker.py", "client.py", "cache.py",
                                                    "workflows/executor.py", "slo/alerting.py")]
                  if "TODO(student)" in path.read_text(encoding="utf-8")]
    check(not unresolved, f"All student implementations completed: {unresolved}")
    print(f"{len(errors)} failed checks")
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
