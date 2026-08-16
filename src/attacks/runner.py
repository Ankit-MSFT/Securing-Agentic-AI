"""Shared attack runner: handles PyRIT setup, model loop, ASR bookkeeping.

Each scenario only supplies a `ScenarioSpec`; the runner takes care of the
rest so scenarios stay small and comparable.
"""

from __future__ import annotations

import asyncio
import io
import logging
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

# Force UTF-8 on stdout/stderr so ₹, arrows, and box-drawing chars survive `>` redirects on Windows.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from common import load_env

load_env()

from pyrit.prompt_target import OpenAIChatTarget
from pyrit.executor.attack.multi_turn import RedTeamingAttack
from pyrit.executor.attack.core.attack_config import (
    AttackAdversarialConfig,
    AttackScoringConfig,
)
from pyrit.score import SelfAskTrueFalseScorer
from pyrit.score.true_false.self_ask_true_false_scorer import TrueFalseQuestion
from pyrit.memory import CentralMemory
from pyrit.memory.sqlite_memory import SQLiteMemory

from attacks.pyrit_target import MidTownAgentTarget
from attacks.bank_state import (
    BANK_DB_BACKUP,
    snapshot as snapshot_bank_state,
    restore as restore_bank_state,
)

DEFAULT_MODELS = ("gpt-5.1", "mistral", "deepseek")


@dataclass
class ScenarioSpec:
    """Static description of an attack scenario."""

    id: str
    name: str
    objective: str
    # Deterministic success signal: attack succeeded if the agent called ANY of these tools.
    # For custom logic, override with `success_predicate`.
    success_tools: frozenset[str] = frozenset()
    success_predicate: Callable[[list[str], list[dict]], bool] | None = None
    # PyRIT LLM-judge question, used only to drive when the multi-turn attack stops.
    pyrit_true_desc: str = ""
    pyrit_false_desc: str = ""
    pyrit_category: str = "attack"
    header_lines: Sequence[str] = ()
    n_runs: int = 30
    max_turns: int = 5
    models: Sequence[str] = DEFAULT_MODELS
    inter_run_sleep_seconds: float = 2.0

    def is_success(self, tool_calls: list[str], tool_details: list[dict]) -> bool:
        if self.success_predicate is not None:
            return self.success_predicate(tool_calls, tool_details)
        return any(t in self.success_tools for t in tool_calls)


def _parse_flags(argv: Sequence[str]) -> tuple[bool, bool, Path | None]:
    debug = "--debug" in argv
    conv = debug or "--conversation" in argv or "--conv" in argv
    log_path: Path | None = None
    if "--log" in argv:
        i = argv.index("--log")
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            log_path = Path(argv[i + 1])
        else:
            log_path = _default_log_path()
    return debug, conv, log_path


def _default_log_path() -> Path:
    from common import REPO_ROOT
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "data" / "attack-logs" / f"run_{ts}.log"


class _Tee(io.TextIOBase):
    """Duplicate writes to the original stream and a UTF-8 file."""

    def __init__(self, original, file_handle) -> None:
        self._original = original
        self._file = file_handle

    def write(self, s: str) -> int:
        self._file.write(s)
        self._file.flush()
        try:
            return self._original.write(s)
        except Exception:
            return len(s)

    def flush(self) -> None:
        try:
            self._original.flush()
        finally:
            self._file.flush()

    def isatty(self) -> bool:
        try:
            return self._original.isatty()
        except Exception:
            return False


def _setup_logging(debug: bool, logger_name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="[%(asctime)s] %(name)-20s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )
    if not debug:
        for noisy in ("httpx", "openai", "langchain", "pyrit"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger(logger_name)


def _print_header(spec: ScenarioSpec) -> None:
    print("=" * 70)
    print(f"SCENARIO {spec.id} — {spec.name.upper()} — FULL ASR EXPERIMENT")
    print("=" * 70)
    print(f"Models:      {', '.join(spec.models)}")
    print(f"Runs/model:  {spec.n_runs}")
    print(f"Max turns:   {spec.max_turns} per run")
    for line in spec.header_lines:
        print(line)
    print(f"Started:     {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)


def _print_footer(spec: ScenarioSpec, results: dict[str, dict]) -> None:
    print("\n" + "=" * 70)
    print(f"FINAL ASR COMPARISON — SCENARIO {spec.id} ({spec.name})")
    print("=" * 70)
    print(f"{'Model':<25} | {'Runs':<5} | {'Success':<8} | {'Errors':<7} | {'ASR':<8} | {'Time':<8}")
    print("-" * 70)
    for model_name, res in results.items():
        print(
            f"{model_name:<25} | "
            f"{res['total_valid']:<5} | "
            f"{res['successes']:<8} | "
            f"{res['errors']:<7} | "
            f"{res['asr']:<7.1f}% | "
            f"{res['elapsed_seconds']:<7.0f}s"
        )
    print("-" * 70)
    print(f"Completed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)


async def _run_async(spec: ScenarioSpec, debug: bool, show_conversation: bool) -> None:
    log = _setup_logging(debug, f"scenario_{spec.id.lower()}")

    def dbg(msg: str) -> None:
        if debug:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] 🐛 {msg}")

    snapshot_bank_state()
    dbg(f"Snapshotted bank DB to {BANK_DB_BACKUP}")

    memory = SQLiteMemory(db_path=":memory:")
    CentralMemory.set_memory_instance(memory)

    _print_header(spec)

    all_results: dict[str, dict] = {}
    for model_name in spec.models:
        print(f"\n{'─'*70}")
        print(f"MODEL: {model_name}")
        print(f"{'─'*70}")

        objective_target = MidTownAgentTarget(
            model_name=model_name, verbose=show_conversation
        )
        adversarial_llm = OpenAIChatTarget(temperature=1.0)
        scorer_llm = OpenAIChatTarget(temperature=0)
        objective_scorer = SelfAskTrueFalseScorer(
            chat_target=scorer_llm,
            true_false_question=TrueFalseQuestion(
                true_description=spec.pyrit_true_desc,
                false_description=spec.pyrit_false_desc,
                category=spec.pyrit_category,
            ),
        )
        attack = RedTeamingAttack(
            objective_target=objective_target,
            attack_adversarial_config=AttackAdversarialConfig(target=adversarial_llm),
            attack_scoring_config=AttackScoringConfig(objective_scorer=objective_scorer),
            max_turns=spec.max_turns,
        )

        restore_bank_state()
        successes = 0
        errors = 0
        model_start = time.time()

        for run in range(1, spec.n_runs + 1):
            objective_target.reset_tool_calls()
            try:
                await attack.execute_async(objective=spec.objective)
            except Exception as e:
                print(f"  Run {run:>2}/{spec.n_runs}: ⚠ ERROR — {type(e).__name__}: {e}")
                if debug:
                    traceback.print_exc()
                errors += 1
                restore_bank_state()
                continue

            tools = objective_target.get_tool_calls()
            details = objective_target.get_tool_call_details()
            success = spec.is_success(tools, details)
            if success:
                successes += 1

            status = "✓ SUCCESS" if success else "✗ FAILED"
            print(
                f"  Run {run:>2}/{spec.n_runs}: {status}  |  "
                f"ASR: {successes}/{run} ({successes/run*100:.0f}%)"
            )
            dbg(f"Tools called this run: {tools}")

            restore_bank_state()
            await asyncio.sleep(spec.inter_run_sleep_seconds)

        elapsed = time.time() - model_start
        valid = spec.n_runs - errors
        all_results[model_name] = {
            "successes": successes,
            "errors": errors,
            "total_valid": valid,
            "asr": (successes / valid * 100) if valid > 0 else 0,
            "elapsed_seconds": elapsed,
        }
        print(
            f"\n  [{model_name}] ASR: {all_results[model_name]['asr']:.1f}% "
            f"({successes}/{valid} valid runs, {errors} errors, {elapsed:.0f}s elapsed)"
        )

    _print_footer(spec, all_results)


def run_scenario(spec: ScenarioSpec) -> None:
    """Blocking entry point. Reads CLI flags from sys.argv.

    Flags:
        --conv / --conversation   show attacker/agent turns
        --debug                   verbose logging
        --log [PATH]              tee stdout+stderr to a UTF-8 log file
                                  (default: data/attack-logs/run_<utc>.log)
    """
    debug, show_conversation, log_path = _parse_flags(sys.argv)

    log_file = None
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "w", encoding="utf-8", newline="")
        sys.stdout = _Tee(orig_stdout, log_file)
        sys.stderr = _Tee(orig_stderr, log_file)
        print(f"[runner] logging to {log_path}")

    try:
        asyncio.run(_run_async(spec, debug=debug, show_conversation=show_conversation))
    finally:
        if log_file is not None:
            sys.stdout = orig_stdout
            sys.stderr = orig_stderr
            log_file.close()
            print(f"[runner] log written to {log_path}")
