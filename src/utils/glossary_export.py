from __future__ import annotations

from src.models.glossary import Glossary


def build_glossary_table(glossary: Glossary) -> dict[str, list]:
    languages = glossary.resolved_target_languages
    columns = [
        "source",
        *languages,
        "category",
        "context",
        "frequency",
        "do_not_translate",
    ]
    rows: list[dict[str, object]] = []

    for term in glossary.terms:
        row: dict[str, object] = {
            "id": term.id,
            "source": term.source,
            "category": term.category,
            "context": term.context,
            "frequency": term.frequency,
            "do_not_translate": term.do_not_translate,
        }
        for language in languages:
            row[language] = term.get_target(language)
        rows.append(row)

    return {"columns": columns, "rows": rows}


def export_markdown(glossary: Glossary) -> str:
    table = build_glossary_table(glossary)
    columns = table["columns"]
    rows = table["rows"]
    if not rows:
        return ""

    def _escape(value: object) -> str:
        return str(value).replace("\n", " ").replace("|", "\\|")

    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = [
        "| " + " | ".join(_escape(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def export_tsv(glossary: Glossary) -> str:
    table = build_glossary_table(glossary)
    columns = table["columns"]
    rows = table["rows"]
    if not rows:
        return ""

    header = "\t".join(columns)
    body = [
        "\t".join(str(row.get(column, "")) for column in columns)
        for row in rows
    ]
    return "\n".join([header, *body])


def build_glossary_exports(glossary: Glossary) -> dict[str, object]:
    table = build_glossary_table(glossary)
    return {
        "columns": table["columns"],
        "rows": table["rows"],
        "markdown": export_markdown(glossary),
        "tsv": export_tsv(glossary),
    }
