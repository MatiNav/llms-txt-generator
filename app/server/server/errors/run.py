class RunNotCompletedError(Exception):
    def __init__(
        self, *, run_state: str, message: str = "Run is not completed yet"
    ) -> None:
        super().__init__(message)
        self.run_state = run_state

    def to_response_detail(self) -> dict[str, str | bool]:
        can_retry = self.run_state != "failed"
        return {
            "code": "RUN_NOT_COMPLETED",
            "message": str(self),
            "state": self.run_state,
            "can_retry": can_retry,
        }
