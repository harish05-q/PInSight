from typing import Any


def compute_precision_recall(
    retrieved: list[dict[str, Any]], expected: list[dict[str, Any]]
) -> tuple[float, float]:
    """Compute precision and recall for evidence retrieval.

    Match criteria: deterministic equality on source_tool and source_ref.
    """
    if not expected and not retrieved:
        return 1.0, 1.0
    if not expected:
        return 0.0, 1.0
    if not retrieved:
        return 1.0, 0.0

    def normalize(ev):
        return (ev.get("source_tool", ""), ev.get("source_ref", ""))

    expected_set = {normalize(e) for e in expected}
    retrieved_set = {normalize(e) for e in retrieved}

    true_positives = len(expected_set.intersection(retrieved_set))

    precision = true_positives / len(retrieved_set) if retrieved_set else 1.0
    recall = true_positives / len(expected_set) if expected_set else 1.0

    return precision, recall
