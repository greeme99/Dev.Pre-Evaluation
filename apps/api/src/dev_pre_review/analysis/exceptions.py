"""StepFailed exception for controlled step failures."""


class StepFailed(Exception):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code
