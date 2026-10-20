class FlyInError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(f"FlyInError: {msg}")


class ParseError(FlyInError):
    def __init__(self, l_n: int, msg: str) -> None:
        self.l_n = l_n
        self.msg = msg
        super().__init__(f"Line: {l_n} - {msg}")


class UnsolvableMapError(FlyInError):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class SimulationError(FlyInError):
    def __init__(self, turn: int, msg: str):
        super().__init__(f"Turn: {turn}: {msg}")
