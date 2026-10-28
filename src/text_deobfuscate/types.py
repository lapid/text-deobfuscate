from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Step:
    """One accepted transform.

    ``start`` and ``end`` locate ``before`` in the text as it stood before this
    step, not in the original input.
    """

    transform: str
    start: int
    end: int
    before: str
    after: str
    confidence: float
    # Content the step removed from view but that the reader should know about,
    # such as text hidden in invisible characters.
    hidden: str | None = None


@dataclass(frozen=True, slots=True)
class Result:
    text: str
    steps: tuple[Step, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.steps)

    def to_dict(self) -> dict:
        return {"text": self.text, "steps": [asdict(step) for step in self.steps]}
