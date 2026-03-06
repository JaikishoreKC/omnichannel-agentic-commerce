from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationRecord:
    expected_intent: str
    predicted_intent: str
    confidence: float
    action_match: bool


class ConfusionMatrixCollector:
    """Collects intent/action diagnostics for NL eval tests."""

    def __init__(self) -> None:
        self._records: list[EvaluationRecord] = []

    def record(
        self,
        *,
        expected_intent: str,
        predicted_intent: str,
        confidence: float,
        action_match: bool,
    ) -> None:
        self._records.append(
            EvaluationRecord(
                expected_intent=str(expected_intent),
                predicted_intent=str(predicted_intent),
                confidence=max(0.0, min(1.0, float(confidence))),
                action_match=bool(action_match),
            )
        )

    @property
    def total_predictions(self) -> int:
        return len(self._records)

    def intent_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self._records:
            counts[row.expected_intent] = counts.get(row.expected_intent, 0) + 1
        return counts

    def confusion_matrix(self) -> dict[tuple[str, str], int]:
        matrix: dict[tuple[str, str], int] = {}
        for row in self._records:
            key = (row.expected_intent, row.predicted_intent)
            matrix[key] = matrix.get(key, 0) + 1
        return matrix

    def per_intent_stats(self) -> dict[str, dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}
        for row in self._records:
            bucket = stats.setdefault(
                row.expected_intent,
                {
                    "total": 0,
                    "intent_correct": 0,
                    "action_correct": 0,
                    "confidence_sum": 0.0,
                },
            )
            bucket["total"] += 1
            if row.predicted_intent == row.expected_intent:
                bucket["intent_correct"] += 1
            if row.action_match:
                bucket["action_correct"] += 1
            bucket["confidence_sum"] += row.confidence

        for intent, bucket in stats.items():
            total = int(bucket["total"]) or 1
            bucket["intent_accuracy"] = bucket["intent_correct"] / total
            bucket["action_accuracy"] = bucket["action_correct"] / total
            bucket["avg_confidence"] = bucket["confidence_sum"] / total
            bucket["intent"] = intent

        return stats

    def low_confidence_misroutes(self, *, threshold: float = 0.7) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        floor = max(0.0, min(1.0, float(threshold)))
        for row in self._records:
            if row.predicted_intent == row.expected_intent:
                continue
            if row.confidence > floor:
                continue
            rows.append(
                {
                    "expected": row.expected_intent,
                    "predicted": row.predicted_intent,
                    "confidence": row.confidence,
                }
            )
        return rows

    def render_report(self) -> str:
        if not self._records:
            return "No diagnostics available."

        lines: list[str] = []
        lines.append("NL eval diagnostics summary")
        lines.append(f"total_predictions={self.total_predictions}")

        stats = self.per_intent_stats()
        for intent in sorted(stats):
            row = stats[intent]
            lines.append(
                "intent={intent} total={total} intent_acc={intent_acc:.3f} action_acc={action_acc:.3f} avg_conf={avg_conf:.3f}".format(
                    intent=intent,
                    total=row["total"],
                    intent_acc=row["intent_accuracy"],
                    action_acc=row["action_accuracy"],
                    avg_conf=row["avg_confidence"],
                )
            )

        low_conf = self.low_confidence_misroutes(threshold=0.7)
        lines.append(f"low_confidence_misroutes={len(low_conf)}")
        return "\n".join(lines)
