"""Domain exceptions for the payment service layer."""


class TransactionError(Exception):
    """Base exception for transaction errors."""

    pass


class InvalidTransitionError(TransactionError):
    """Raised when a state transition is not valid per the state machine."""

    def __init__(self, current_state: str, target_state: str):
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(f"Invalid transition from '{current_state}' to '{target_state}'")


class ConcurrencyError(TransactionError):
    """Raised when an optimistic concurrency conflict is detected (version mismatch)."""

    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        super().__init__(f"Concurrent modification detected for transaction '{transaction_id}'")


class TransactionNotFoundError(TransactionError):
    """Raised when a transaction is not found."""

    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        super().__init__(f"Transaction '{transaction_id}' not found")
