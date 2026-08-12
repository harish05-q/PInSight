"""Tests for evaluation metrics logic."""

from app.services.eval_service import compute_precision_recall


def test_compute_precision_recall_perfect_match():
    expected = [
        {"source_tool": "db", "source_ref": "ref1"},
        {"source_tool": "logs", "source_ref": "ref2"},
    ]
    retrieved = [
        {"source_tool": "db", "source_ref": "ref1", "claim": "x"},
        {"source_tool": "logs", "source_ref": "ref2", "claim": "y"},
    ]

    p, r = compute_precision_recall(retrieved, expected)
    assert p == 1.0
    assert r == 1.0


def test_compute_precision_recall_partial():
    expected = [
        {"source_tool": "db", "source_ref": "ref1"},
        {"source_tool": "logs", "source_ref": "ref2"},
    ]
    retrieved = [
        {"source_tool": "db", "source_ref": "ref1"},
        {"source_tool": "wrong", "source_ref": "wrong"},
    ]

    p, r = compute_precision_recall(retrieved, expected)
    assert p == 0.5  # 1 true positive / 2 retrieved
    assert r == 0.5  # 1 true positive / 2 expected


def test_compute_precision_recall_empty():
    p, r = compute_precision_recall([], [])
    assert p == 1.0
    assert r == 1.0

    p, r = compute_precision_recall([{"source_tool": "x"}], [])
    assert p == 0.0
    assert r == 1.0

    p, r = compute_precision_recall([], [{"source_tool": "x"}])
    assert p == 1.0
    assert r == 0.0
