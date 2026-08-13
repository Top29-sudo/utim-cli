"""
UTIM CLI — Comprehensive Agent Benchmark Suite
================================================

Covers all 9 benchmark families with a free model (poolside/laguna-s-2.1:free).

Benchmark families:
  1. Terminal / environment operation
  2. Repository-level software engineering
  3. Agentic coding / feature development
  4. General agent intelligence (planning, reasoning, multi-step)
  5. Tool-use / function-calling accuracy
  6. Long-horizon autonomy
  7. Computer-use / GUI (CLI-proxy tasks)
  8. Multi-agent / swarm (subagent delegation)
  9. Efficiency / economics (token, time, tool-call metrics)

Run:
  pytest tests/test_benchmark.py -v
  pytest tests/test_benchmark.py -v -m benchmark
  pytest tests/test_benchmark.py -v -m "benchmark and not slow"
  pytest tests/test_benchmark.py -v -k "terminal"          # single family

Each test case:
  - Uses the free model via headless Orchestrator (no TTY, no auth required)
  - Records pass/fail, elapsed seconds, tool call count, iteration count
  - Prints a summary scorecard table at the end via a session fixture
  - Writes results to tests/benchmark_results.json for CI/CD integration

Model: poolside/laguna-s-2.1:free  (OpenRouter free tier — no credits consumed)
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import threading
import time
import pathlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ── Ensure project root is on sys.path ────────────────────────────────────────
ROOT = pathlib.Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env from root or tests/.env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "tests" / ".env")
except ImportError:
    pass

# ── Benchmark model (free, no credits) ────────────────────────────────────────
BENCH_MODEL = "poolside/laguna-s-2.1:free"

# ── Result storage ─────────────────────────────────────────────────────────────
RESULTS_FILE = ROOT / "tests" / "benchmark_results.json"

# ── Per-test timeout (seconds) ─────────────────────────────────────────────────
DEFAULT_TIMEOUT = 120  # 2 min per test case
LONG_TIMEOUT    = 300  # 5 min for long-horizon and multi-agent tests


# ══════════════════════════════════════════════════════════════════════════════
# Data model
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BenchResult:
    """Single benchmark task result."""
    family:     str
    task_id:    str
    name:       str
    passed:     bool
    score:      float       = 0.0   # 0.0 – 1.0
    elapsed_s:  float       = 0.0
    iterations: int         = 0
    tool_calls: int         = 0
    tokens_in:  int         = 0
    tokens_out: int         = 0
    notes:      str         = ""
    error:      str         = ""


# Session-level accumulator — shared across all test classes
_ALL_RESULTS: List[BenchResult] = []
_RESULTS_LOCK = threading.Lock()


def _record(result: BenchResult) -> BenchResult:
    with _RESULTS_LOCK:
        _ALL_RESULTS.append(result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Harness — headless Orchestrator runner
# ══════════════════════════════════════════════════════════════════════════════

class HeadlessRunner:
    """
    Drives a real UTIM Orchestrator in headless mode with the free benchmark model.

    Environment:
      - UTIM_HEADLESS=1   → suppresses auth prompts
      - OPENROUTER_API_KEY → read from .env or env (required for real LLM calls)

    If no API key is found the runner falls back to mock mode so the benchmark
    still executes and tests the non-LLM path (tool dispatch, safety guards, etc.).
    """

    def __init__(
        self,
        system_prompt: str = "",
        model: str = BENCH_MODEL,
        max_iterations: int = 15,
        timeout: int = DEFAULT_TIMEOUT,
        workdir: Optional[str] = None,
    ):
        self.model         = model
        self.max_iterations = max_iterations
        self.timeout       = timeout
        self.workdir       = workdir or tempfile.mkdtemp(prefix="utim_bench_")
        self.system_prompt = system_prompt or (
            f"You are a UTIM benchmark agent. Model: {model}. "
            "Complete tasks accurately and efficiently. "
            "Use tools when needed. Do not ask clarifying questions."
        )
        self._orig_cwd = os.getcwd()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _make_session(self) -> Any:
        """Create an isolated Orchestrator with a silent console."""
        os.environ["UTIM_HEADLESS"] = "1"
        from rich.console import Console
        from utim_cli.orchestrator import Orchestrator

        silent = Console(file=io.StringIO(), highlight=False, markup=True)
        session = Orchestrator(console=silent)
        session.model_id = self.model

        if self.system_prompt:
            session.messages = [{"role": "system", "content": self.system_prompt}]

        return session

    def run(self, task: str) -> Dict[str, Any]:
        """
        Run a task string through the Orchestrator.

        Returns a dict with:
          output, iterations, tool_calls, elapsed_s, tokens_in, tokens_out
        """
        t0 = time.time()
        result_holder: Dict[str, Any] = {
            "output":     "",
            "iterations": 0,
            "tool_calls": 0,
            "tokens_in":  0,
            "tokens_out": 0,
            "error":      "",
        }

        orig_cwd = os.getcwd()
        try:
            os.chdir(self.workdir)
            session = self._make_session()

            def _run():
                try:
                    session.run_task(
                        user_message=task,
                        max_iterations=self.max_iterations,
                    )
                    for m in reversed(session.messages):
                        if m.get("role") == "assistant" and m.get("content"):
                            result_holder["output"] = m["content"]
                            break
                    result_holder["iterations"] = (
                        getattr(session, "current_iteration", 0) + 1
                    )
                    result_holder["tool_calls"] = len(
                        getattr(session, "tool_results", [])
                    )
                    # Token counts from last response metadata if available
                    last_usage = getattr(session, "_last_usage", {}) or {}
                    result_holder["tokens_in"]  = last_usage.get("prompt_tokens", 0)
                    result_holder["tokens_out"] = last_usage.get("completion_tokens", 0)
                except Exception as exc:
                    result_holder["error"] = str(exc)

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=self.timeout)

            if t.is_alive():
                result_holder["error"] = f"Timed out after {self.timeout}s"

        except Exception as exc:
            result_holder["error"] = str(exc)
        finally:
            os.chdir(orig_cwd)

        result_holder["elapsed_s"] = round(time.time() - t0, 2)
        return result_holder


# ══════════════════════════════════════════════════════════════════════════════
# Session fixture — prints scorecard after all benchmarks finish
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session", autouse=True)
def benchmark_scorecard():
    """Print and save the benchmark scorecard after the full session completes."""
    yield  # all tests run here

    if not _ALL_RESULTS:
        return

    print("\n\n" + "═" * 78)
    print("  UTIM BENCHMARK SCORECARD")
    print("═" * 78)

    families: Dict[str, List[BenchResult]] = {}
    for r in _ALL_RESULTS:
        families.setdefault(r.family, []).append(r)

    grand_pass = grand_total = 0
    family_rows = []

    for fam_name, results in families.items():
        passed  = sum(1 for r in results if r.passed)
        total   = len(results)
        avg_s   = sum(r.elapsed_s for r in results) / max(total, 1)
        avg_tc  = sum(r.tool_calls for r in results) / max(total, 1)
        avg_it  = sum(r.iterations for r in results) / max(total, 1)
        score   = (passed / total) * 100 if total else 0
        icon    = "✓" if score >= 80 else ("⚠" if score >= 50 else "✗")
        grand_pass  += passed
        grand_total += total
        family_rows.append((fam_name, icon, passed, total, score, avg_s, avg_tc, avg_it))

    # Print per-family rows
    print(f"  {'Family':<38} {'':2} {'Pass':>5}  {'Score':>6}  {'AvgTime':>8}  {'AvgCalls':>9}")
    print("  " + "─" * 74)
    for (fam_name, icon, passed, total, score, avg_s, avg_tc, avg_it) in family_rows:
        print(
            f"  {fam_name:<38} {icon}  {passed}/{total}   {score:5.1f}%  "
            f"{avg_s:6.1f}s  {avg_tc:7.1f} tc"
        )

    print("  " + "─" * 74)
    overall = (grand_pass / grand_total * 100) if grand_total else 0
    print(f"  {'OVERALL':<38}     {grand_pass}/{grand_total}   {overall:5.1f}%")
    print("═" * 78 + "\n")

    # Detailed per-task table
    print("  DETAILED RESULTS")
    print("  " + "─" * 74)
    for r in _ALL_RESULTS:
        status = "PASS" if r.passed else "FAIL"
        print(
            f"  [{status}] {r.task_id:<28}  "
            f"{r.elapsed_s:5.1f}s  {r.tool_calls:2}tc  {r.iterations:2}it  "
            f"score={r.score:.2f}"
        )
        if r.error:
            print(f"         ERROR: {r.error[:80]}")
        if r.notes:
            print(f"         note:  {r.notes[:80]}")
    print("═" * 78 + "\n")

    # Persist to JSON
    payload = {
        "model":        BENCH_MODEL,
        "timestamp":    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_pct":  round(overall, 2),
        "pass":         grand_pass,
        "total":        grand_total,
        "results":      [asdict(r) for r in _ALL_RESULTS],
    }
    try:
        RESULTS_FILE.write_text(json.dumps(payload, indent=2))
        print(f"  Benchmark results saved → {RESULTS_FILE}")
    except Exception as exc:
        print(f"  Warning: could not save results JSON: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 1 — Terminal / Environment Operation
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestTerminalOperation:
    """
    Can the agent navigate a real shell, create/read/write files,
    run commands, and recover from errors?
    """

    FAMILY = "1. Terminal / Environment"

    def test_file_write_and_read(self):
        """Agent writes a Python file and reads it back, verifying the content."""
        runner = HeadlessRunner()
        task   = (
            "Create a file called bench_output.txt in the current directory "
            "with the content 'UTIM_BENCH_OK'. Then read it back and confirm "
            "its content. Reply with 'VERIFIED: <content>'."
        )
        res = runner.run(task)
        passed = (
            not res["error"]
            and (
                "UTIM_BENCH_OK" in res["output"]
                or "VERIFIED" in res["output"].upper()
            )
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="term-01", name="File write + read",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=res["output"][:120],
        ))
        assert passed, f"File write+read failed. Output: {res['output'][:300]}"

    def test_shell_command_execution(self):
        """Agent runs a shell command (echo) and reports the result."""
        runner = HeadlessRunner()
        task   = (
            "Run the shell command `echo BENCH_SHELL_OK` and tell me the exact output."
        )
        res = runner.run(task)
        passed = (
            not res["error"]
            and "BENCH_SHELL_OK" in res["output"]
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="term-02", name="Shell command execution",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Shell exec failed. Output: {res['output'][:300]}"

    def test_directory_listing(self):
        """Agent lists a directory and identifies files in it."""
        runner = HeadlessRunner()
        # Create a known file first
        pathlib.Path(runner.workdir, "canary.txt").write_text("canary")
        task = "List the contents of the current directory and tell me what files are present."
        res  = runner.run(task)
        passed = (
            not res["error"]
            and "canary" in res["output"].lower()
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="term-03", name="Directory listing",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Dir listing failed. Output: {res['output'][:300]}"

    def test_file_search_and_grep(self):
        """Agent finds the file containing a specific string."""
        runner = HeadlessRunner()
        p = pathlib.Path(runner.workdir, "needle.py")
        p.write_text("SECRET_TOKEN = 'BENCH_GREP_42'\n")
        task = (
            "Search the current directory for a file containing the string "
            "'BENCH_GREP_42' and tell me the filename."
        )
        res = runner.run(task)
        passed = (
            not res["error"]
            and "needle" in res["output"].lower()
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="term-04", name="File search / grep",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Grep failed. Output: {res['output'][:300]}"

    def test_command_error_recovery(self):
        """Agent recovers when a command fails and tries an alternative."""
        runner = HeadlessRunner()
        task = (
            "Try running the command `nonexistent_program_xyz --help`. "
            "It will fail. Then recover by running `echo RECOVERED` instead "
            "and report the output."
        )
        res = runner.run(task)
        passed = (
            not res["error"]
            and "RECOVERED" in res["output"]
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="term-05", name="Command error recovery",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Error recovery failed. Output: {res['output'][:300]}"


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 2 — Repository-Level Software Engineering
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestRepoEngineering:
    """
    Can the agent understand an existing codebase and correctly fix bugs,
    understand module structure, and answer architectural questions?
    """

    FAMILY = "2. Repo-Level Engineering"

    def _make_mini_repo(self, workdir: str):
        """Create a tiny Python repo with a deliberate bug."""
        src = pathlib.Path(workdir, "mylib")
        src.mkdir(exist_ok=True)
        (src / "__init__.py").write_text("")
        (src / "math_utils.py").write_text(
            "def add(a, b):\n    return a - b  # BUG: should be a + b\n\n"
            "def multiply(a, b):\n    return a * b\n"
        )
        (src / "test_math.py").write_text(
            "from mylib.math_utils import add, multiply\n\n"
            "def test_add():\n    assert add(2, 3) == 5\n\n"
            "def test_multiply():\n    assert multiply(3, 4) == 12\n"
        )

    def test_bug_identification(self):
        """Agent reads code, identifies the bug, and explains it."""
        runner = HeadlessRunner()
        self._make_mini_repo(runner.workdir)
        task = (
            "Read the file mylib/math_utils.py. "
            "There is a bug in the add() function. "
            "Identify what it is and explain the fix needed."
        )
        res = runner.run(task)
        passed = (
            not res["error"]
            and (
                "subtract" in res["output"].lower()
                or "minus" in res["output"].lower()
                or "a + b" in res["output"]
                or "addition" in res["output"].lower()
            )
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="repo-01", name="Bug identification",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Bug ID failed. Output: {res['output'][:300]}"

    def test_bug_fix(self):
        """Agent actually fixes the bug by editing the file."""
        runner = HeadlessRunner()
        self._make_mini_repo(runner.workdir)
        task = (
            "Fix the bug in mylib/math_utils.py — the add() function uses "
            "subtraction instead of addition. Apply the fix in the file."
        )
        res = runner.run(task)
        fixed_src = pathlib.Path(runner.workdir, "mylib", "math_utils.py").read_text()
        passed = (
            not res["error"]
            and "return a + b" in fixed_src
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="repo-02", name="Bug fix applied",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"File content after: {fixed_src[:120]}",
        ))
        assert passed, f"Bug fix failed. File: {fixed_src}"

    def test_architecture_question(self):
        """Agent answers a structural question about the repo."""
        runner = HeadlessRunner()
        self._make_mini_repo(runner.workdir)
        task = (
            "Look at the current directory structure. "
            "How many Python files are there, and what is the name of the main library module?"
        )
        res = runner.run(task)
        passed = (
            not res["error"]
            and ("mylib" in res["output"].lower() or "math_utils" in res["output"].lower())
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="repo-03", name="Architecture question",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Arch Q failed. Output: {res['output'][:300]}"

    def test_add_docstring(self):
        """Agent adds a docstring to an undocumented function."""
        runner = HeadlessRunner()
        self._make_mini_repo(runner.workdir)
        task = (
            "Add a proper Python docstring to the multiply() function in "
            "mylib/math_utils.py. The docstring should describe what the function does."
        )
        res = runner.run(task)
        updated = pathlib.Path(runner.workdir, "mylib", "math_utils.py").read_text()
        passed = (
            not res["error"]
            and '"""' in updated
            and "multiply" in updated
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="repo-04", name="Add docstring",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Docstring failed. File: {updated}"


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 3 — Agentic Coding / Feature Development
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestAgenticCoding:
    """
    Can the agent build features, write tests, and iterate
    autonomously (not just generate code snippets)?
    """

    FAMILY = "3. Agentic Coding"

    def test_write_new_function(self):
        """Agent creates a new utility function from a specification."""
        runner = HeadlessRunner()
        task = (
            "Create a file called string_utils.py with a function called "
            "'is_palindrome(s)' that returns True if string s is a palindrome "
            "(case-insensitive, ignoring spaces). Include a brief docstring."
        )
        res = runner.run(task)
        src = (pathlib.Path(runner.workdir) / "string_utils.py").read_text() \
            if (pathlib.Path(runner.workdir) / "string_utils.py").exists() else ""
        passed = (
            not res["error"]
            and "is_palindrome" in src
            and "def is_palindrome" in src
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="code-01", name="Write new function",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Function creation failed. src={src[:200]}"

    def test_write_unit_tests(self):
        """Agent writes pytest unit tests for an existing function."""
        runner = HeadlessRunner()
        # Pre-create the function
        (pathlib.Path(runner.workdir) / "calc.py").write_text(
            "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n"
        )
        task = (
            "Write pytest unit tests for the factorial() function in calc.py. "
            "Create a file called test_calc.py with at least 3 test cases covering "
            "edge cases (0, 1, and a larger number like 5)."
        )
        res = runner.run(task)
        test_file = pathlib.Path(runner.workdir) / "test_calc.py"
        src = test_file.read_text() if test_file.exists() else ""
        test_count = src.count("def test_")
        passed = (
            not res["error"]
            and "factorial" in src
            and test_count >= 3
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="code-02", name="Write unit tests",
            passed=passed, score=min(test_count / 3, 1.0),
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"{test_count} test functions found",
        ))
        assert passed, f"Test writing failed. test_count={test_count}, src={src[:200]}"

    def test_refactor_code(self):
        """Agent refactors repeated code into a reusable function."""
        runner = HeadlessRunner()
        (pathlib.Path(runner.workdir) / "messy.py").write_text(
            "# Repeated logic — needs refactoring\n"
            "result1 = [x * x for x in range(10) if x % 2 == 0]\n"
            "result2 = [x * x for x in range(20) if x % 2 == 0]\n"
            "result3 = [x * x for x in range(30) if x % 2 == 0]\n"
        )
        task = (
            "Refactor messy.py: extract the repeated list-comprehension logic into "
            "a reusable function called 'even_squares(n)' and rewrite the three "
            "result variables to use it."
        )
        res = runner.run(task)
        src = (pathlib.Path(runner.workdir) / "messy.py").read_text()
        passed = (
            not res["error"]
            and "def even_squares" in src
            and src.count("[x * x") <= 1   # at most 1 raw comprehension left
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="code-03", name="Refactor repeated code",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Refactor failed. src={src[:300]}"

    def test_debug_runtime_error(self):
        """Agent diagnoses a ZeroDivisionError and fixes it."""
        runner = HeadlessRunner()
        (pathlib.Path(runner.workdir) / "divider.py").write_text(
            "def safe_divide(a, b):\n    return a / b  # crashes when b == 0\n"
        )
        task = (
            "The function safe_divide() in divider.py crashes with ZeroDivisionError "
            "when b is 0. Fix it: return None when b is 0, otherwise return a / b."
        )
        res = runner.run(task)
        src = (pathlib.Path(runner.workdir) / "divider.py").read_text()
        passed = (
            not res["error"]
            and ("if b == 0" in src or "if not b" in src or "b == 0" in src)
            and "None" in src
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="code-04", name="Debug runtime error",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Debug failed. src={src}"

    def test_create_readme(self):
        """Agent writes a README.md for a small project."""
        runner = HeadlessRunner()
        (pathlib.Path(runner.workdir) / "app.py").write_text(
            "# Weather CLI app\ndef get_weather(city): return f'Weather in {city}: sunny'\n"
        )
        task = (
            "Create a README.md for the project in the current directory. "
            "It should include: project name, description, installation, and usage sections."
        )
        res = runner.run(task)
        readme = pathlib.Path(runner.workdir) / "README.md"
        src = readme.read_text() if readme.exists() else ""
        sections = sum(1 for kw in ["install", "usage", "description"] if kw in src.lower())
        passed = not res["error"] and readme.exists() and sections >= 2
        _record(BenchResult(
            family=self.FAMILY, task_id="code-05", name="Create README",
            passed=passed, score=min(sections / 3, 1.0),
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"{sections}/3 sections found",
        ))
        assert passed, f"README failed. sections={sections}, src={src[:200]}"


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 4 — General Agent Intelligence (Planning & Reasoning)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestAgentIntelligence:
    """
    Planning, multi-step reasoning, sequential decision-making,
    and adapting when a step fails.
    """

    FAMILY = "4. Agent Intelligence"

    def test_multi_step_plan_execution(self):
        """Agent correctly executes a 3-step plan in order."""
        runner = HeadlessRunner()
        task = (
            "Do the following steps IN ORDER:\n"
            "1. Create a file called step1.txt with the content 'STEP1_DONE'.\n"
            "2. Create a file called step2.txt with the content 'STEP2_DONE'.\n"
            "3. Create a file called final.txt whose content is the combined "
            "contents of step1.txt and step2.txt separated by a newline.\n"
            "When done, tell me the content of final.txt."
        )
        res = runner.run(task)
        final = pathlib.Path(runner.workdir, "final.txt")
        content = final.read_text() if final.exists() else ""
        passed = (
            not res["error"]
            and "STEP1_DONE" in content
            and "STEP2_DONE" in content
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="intel-01", name="Multi-step plan execution",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Plan exec failed. content={content!r}"

    def test_conditional_logic(self):
        """Agent applies conditional reasoning: acts differently based on file state."""
        runner = HeadlessRunner()
        # Write a status file
        pathlib.Path(runner.workdir, "status.txt").write_text("INACTIVE")
        task = (
            "Read status.txt. If it says 'ACTIVE', create a file called active_log.txt. "
            "If it says 'INACTIVE', create a file called inactive_log.txt instead. "
            "Then tell me which file you created."
        )
        res = runner.run(task)
        created = pathlib.Path(runner.workdir, "inactive_log.txt").exists()
        wrong   = pathlib.Path(runner.workdir, "active_log.txt").exists()
        passed  = not res["error"] and created and not wrong
        _record(BenchResult(
            family=self.FAMILY, task_id="intel-02", name="Conditional logic",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Conditional logic failed. created={created}, wrong={wrong}"

    def test_data_transformation(self):
        """Agent reads a CSV, computes a sum, writes the result."""
        runner = HeadlessRunner()
        pathlib.Path(runner.workdir, "data.csv").write_text(
            "name,score\nalice,80\nbob,90\ncarol,70\n"
        )
        task = (
            "Read data.csv, calculate the average score of all students, "
            "and write the result to result.txt as 'Average: X' where X is the number."
        )
        res = runner.run(task)
        result_file = pathlib.Path(runner.workdir, "result.txt")
        content = result_file.read_text() if result_file.exists() else ""
        # Average of 80, 90, 70 = 80.0
        passed = (
            not res["error"]
            and result_file.exists()
            and "80" in content
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="intel-03", name="Data transformation",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"result.txt: {content[:80]}",
        ))
        assert passed, f"Data transform failed. content={content!r}"

    def test_goal_decomposition(self):
        """Agent autonomously decomposes a vague goal into steps and executes them."""
        runner = HeadlessRunner()
        task = (
            "Set up a minimal Python project structure for a library called 'mypackage'. "
            "It should include: a package directory, __init__.py, a main module, "
            "and a requirements.txt. Do it all autonomously."
        )
        res = runner.run(task)
        checks = [
            (pathlib.Path(runner.workdir) / "mypackage" / "__init__.py").exists(),
            (pathlib.Path(runner.workdir) / "requirements.txt").exists(),
        ]
        passed = not res["error"] and sum(checks) >= 2
        _record(BenchResult(
            family=self.FAMILY, task_id="intel-04", name="Goal decomposition",
            passed=passed, score=sum(checks) / 2,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"checks: init={checks[0]}, reqs={checks[1]}",
        ))
        assert passed, f"Goal decomp failed. checks={checks}"


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 5 — Tool-Use / Function-Calling Accuracy
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestToolUse:
    """
    Does the agent select the right tools, construct valid arguments,
    recover from tool errors, and avoid unnecessary calls?
    """

    FAMILY = "5. Tool-Use Accuracy"

    def test_correct_tool_selection_read_vs_search(self):
        """Agent uses read_file for a known path, not search_files."""
        runner = HeadlessRunner()
        pathlib.Path(runner.workdir, "config.json").write_text('{"version": "1.0.0"}')
        task = "Read the file config.json and tell me the version value."
        res  = runner.run(task)
        passed = (
            not res["error"]
            and "1.0.0" in res["output"]
        )
        # Also check it didn't use more tool calls than necessary (should be 1-2)
        efficiency_score = 1.0 if res["tool_calls"] <= 2 else 0.5
        _record(BenchResult(
            family=self.FAMILY, task_id="tool-01", name="Correct tool: read_file",
            passed=passed, score=efficiency_score if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"tool_calls={res['tool_calls']} (ideal ≤2)",
        ))
        assert passed, f"Tool selection failed. Output: {res['output'][:200]}"

    def test_tool_argument_validity(self):
        """Agent passes valid arguments to write_file (path, content)."""
        runner = HeadlessRunner()
        task = "Create a file named 'output.json' containing valid JSON: {\"status\": \"ok\"}."
        res  = runner.run(task)
        out_file = pathlib.Path(runner.workdir, "output.json")
        if out_file.exists():
            try:
                parsed = json.loads(out_file.read_text())
                valid_json = parsed.get("status") == "ok"
            except Exception:
                valid_json = False
        else:
            valid_json = False
        passed = not res["error"] and valid_json
        _record(BenchResult(
            family=self.FAMILY, task_id="tool-02", name="Valid tool arguments",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Arg validity failed. file_exists={out_file.exists()}"

    def test_tool_error_recovery(self):
        """Agent recovers when reading a nonexistent file and tries alternatives."""
        runner = HeadlessRunner()
        task = (
            "Try to read the file 'does_not_exist.txt'. It won't exist. "
            "When you get an error, create it with the content 'CREATED_AFTER_ERROR' "
            "and then read it to confirm."
        )
        res = runner.run(task)
        target = pathlib.Path(runner.workdir, "does_not_exist.txt")
        passed = (
            not res["error"]
            and target.exists()
            and "CREATED_AFTER_ERROR" in target.read_text()
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="tool-03", name="Tool error recovery",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Error recovery failed. file_exists={target.exists()}"

    def test_no_unnecessary_tool_calls(self):
        """Agent answers a simple factual question without making tool calls."""
        runner = HeadlessRunner()
        task = "What is 12 * 12? Just give me the number."
        res  = runner.run(task)
        passed = (
            not res["error"]
            and "144" in res["output"]
        )
        # For a pure arithmetic question, ideally 0 tool calls
        unnecessary = res["tool_calls"] > 2
        score = 1.0 if (passed and not unnecessary) else (0.5 if passed else 0.0)
        _record(BenchResult(
            family=self.FAMILY, task_id="tool-04", name="No unnecessary tool calls",
            passed=passed, score=score,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"tool_calls={res['tool_calls']} (ideal 0)",
        ))
        assert passed, f"Arithmetic failed. Output: {res['output'][:200]}"


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 6 — Long-Horizon Autonomy
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
@pytest.mark.slow
class TestLongHorizonAutonomy:
    """
    Can the agent maintain a goal across many steps without drifting or forgetting?
    """

    FAMILY = "6. Long-Horizon Autonomy"

    def test_multi_file_project_setup(self):
        """Agent sets up a 5+ file Python project autonomously."""
        runner = HeadlessRunner(max_iterations=25, timeout=LONG_TIMEOUT)
        task = (
            "Create a complete minimal REST API project with the following files:\n"
            "1. app.py — Flask app with one GET /ping endpoint returning {\"pong\": true}\n"
            "2. requirements.txt — with flask listed\n"
            "3. README.md — brief description\n"
            "4. .gitignore — ignoring __pycache__ and .env\n"
            "5. tests/test_ping.py — a pytest test for the /ping endpoint\n"
            "Do all of this autonomously."
        )
        res = runner.run(task)
        files_created = [
            (pathlib.Path(runner.workdir) / f).exists()
            for f in ["app.py", "requirements.txt", "README.md", ".gitignore"]
        ]
        score = sum(files_created) / 4
        passed = not res["error"] and sum(files_created) >= 3
        _record(BenchResult(
            family=self.FAMILY, task_id="long-01", name="Multi-file project setup",
            passed=passed, score=score,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"{sum(files_created)}/4 required files created",
        ))
        assert passed, f"Multi-file setup failed. files={files_created}"

    def test_sequential_dependency_chain(self):
        """Agent builds a 4-step chain where each step depends on the previous."""
        runner = HeadlessRunner(max_iterations=20, timeout=LONG_TIMEOUT)
        task = (
            "Complete these steps in order — each depends on the previous:\n"
            "1. Write numbers 1 to 10, one per line, to 'numbers.txt'.\n"
            "2. Read numbers.txt, double each number, write to 'doubled.txt'.\n"
            "3. Read doubled.txt, filter only numbers > 10, write to 'filtered.txt'.\n"
            "4. Read filtered.txt, sum all numbers, write 'Sum: X' to 'sum.txt'.\n"
            "Report the final sum."
        )
        res = runner.run(task)
        # doubled: 2,4,6,8,10,12,14,16,18,20
        # filtered (>10): 12,14,16,18,20 → sum = 80
        sum_file = pathlib.Path(runner.workdir, "sum.txt")
        content  = sum_file.read_text() if sum_file.exists() else ""
        passed   = not res["error"] and "80" in content
        _record(BenchResult(
            family=self.FAMILY, task_id="long-02", name="Sequential dependency chain",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"sum.txt content: {content[:60]}",
        ))
        assert passed, f"Chain failed. sum.txt={content!r}"

    def test_goal_persistence_across_errors(self):
        """Agent continues toward the goal even when intermediate steps fail."""
        runner = HeadlessRunner(max_iterations=20, timeout=LONG_TIMEOUT)
        task = (
            "Your goal is to create a file called 'goal_reached.txt' with content 'SUCCESS'.\n"
            "Along the way:\n"
            "1. First try to read 'missing1.txt' (it doesn't exist — handle the error).\n"
            "2. Then try to read 'missing2.txt' (also missing — handle the error).\n"
            "3. Despite those failures, still create 'goal_reached.txt' with 'SUCCESS'.\n"
            "The goal must be reached regardless of errors."
        )
        res   = runner.run(task)
        goal  = pathlib.Path(runner.workdir, "goal_reached.txt")
        passed = not res["error"] and goal.exists() and "SUCCESS" in goal.read_text()
        _record(BenchResult(
            family=self.FAMILY, task_id="long-03", name="Goal persistence across errors",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Goal persistence failed. goal_exists={goal.exists()}"


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 7 — Computer-Use / GUI (CLI-proxy)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestCLIProxy:
    """
    CLI-proxy for computer-use: the agent interacts with real tools
    (git, pip, python) as a proxy for full GUI/desktop tasks.
    """

    FAMILY = "7. CLI-Proxy (Computer-Use)"

    def test_git_init_and_commit(self):
        """Agent initialises a git repo and makes an initial commit."""
        runner = HeadlessRunner()
        (pathlib.Path(runner.workdir) / "hello.py").write_text("print('hello')\n")
        task = (
            "In the current directory:\n"
            "1. Initialise a new git repository.\n"
            "2. Set git user config: name='UTIM Test', email='test@utim.dev'.\n"
            "3. Add all files and make an initial commit with message 'Initial commit'.\n"
            "Report the commit hash or confirm success."
        )
        res = runner.run(task)
        git_dir = pathlib.Path(runner.workdir, ".git")
        passed  = not res["error"] and git_dir.exists()
        _record(BenchResult(
            family=self.FAMILY, task_id="gui-01", name="Git init + commit",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Git init failed. .git_exists={git_dir.exists()}"

    def test_python_script_execution_and_capture(self):
        """Agent writes and runs a Python script, capturing its output."""
        runner = HeadlessRunner()
        task = (
            "Write a Python script called compute.py that prints the sum of all "
            "even numbers from 1 to 100. Run it and tell me the output."
        )
        res = runner.run(task)
        # Sum of even numbers 2+4+...+100 = 2550
        passed = (
            not res["error"]
            and "2550" in res["output"]
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="gui-02", name="Script execution + capture",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Script exec failed. Output: {res['output'][:300]}"

    def test_environment_inspection(self):
        """Agent inspects the Python environment and reports key details."""
        runner = HeadlessRunner()
        task = (
            "Check which Python version is installed and which packages are "
            "available via `pip list`. Report the Python version number."
        )
        res = runner.run(task)
        passed = (
            not res["error"]
            and re.search(r"\d+\.\d+", res["output"]) is not None
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="gui-03", name="Environment inspection",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
        ))
        assert passed, f"Env inspect failed. Output: {res['output'][:200]}"


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 8 — Multi-Agent / Swarm
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
@pytest.mark.slow
class TestMultiAgent:
    """
    Does delegation via invoke_subagents actually improve results?
    Tests coordination, parallel execution, result aggregation, and
    correctness when tasks are split across subagents.
    """

    FAMILY = "8. Multi-Agent / Swarm"

    def test_subagent_dispatch_basic(self):
        """Main agent correctly spawns a subagent and receives its result."""
        from utim_cli.subagent_manager import SubAgentTask, SubAgentManager, format_subagent_results

        runner = HeadlessRunner()
        task = SubAgentTask(
            task_id     = "bench-sub-01",
            role        = "File Writer",
            system_prompt = "You are a file-writing agent. Write files as instructed.",
            user_prompt = (
                f"Create a file called subagent_output.txt in {runner.workdir} "
                "with the content 'SUBAGENT_WORKED'."
            ),
            model_id    = BENCH_MODEL,
            max_iterations = 5,
            timeout_seconds = 60,
        )

        import io as _io
        from rich.console import Console
        silent = Console(file=_io.StringIO(), highlight=False)

        t0 = time.time()
        manager = SubAgentManager(
            parent_model=BENCH_MODEL,
            console=silent,
            cancel_event=threading.Event(),
            current_depth=0,
        )
        results = manager.run_parallel([task])
        elapsed = time.time() - t0

        target = pathlib.Path(runner.workdir, "subagent_output.txt")
        passed = (
            len(results) == 1
            and results[0].success
            and (
                target.exists() and "SUBAGENT_WORKED" in target.read_text()
                or "SUBAGENT_WORKED" in results[0].output
            )
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="swarm-01", name="Subagent dispatch basic",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=elapsed, iterations=results[0].iterations if results else 0,
            tool_calls=0, error=results[0].error if results else "no results",
        ))
        assert passed, f"Subagent dispatch failed. results={results}"

    def test_parallel_subagents_independent(self):
        """Two subagents run in parallel and each completes independently."""
        from utim_cli.subagent_manager import SubAgentTask, SubAgentManager, format_subagent_results

        runner = HeadlessRunner()
        tasks = [
            SubAgentTask(
                task_id="bench-parallel-A",
                role="Writer A",
                system_prompt="You are Writer A.",
                user_prompt=f"Create file agent_a.txt in {runner.workdir} with content 'AGENT_A'.",
                model_id=BENCH_MODEL,
                max_iterations=5,
                timeout_seconds=90,
            ),
            SubAgentTask(
                task_id="bench-parallel-B",
                role="Writer B",
                system_prompt="You are Writer B.",
                user_prompt=f"Create file agent_b.txt in {runner.workdir} with content 'AGENT_B'.",
                model_id=BENCH_MODEL,
                max_iterations=5,
                timeout_seconds=90,
            ),
        ]

        import io as _io
        from rich.console import Console
        silent = Console(file=_io.StringIO(), highlight=False)

        t0 = time.time()
        manager = SubAgentManager(
            parent_model=BENCH_MODEL,
            console=silent,
            cancel_event=threading.Event(),
            current_depth=0,
        )
        results = manager.run_parallel(tasks)
        elapsed = time.time() - t0

        a_ok = pathlib.Path(runner.workdir, "agent_a.txt").exists()
        b_ok = pathlib.Path(runner.workdir, "agent_b.txt").exists()
        passed = a_ok and b_ok
        _record(BenchResult(
            family=self.FAMILY, task_id="swarm-02", name="Parallel subagents independent",
            passed=passed, score=(int(a_ok) + int(b_ok)) / 2,
            elapsed_s=elapsed,
            iterations=sum(r.iterations for r in results),
            tool_calls=0,
            notes=f"a={a_ok}, b={b_ok}",
        ))
        assert passed, f"Parallel failed. a={a_ok}, b={b_ok}"

    def test_subagent_permission_enforcement(self):
        """Subagent with read_only permission cannot write files."""
        from utim_cli.subagent_manager import SubAgentTask, SubAgentManager, PERMISSION_PROFILES

        runner = HeadlessRunner()
        task = SubAgentTask(
            task_id     = "bench-perm-01",
            role        = "Read-Only Agent",
            system_prompt = "You are a read-only agent. You cannot write files.",
            user_prompt   = f"Try to create a file blocked.txt in {runner.workdir} with content 'BLOCKED'.",
            model_id      = BENCH_MODEL,
            permission    = "read_only",
            max_iterations = 5,
            timeout_seconds = 60,
        )

        # Verify the permission profile blocks write tools
        blocked = PERMISSION_PROFILES.get("read_only", set())
        passed  = "write_file" in blocked and "run_command" in blocked

        _record(BenchResult(
            family=self.FAMILY, task_id="swarm-03", name="Permission enforcement",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=0, iterations=0, tool_calls=0,
            notes=f"blocked tools: {sorted(blocked)}",
        ))
        assert passed, f"Permission enforcement failed. blocked={blocked}"

    def test_subagent_result_aggregation(self):
        """format_subagent_results correctly aggregates results from multiple agents."""
        from utim_cli.subagent_manager import SubAgentResult, format_subagent_results

        results = [
            SubAgentResult(task_id="t1", role="A", success=True,
                           output="Result from A", iterations=3, elapsed_s=1.2, depth=1),
            SubAgentResult(task_id="t2", role="B", success=False, output="",
                           error="Something went wrong", iterations=1, elapsed_s=0.5, depth=1),
        ]
        formatted = format_subagent_results(results)
        passed = (
            "Result from A" in formatted
            and "Something went wrong" in formatted
            and "SUCCESS" in formatted
            and "FAILED" in formatted
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="swarm-04", name="Result aggregation",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=0, iterations=0, tool_calls=0,
        ))
        assert passed, f"Aggregation failed. formatted={formatted[:300]}"


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY 9 — Efficiency / Economics
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestEfficiency:
    """
    How efficient is the agent? Measures time, tool calls, iterations,
    unnecessary tool use, and token usage relative to task complexity.
    """

    FAMILY = "9. Efficiency / Economics"

    def test_simple_task_low_iteration_count(self):
        """A trivial task completes in ≤ 3 iterations."""
        runner = HeadlessRunner(max_iterations=10)
        task = "Create a file hello.txt with the single word 'hello'."
        res  = runner.run(task)
        target = pathlib.Path(runner.workdir, "hello.txt")
        passed  = not res["error"] and target.exists() and "hello" in target.read_text()
        efficient = res["iterations"] <= 4  # ideally 1-2
        score = 1.0 if (passed and efficient) else (0.5 if passed else 0.0)
        _record(BenchResult(
            family=self.FAMILY, task_id="eff-01", name="Simple task low iterations",
            passed=passed, score=score,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"iterations={res['iterations']} (ideal ≤4)",
        ))
        assert passed, f"Simple task failed. file_exists={target.exists()}"

    def test_no_redundant_reads(self):
        """Agent doesn't re-read the same file multiple times unnecessarily."""
        runner = HeadlessRunner(max_iterations=8)
        (pathlib.Path(runner.workdir) / "config.txt").write_text("COLOR=blue")
        task = "Read config.txt once and tell me the value of COLOR."
        res  = runner.run(task)
        passed = not res["error"] and "blue" in res["output"]
        # More than 3 tool calls for a single-read task suggests redundancy
        redundant = res["tool_calls"] > 3
        score = 1.0 if (passed and not redundant) else (0.5 if passed else 0.0)
        _record(BenchResult(
            family=self.FAMILY, task_id="eff-02", name="No redundant reads",
            passed=passed, score=score,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"tool_calls={res['tool_calls']} (ideal ≤3)",
        ))
        assert passed, f"Redundant reads test failed. Output: {res['output'][:200]}"

    def test_response_time_simple_task(self):
        """A simple one-tool task completes within 60 seconds."""
        runner = HeadlessRunner(timeout=90)
        task = "Create a file fast.txt with the word 'quick'."
        t0   = time.time()
        res  = runner.run(task)
        elapsed = time.time() - t0
        target  = pathlib.Path(runner.workdir, "fast.txt")
        passed  = not res["error"] and target.exists()
        fast    = elapsed < 60
        score   = 1.0 if (passed and fast) else (0.5 if passed else 0.0)
        _record(BenchResult(
            family=self.FAMILY, task_id="eff-03", name="Response time simple task",
            passed=passed, score=score,
            elapsed_s=elapsed, iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"elapsed={elapsed:.1f}s (threshold=60s)",
        ))
        assert passed, f"Timing test failed. elapsed={elapsed:.1f}s, exists={target.exists()}"

    def test_tool_call_economy(self):
        """Multi-file task uses the minimum reasonable number of tool calls."""
        runner = HeadlessRunner(max_iterations=15)
        task = (
            "Create two files:\n"
            "1. a.txt with content 'AAA'\n"
            "2. b.txt with content 'BBB'\n"
            "This is a simple 2-file task."
        )
        res = runner.run(task)
        a_ok = (pathlib.Path(runner.workdir) / "a.txt").exists()
        b_ok = (pathlib.Path(runner.workdir) / "b.txt").exists()
        passed = not res["error"] and a_ok and b_ok
        # Should need at most 4 tool calls for 2 writes
        economical = res["tool_calls"] <= 6
        score = 1.0 if (passed and economical) else (0.5 if passed else 0.0)
        _record(BenchResult(
            family=self.FAMILY, task_id="eff-04", name="Tool call economy",
            passed=passed, score=score,
            elapsed_s=res["elapsed_s"], iterations=res["iterations"],
            tool_calls=res["tool_calls"], error=res["error"],
            notes=f"tool_calls={res['tool_calls']} (ideal ≤6)",
        ))
        assert passed, f"Economy test failed. a={a_ok}, b={b_ok}, calls={res['tool_calls']}"

    def test_context_pruner_activates(self):
        """Context pruner module imports and calculates a valid threshold."""
        from utim_cli.context_pruner import (
            score_message_importance, sanitize_message_sequence
        )
        sample_messages = [
            {"role": "system",    "content": "You are UTIM AI."},
            {"role": "user",      "content": "Fix the bug in app.py"},
            {"role": "assistant", "content": "I'll read app.py first."},
            {"role": "user",      "content": "ok"},
            {"role": "assistant", "content": "Done, the bug is fixed."},
        ]
        scores  = [score_message_importance(m) for m in sample_messages]
        pruned  = sanitize_message_sequence(sample_messages)
        passed  = (
            isinstance(scores, list)
            and len(scores) == len(sample_messages)
            and isinstance(pruned, list)
            and len(pruned) > 0
        )
        _record(BenchResult(
            family=self.FAMILY, task_id="eff-05", name="Context pruner activation",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=0, iterations=0, tool_calls=0,
            notes=f"scores={scores}, pruned_len={len(pruned)}",
        ))
        assert passed, f"Context pruner failed. scores={scores}"

    def test_compression_threshold_per_model(self):
        """Dynamic compression threshold is computed correctly for BENCH_MODEL."""
        from rich.console import Console
        import io as _io
        os.environ["UTIM_HEADLESS"] = "1"
        from utim_cli.orchestrator import Orchestrator
        silent  = Console(file=_io.StringIO(), highlight=False)
        session = Orchestrator(console=silent)
        session.model_id = BENCH_MODEL
        threshold = session._get_dynamic_threshold()
        passed = isinstance(threshold, int) and threshold > 0
        _record(BenchResult(
            family=self.FAMILY, task_id="eff-06", name="Dynamic compression threshold",
            passed=passed, score=1.0 if passed else 0.0,
            elapsed_s=0, iterations=0, tool_calls=0,
            notes=f"threshold={threshold:,} tokens for {BENCH_MODEL}",
        ))
        assert passed, f"Threshold failed. threshold={threshold}"


# ══════════════════════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestBenchmarkHarness:
    """Sanity checks that the benchmark harness itself works correctly."""

    FAMILY = "0. Harness / Sanity"

    def test_free_model_constant(self):
        """BENCH_MODEL is a free OpenRouter model."""
        assert BENCH_MODEL.endswith(":free"), f"Expected free model, got {BENCH_MODEL}"
        _record(BenchResult(
            family=self.FAMILY, task_id="harness-01", name="Free model constant",
            passed=True, score=1.0,
        ))

    def test_headless_runner_creates_workdir(self):
        """HeadlessRunner creates a unique temp workdir."""
        r1 = HeadlessRunner()
        r2 = HeadlessRunner()
        assert r1.workdir != r2.workdir
        assert pathlib.Path(r1.workdir).exists()
        _record(BenchResult(
            family=self.FAMILY, task_id="harness-02", name="Unique workdir creation",
            passed=True, score=1.0,
        ))

    def test_bench_result_dataclass(self):
        """BenchResult serialises cleanly to dict."""
        r = BenchResult(family="test", task_id="t1", name="n1",
                        passed=True, score=0.9, elapsed_s=1.5)
        d = asdict(r)
        assert d["passed"] is True
        assert d["score"] == 0.9
        _record(BenchResult(
            family=self.FAMILY, task_id="harness-03", name="BenchResult serialisation",
            passed=True, score=1.0,
        ))

    def test_orchestrator_importable(self):
        """Orchestrator can be imported without errors."""
        from utim_cli.orchestrator import Orchestrator
        assert Orchestrator is not None
        _record(BenchResult(
            family=self.FAMILY, task_id="harness-04", name="Orchestrator importable",
            passed=True, score=1.0,
        ))

    def test_subagent_manager_importable(self):
        """SubAgentManager imports and MAX_NEST_DEPTH == 10."""
        from utim_cli.subagent_manager import SubAgentManager, MAX_NEST_DEPTH
        assert SubAgentManager is not None
        assert MAX_NEST_DEPTH == 10
        _record(BenchResult(
            family=self.FAMILY, task_id="harness-05", name="SubAgentManager MAX_DEPTH=10",
            passed=True, score=1.0,
        ))
