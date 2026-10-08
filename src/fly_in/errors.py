class FlyInError(Exception):
    pass


class ParseError(FlyInError):
    def __init__(self, l_n: int, msg: str) -> None:
        self.l_n = l_n
        self.msg = msg
        super().__init__(f"Line: {l_n} - {msg}")
