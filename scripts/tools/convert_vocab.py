#!/usr/bin/env python3
"""
Convert downloaded vocabulary data to English Coach markdown format.
Format: word|definition_en|definition_zh|example|pos|synonyms|antonyms
"""

import json
import csv
import sys
from pathlib import Path

def convert_wordsta_json(json_file, output_file, exam_type, difficulty):
    """Convert wordsta JSON format to markdown."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    words = data.get('words', [])

    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"---\n")
        f.write(f"exam: {exam_type}\n")
        f.write(f"difficulty: {difficulty}\n")
        f.write(f"source: {Path(json_file).stem}\n")
        f.write(f"topic: general\n")
        f.write(f"---\n")
        f.write("word|definition_en|definition_zh|example|pos|synonyms|antonyms\n")

        # Write words
        for item in words:
            word = item.get('word', '').strip()
            definition = item.get('definition', '').strip()

            if not word or not definition:
                continue

            # Format: word|definition_en|definition_zh|example|pos|synonyms|antonyms
            # We only have word and definition, leave others empty for now
            line = f"{word}|{definition}||||\n"
            f.write(line)

    print(f"Converted {len(words)} words from {json_file} to {output_file}")

def convert_gre_csv(csv_file, output_file):
    """Convert GRE CSV format to markdown."""
    words_data = []

    with open(csv_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Format: word, pos, definition, example
            parts = [p.strip() for p in line.split(',', 3)]
            if len(parts) >= 3:
                word = parts[0]
                pos = parts[1] if len(parts) > 1 else ''
                definition = parts[2] if len(parts) > 2 else ''
                example = parts[3] if len(parts) > 3 else ''

                words_data.append({
                    'word': word,
                    'pos': pos,
                    'definition': definition,
                    'example': example
                })

    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"---\n")
        f.write(f"exam: gre\n")
        f.write(f"difficulty: C1\n")
        f.write(f"source: {Path(csv_file).stem}\n")
        f.write(f"topic: general\n")
        f.write(f"---\n")
        f.write("word|definition_en|definition_zh|example|pos|synonyms|antonyms\n")

        # Write words
        for item in words_data:
            word = item['word']
            definition = item['definition']
            example = item['example']
            pos = item['pos']

            line = f"{word}|{definition}||{example}|{pos}||\n"
            f.write(line)

    print(f"Converted {len(words_data)} words from {csv_file} to {output_file}")

def convert_gre_collection_csv(csv_file, output_file, exam_type='gre', difficulty='C1'):
    """Convert GRE collection CSV (just word list) to markdown."""
    words = []

    with open(csv_file, 'r', encoding='utf-8') as f:
        for line in f:
            word = line.strip()
            if word:
                words.append(word)

    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"---\n")
        f.write(f"exam: {exam_type}\n")
        f.write(f"difficulty: {difficulty}\n")
        f.write(f"source: {Path(csv_file).stem}\n")
        f.write(f"topic: general\n")
        f.write(f"---\n")
        f.write("word|definition_en|definition_zh|example|pos|synonyms|antonyms\n")

        # Write words (only word, no definition yet)
        for word in words:
            line = f"{word}|||||||\n"
            f.write(line)

    print(f"Converted {len(words)} words from {csv_file} to {output_file}")

def convert_oxford_txt(txt_file, output_file):
    """Convert Oxford 3000 text format to markdown."""
    words = []

    with open(txt_file, 'r', encoding='utf-8') as f:
        for line in f:
            word = line.strip()
            if word and not word.startswith('﻿'):
                words.append(word)

    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"---\n")
        f.write(f"exam: general\n")
        f.write(f"difficulty: B1-B2\n")
        f.write(f"source: oxford_3000\n")
        f.write(f"topic: general\n")
        f.write(f"---\n")
        f.write("word|definition_en|definition_zh|example|pos|synonyms|antonyms\n")

        # Write words (only word, no definition yet)
        for word in words:
            line = f"{word}|||||||\n"
            f.write(line)

    print(f"Converted {len(words)} words from {txt_file} to {output_file}")

if __name__ == '__main__':
    import os

    # Use Windows-compatible paths
    tmp_base = Path(os.environ.get('TEMP', '/tmp'))

    output_dir = Path('content/vocab_new')
    output_dir.mkdir(exist_ok=True)

    # Convert wordsta JSON files
    print("Converting wordsta JSON files...")
    convert_wordsta_json(tmp_base / 'wordsta/baron-334.json',
                        output_dir / 'gre_baron334.md', 'gre', 'C1')
    convert_wordsta_json(tmp_base / 'wordsta/baron-753.json',
                        output_dir / 'gre_baron753.md', 'gre', 'C1')
    convert_wordsta_json(tmp_base / 'wordsta/qitao-1787.json',
                        output_dir / 'gre_qitao1787.md', 'gre', 'C1')
    convert_wordsta_json(tmp_base / 'wordsta/vocabularydotcom-top-1000.json',
                        output_dir / 'general_vocab1000.md', 'general', 'B2-C1')

    # Convert GRE CSV
    print("\nConverting GRE CSV...")
    convert_gre_csv(tmp_base / 'gre/vocab.csv',
                   output_dir / 'gre_taklee.md')

    # Convert GRE collection CSVs
    print("\nConverting GRE collection CSVs...")
    convert_gre_collection_csv(tmp_base / 'gre-words-collection/word-list/006 Barrons-333.csv',
                              output_dir / 'gre_barrons333.md', 'gre', 'C1')
    convert_gre_collection_csv(tmp_base / 'gre-words-collection/word-list/008 Magoosh-1000.csv',
                              output_dir / 'gre_magoosh1000.md', 'gre', 'C1')
    convert_gre_collection_csv(tmp_base / 'gre-words-collection/word-list/combined.csv',
                              output_dir / 'gre_combined_9566.md', 'gre', 'C1')

    # Convert Oxford 3000
    print("\nConverting Oxford 3000...")
    convert_oxford_txt(tmp_base / 'The-Oxford-3000/The_Oxford_3000.txt',
                      output_dir / 'general_oxford3000.md')

    print("\n✅ Conversion complete!")
    print(f"Output directory: {output_dir.absolute()}")
