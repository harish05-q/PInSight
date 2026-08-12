"""Unit tests for the transaction state machine.

These test the pure Python state machine logic (no DB required).
"""

import pytest

from app.models.transaction import (
    VALID_TRANSITIONS,
    TransactionState,
    get_valid_source_states,
    is_valid_transition,
)


class TestValidTransitions:
    """Test every valid transition in the state machine."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (TransactionState.AUTHORIZED, TransactionState.CAPTURED),
            (TransactionState.AUTHORIZED, TransactionState.FAILED),
            (TransactionState.AUTHORIZED, TransactionState.REFUNDED),
            (TransactionState.CAPTURED, TransactionState.SETTLED),
            (TransactionState.CAPTURED, TransactionState.REFUNDED),
            (TransactionState.CAPTURED, TransactionState.FAILED),
            (TransactionState.SETTLED, TransactionState.REFUNDED),
        ],
    )
    def test_valid_transition(self, current: TransactionState, target: TransactionState):
        assert is_valid_transition(current, target) is True


class TestInvalidTransitions:
    """Test every invalid transition in the state machine."""

    @pytest.mark.parametrize(
        "current,target",
        [
            # Self-transitions are invalid
            (TransactionState.AUTHORIZED, TransactionState.AUTHORIZED),
            (TransactionState.CAPTURED, TransactionState.CAPTURED),
            # Backward transitions
            (TransactionState.CAPTURED, TransactionState.AUTHORIZED),
            (TransactionState.SETTLED, TransactionState.AUTHORIZED),
            (TransactionState.SETTLED, TransactionState.CAPTURED),
            # Transitions from terminal states
            (TransactionState.REFUNDED, TransactionState.AUTHORIZED),
            (TransactionState.REFUNDED, TransactionState.CAPTURED),
            (TransactionState.REFUNDED, TransactionState.SETTLED),
            (TransactionState.REFUNDED, TransactionState.FAILED),
            (TransactionState.FAILED, TransactionState.AUTHORIZED),
            (TransactionState.FAILED, TransactionState.CAPTURED),
            (TransactionState.FAILED, TransactionState.SETTLED),
            (TransactionState.FAILED, TransactionState.REFUNDED),
            # Skip-ahead
            (TransactionState.AUTHORIZED, TransactionState.SETTLED),
        ],
    )
    def test_invalid_transition(self, current: TransactionState, target: TransactionState):
        assert is_valid_transition(current, target) is False


class TestTerminalStates:
    """Terminal states (refunded, failed) must reject all outgoing transitions."""

    def test_refunded_is_terminal(self):
        assert VALID_TRANSITIONS[TransactionState.REFUNDED] == set()

    def test_failed_is_terminal(self):
        assert VALID_TRANSITIONS[TransactionState.FAILED] == set()


class TestGetValidSourceStates:
    """Test reverse lookup: which states can reach a given target."""

    def test_sources_for_captured(self):
        sources = get_valid_source_states(TransactionState.CAPTURED)
        assert sources == {TransactionState.AUTHORIZED}

    def test_sources_for_refunded(self):
        sources = get_valid_source_states(TransactionState.REFUNDED)
        assert sources == {
            TransactionState.AUTHORIZED,
            TransactionState.CAPTURED,
            TransactionState.SETTLED,
        }

    def test_sources_for_settled(self):
        sources = get_valid_source_states(TransactionState.SETTLED)
        assert sources == {TransactionState.CAPTURED}

    def test_sources_for_failed(self):
        sources = get_valid_source_states(TransactionState.FAILED)
        assert sources == {TransactionState.AUTHORIZED, TransactionState.CAPTURED}

    def test_no_sources_for_authorized(self):
        """No state transitions TO authorized — it's the initial state only."""
        sources = get_valid_source_states(TransactionState.AUTHORIZED)
        assert sources == set()


class TestStateCompleteness:
    """Ensure the transition map covers all states."""

    def test_all_states_in_transition_map(self):
        for state in TransactionState:
            assert state in VALID_TRANSITIONS, f"{state} missing from VALID_TRANSITIONS"
