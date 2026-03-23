# Vocabulary Content Status

## Current Reality

This directory is **not** a fully validated "15k+ ready-to-study" vocabulary release.

As of 2026-03-15, the repository snapshot under:

- `content/vocab/`
- `content/vocab_selected/`
- `content/vocab_expanded/`

has the following measured status:

| Metric | Count |
|---|---:|
| Raw data rows declared in markdown tables | 23,662 |
| Usable rows with `definition_en` (importable) | 8,908 |
| Incomplete rows skipped during import | 14,754 |
| Importable unique words across all files | 3,500 |
| Cross-file duplicate words | 3,176 |

## Current Built-in Coverage

These are the current importable unique-word counts by exam bucket:

| Exam | Importable unique words |
|---|---:|
| TOEFL | 569 |
| IELTS | 243 |
| GRE | 2,326 |
| CET | 119 |
| General | 1,000 |

Important:

- These exam buckets **overlap**. Do not add them together and present the sum as the global unique vocabulary size.
- A large share of the raw rows in this folder are word-only entries without usable definitions.
- The app now treats those rows as incomplete content instead of pretending they are ready for study.

## Source Positioning

Current wording for these files should be:

- "repository-built markdown vocabulary files"
- "community-curated / project-curated content"
- "some files are partial or word-only"

Do **not** describe this folder as:

- an official ETS / Cambridge / Oxford / CET release
- a fully licensed commercial vocabulary database
- a complete TOEFL / IELTS / CET official wordlist package

If a file is based on a public list, keep that statement precise and limited to the specific file. Do not generalize it to the whole directory.

## Import Rules Used by the App

The app currently imports only rows that have:

- `word`
- `definition_en`

Current governance behavior:

- normalize duplicate words by lowercase `word`
- keep user-created word entries intact
- reuse user-created words inside built-in books when the same word appears
- merge only better/more complete fields into existing non-user entries

## What This Directory Is Good For

- powering the current built-in vocabulary demo/library
- validating wordbook grouping, metadata, import, and dedup logic
- serving as a maintainable markdown-based vocabulary source tree

## What Still Needs Work

- filling missing English definitions in large word-only files
- reducing duplicate coverage across GRE files
- improving TOEFL / IELTS / CET usable coverage
- adding clearer provenance per file

Last verified: 2026-03-15
