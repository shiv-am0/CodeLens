"""The same LF line definition drives ingestion, citations and exact reads."""
import re


def lines(text: str) -> list[str]:
    parts = text.split("\n")
    return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def chunks(rows: list[str]):
    start = 0
    size = 0
    for index, row in enumerate(rows):
        if index > start and (index - start >= 80 or size + len(row) > 8192):
            yield start + 1, index, "".join(rows[start:index])
            start = index
            size = 0
        size += len(row)
    if start < len(rows):
        yield start + 1, len(rows), "".join(rows[start:])


def expression(query: str) -> str:
    if len(query) > 512:
        raise ValueError("Query exceeds 512 characters.")
    terms = re.findall(r"[^\W_]+", query)
    if not terms:
        raise ValueError("Enter a query containing letters or digits.")
    return " AND ".join(f'"{term}"' for term in terms)
