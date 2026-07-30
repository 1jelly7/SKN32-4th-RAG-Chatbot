class EmbeddingClient:
    def __init__(self, api_key: str, model: str) -> None:
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


def embed(texts: list[str]) -> list[list[float]]:
    ...
