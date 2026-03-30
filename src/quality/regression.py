"""Quality regression testing: run evaluation against a set of test files.

Tracks quality scores across prompt/code versions to detect regressions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from src.utils.paths import get_data_dir

_RESULTS_DIR = get_data_dir() / "data" / "eval_results"


class EvalResult(BaseModel):
    file_name: str = ""
    source_language: str = ""
    target_language: str = ""
    style: str = ""
    domain: str = ""
    faithfulness: float = 0.0
    fluency: float = 0.0
    terminology_consistency: float = 0.0
    style_consistency: float = 0.0
    format_integrity: float = 0.0
    overall: float = 0.0


class RegressionRun(BaseModel):
    run_id: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    prompt_version: str = ""
    results: list[EvalResult] = Field(default_factory=list)
    average_overall: float = 0.0
    notes: str = ""

    def compute_average(self) -> None:
        if self.results:
            self.average_overall = sum(r.overall for r in self.results) / len(
                self.results
            )


class RegressionTracker:
    """Persist and compare quality regression runs."""

    def __init__(self, results_dir: str | Path | None = None) -> None:
        self._dir = Path(results_dir) if results_dir else _RESULTS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run: RegressionRun) -> str:
        run.compute_average()
        path = self._dir / f"{run.run_id}.json"
        path.write_text(
            json.dumps(run.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Saved regression run %s (avg=%.1f)", run.run_id, run.average_overall)
        return str(path)

    def load_runs(self) -> list[RegressionRun]:
        runs: list[RegressionRun] = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                runs.append(RegressionRun(**data))
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("Skipping corrupt run file %s: %s", p.name, e)
        return runs

    def compare_latest(self) -> dict[str, Any] | None:
        """Compare the two most recent runs. Returns delta info or None."""
        runs = self.load_runs()
        if len(runs) < 2:
            return None

        prev, curr = runs[-2], runs[-1]
        delta = curr.average_overall - prev.average_overall
        return {
            "previous": {
                "run_id": prev.run_id,
                "average": prev.average_overall,
            },
            "current": {
                "run_id": curr.run_id,
                "average": curr.average_overall,
            },
            "delta": delta,
            "improved": delta > 0,
            "regressed": delta < -2.0,
        }
