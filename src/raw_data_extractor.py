"""Parse raw EUR-Lex HTML pages listed in sources.yaml into JSONL files.

For every source, writes data/parsed/<key_prefix>_<YYYY_MM_DD>.jsonl with one
record per recital, article and annex:

    {"id", "doc", "kind", "title", "text", "url"}

Usage:
    uv run python src/raw_data_extractor.py [--sources sources.yaml] [--out data/parsed]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import warnings
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

# EUR-Lex serves XHTML; the lenient HTML parser handles it fine.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

REPO_ROOT = Path(__file__).resolve().parent.parent

KIND_MAP = {"rct": "recital", "art": "article", "anx": "annex"}

_WS_RE = re.compile(r"\s+")


def clean(text: str) -> str:
    """Collapse whitespace (incl. non-breaking spaces) into single spaces."""
    return _WS_RE.sub(" ", text.replace("\xa0", " ")).strip()


def innermost_row(el: Tag, stop: Tag) -> Tag | None:
    """Closest enclosing <tr> of `el` that lies inside `stop`."""
    for parent in el.parents:
        if parent is stop:
            return None
        if parent.name == "tr":
            return parent
    return None


def is_excluded(p: Tag, section: Tag) -> bool:
    """Headings and titles are not part of the body text."""
    classes = p.get("class") or []
    if "oj-ti-art" in classes or "oj-doc-ti" in classes:
        return True
    for parent in p.parents:
        if parent is section:
            return False
        if "eli-title" in (parent.get("class") or []):
            return True
    return False


def extract_text(section: Tag) -> str:
    """Body text of a section built from its <p> tags.

    Paragraphs in the same table row (e.g. "(a)" + "point text") are joined with
    a space; everything else is separated by newlines. Table cells holding text
    without a <p> (used in annexes) are treated as paragraphs too.
    """
    leaves = [
        el
        for el in section.find_all(["p", "td"])
        if (el.name == "p" and not is_excluded(el, section))
        or (el.name == "td" and not el.find(["p", "table"]) and clean(el.get_text()))
    ]

    lines: list[str] = []
    prev_row: Tag | None = None
    for leaf in leaves:
        text = clean(leaf.get_text())
        if not text:
            continue
        row = innermost_row(leaf, section)
        if lines and row is not None and row is prev_row:
            lines[-1] = f"{lines[-1]} {text}"
        else:
            lines.append(text)
        prev_row = row
    return "\n".join(lines)


def extract_title(section: Tag, kind: str) -> str | None:
    title_div = section.find("div", class_="eli-title")
    if title_div is not None:
        p = title_div.find("p")
        return clean((p or title_div).get_text(" "))
    if kind == "anx":
        # Annexes have no eli-title: first oj-doc-ti is "ANNEX I", the next one is the title.
        doc_titles = section.find_all("p", class_="oj-doc-ti", recursive=False)
        if len(doc_titles) > 1:
            return clean(" ".join(p.get_text(" ") for p in doc_titles[1:]))
    return None


def iter_sections(soup: BeautifulSoup):
    """Recitals/articles are eli-subdivision divs; annexes are eli-container divs."""
    for div in soup.find_all("div", class_=["eli-subdivision", "eli-container"]):
        div_id = div.get("id", "")
        kind = div_id.split("_", 1)[0]
        if kind not in KIND_MAP:
            continue
        classes = div.get("class") or []
        if kind == "anx" and "eli-container" not in classes:
            continue
        if kind != "anx" and "eli-subdivision" not in classes:
            continue
        yield div_id, kind, div


def parse_source(source: dict) -> list[dict]:
    raw_path = REPO_ROOT / source["raw_path"]
    soup = BeautifulSoup(raw_path.read_text(encoding="utf-8"), "lxml")

    records = []
    for div_id, kind, div in iter_sections(soup):
        records.append(
            {
                "id": f"{source['key_prefix']}_{div_id}",
                "doc": source["title"],
                "kind": KIND_MAP[kind],
                "title": extract_title(div, kind),
                "text": extract_text(div),
                "url": f"{source['url']}#{div_id}",
            }
        )
    return records


def output_name(source: dict) -> str:
    downloaded = source["downloaded"]
    if isinstance(downloaded, str):
        downloaded = dt.date.fromisoformat(downloaded)
    return f"{source['key_prefix'].lower()}_{downloaded:%Y_%m_%d}.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sources", type=Path, default=REPO_ROOT / "sources.yaml")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "parsed")
    args = parser.parse_args()

    sources = yaml.safe_load(args.sources.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)

    for source in sources:
        records = parse_source(source)
        out_path = args.out / output_name(source)
        with out_path.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        counts = {k: sum(r["kind"] == k for r in records) for k in KIND_MAP.values()}
        print(f"{source['title']}: {len(records)} records {counts} -> {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
