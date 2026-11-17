# EU Laws Q&A Assistant

A Q&A assistant over the following EU legislation:

- **AI Act** – Regulation (EU) 2024/1689
- **GDPR** – Regulation (EU) 2016/679
- **Digital Omnibus on AI** – Regulation (EU) 2026/1744

The Digital Omnibus on AI directly amends the AI Act, but it is stored as a
separate source document rather than merged into a consolidated AI Act text.

## Data

Sources are listed in `sources.yaml`. Raw EUR-Lex HTML files are stored in
`data/raw/`, and `src/raw_data_extractor.py` parses them into JSONL files in
`data/parsed/`.

**Note:** The gold Q&A dataset was generated synthetically to speed up development. For a more reliable evaluation, it should be replaced or supplemented with human-written questions.

## Setup

    uv sync
