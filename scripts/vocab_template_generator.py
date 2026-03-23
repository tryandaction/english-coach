#!/usr/bin/env python3
"""
Vocabulary Acquisition Guide and Template Generator

This script helps create properly formatted vocabulary markdown files
for the English Coach platform. It provides templates and validation
for TOEFL, IELTS, GRE, and CET vocabulary lists.

Usage:
    python scripts/vocab_template_generator.py --exam toefl --output toefl_sample.md
"""

import argparse
from pathlib import Path


VOCAB_TEMPLATE = """---
exam: {exam}
difficulty: {difficulty}
source: {source}
topic: {topic}
---
word|definition_en|definition_zh|example|pos|synonyms|antonyms
"""

EXAM_CONFIGS = {
    "toefl": {
        "difficulty": "B2-C1",
        "topics": ["academic", "stem", "humanities", "social_sciences"],
        "target_words": 8000,
        "sources": [
            "Academic Word List (AWL)",
            "ETS Official TOEFL Word List",
            "COCA Academic Corpus",
            "TOEFL iBT Official Guide"
        ]
    },
    "ielts": {
        "difficulty": "B1-C1",
        "topics": ["academic", "general", "collocations"],
        "target_words": 6000,
        "sources": [
            "Cambridge IELTS Vocabulary",
            "Academic Collocation List (ACL)",
            "General Service List (GSL)",
            "IELTS Official Practice Materials"
        ]
    },
    "gre": {
        "difficulty": "C1-C2",
        "topics": ["academic", "advanced"],
        "target_words": 3500,
        "sources": [
            "Barron's GRE Word List",
            "Magoosh GRE Vocabulary",
            "Manhattan Prep GRE Vocabulary"
        ]
    },
    "cet4": {
        "difficulty": "B1-B2",
        "topics": ["general", "academic"],
        "target_words": 4500,
        "sources": [
            "教育部大学英语四级考试大纲",
            "Past CET-4 high-frequency words",
            "新东方 CET-4 vocabulary"
        ]
    },
    "cet6": {
        "difficulty": "B2-C1",
        "topics": ["general", "academic"],
        "target_words": 6000,
        "sources": [
            "教育部大学英语六级考试大纲",
            "Past CET-6 high-frequency words",
            "新东方 CET-6 vocabulary"
        ]
    }
}

SAMPLE_ENTRIES = {
    "toefl": [
        "analyze|examine methodically and in detail|分析|Researchers analyze data to identify patterns.|verb|examine,study,investigate|ignore,overlook",
        "hypothesis|a proposed explanation for a phenomenon|假设|The scientist tested her hypothesis through experiments.|noun|theory,assumption,proposition|fact,proof",
        "significant|sufficiently great to be worthy of attention|显著的|The study found a significant correlation.|adj|notable,substantial,meaningful|insignificant,trivial"
    ],
    "ielts": [
        "accommodate|provide lodging or sufficient space for|容纳;提供住宿|The hotel can accommodate 200 guests.|verb|house,lodge,hold|reject,refuse",
        "approximately|close to the actual but not exact|大约|The journey takes approximately two hours.|adv|roughly,about,nearly|exactly,precisely",
        "demonstrate|clearly show the existence of something|证明;展示|The experiment demonstrates the principle.|verb|show,prove,illustrate|hide,conceal"
    ],
    "cet4": [
        "abandon|give up completely|放弃|She abandoned her plan to study abroad.|verb|give up,quit,desert|continue,pursue",
        "ability|the power or skill to do something|能力|He has the ability to solve complex problems.|noun|skill,capacity,talent|inability",
        "absorb|take in or soak up|吸收|Plants absorb sunlight to produce energy.|verb|soak up,take in,assimilate|release,emit"
    ],
    "cet6": [
        "abstract|existing in thought rather than concrete|抽象的|Philosophy deals with abstract concepts.|adj|theoretical,conceptual,intangible|concrete,tangible",
        "accelerate|increase in speed or rate|加速|The car accelerated rapidly.|verb|speed up,quicken,hasten|decelerate,slow",
        "accumulate|gather together or acquire gradually|积累|Snow accumulated overnight.|verb|collect,gather,amass|disperse,scatter"
    ]
}


def generate_template(exam: str, source: str, topic: str, output_path: Path):
    """Generate a vocabulary template file."""
    config = EXAM_CONFIGS.get(exam.lower())
    if not config:
        print(f"Error: Unknown exam type '{exam}'. Valid options: {', '.join(EXAM_CONFIGS.keys())}")
        return

    # Create template content
    content = VOCAB_TEMPLATE.format(
        exam=exam.lower(),
        difficulty=config["difficulty"],
        source=source or f"{exam.upper()}_source",
        topic=topic or config["topics"][0]
    )

    # Add sample entries
    if exam.lower() in SAMPLE_ENTRIES:
        content += "\n".join(SAMPLE_ENTRIES[exam.lower()])
        content += "\n"

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    print(f"[OK] Template created: {output_path}")
    print(f"\nTarget word count: {config['target_words']}")
    print(f"Recommended sources:")
    for src in config["sources"]:
        print(f"  - {src}")
    print(f"\nAvailable topics: {', '.join(config['topics'])}")


def print_acquisition_guide():
    """Print comprehensive vocabulary acquisition guide."""
    guide = """
================================================================================
                    VOCABULARY ACQUISITION GUIDE
================================================================================

This guide helps you source and prepare vocabulary lists for the English Coach
platform to meet professional exam preparation standards.

--------------------------------------------------------------------------------

CURRENT STATUS

Exam Type    Current Words    Target Words    Gap         Priority
--------------------------------------------------------------------------------
TOEFL        47              8,000-10,000    ~7,950      [CRITICAL]
IELTS        48              6,000-8,000     ~5,950      [CRITICAL]
CET-4        45              4,500           ~4,455      [HIGH]
CET-6        51              6,000           ~5,950      [HIGH]
GRE          13,862          3,500+          [Met]       [COMPLETE]

--------------------------------------------------------------------------------

VOCABULARY SOURCES

1. TOEFL (Target: 8,000-10,000 words)

   Official Sources:
   • Academic Word List (AWL) by Averil Coxhead
     URL: https://www.wgtn.ac.nz/lals/resources/academicwordlist
     Words: 570 families (~2,000 with derivatives)

   • ETS TOEFL Official Resources
     URL: https://www.ets.org/toefl/test-takers/ibt/prepare.html
     Note: Check for official word lists in preparation materials

   • Corpus of Contemporary American English (COCA) - Academic
     URL: https://www.english-corpora.org/coca/
     Filter: Academic subcorpus, frequency list

   Open-Access Options:
   • Wiktionary frequency lists (academic English)
   • Project Gutenberg academic texts (extract vocabulary)
   • OpenStax textbooks (STEM vocabulary)

2. IELTS (Target: 6,000-8,000 words)

   Official Sources:
   • Cambridge IELTS Vocabulary in Use series (check licensing)
   • Academic Collocation List (ACL)
     URL: http://www.pearsonpte.com/organizations/researchers/academic-collocation-list

   • General Service List (GSL) - 2,000 most common words
     URL: http://jbauman.com/gsl.html (public domain)

   Open-Access Options:
   • British National Corpus (BNC) frequency lists
   • BBC Learning English vocabulary archives
   • IELTS Liz free vocabulary lists (with attribution)

3. CET-4/6 (Target: 4,500 / 6,000 words)

   Official Sources:
   • 教育部大学英语四级/六级考试大纲 (Official syllabus - public domain)
     Available from: 中国教育考试网

   • Past exam high-frequency word analysis
     Compile from publicly available past papers

   Open-Access Options:
   • 新东方在线 free vocabulary lists (with attribution)
   • 小站教育 free resources (with attribution)
   • Quizlet public CET-4/6 decks (verify licensing)

--------------------------------------------------------------------------------

AI-ASSISTED VOCABULARY GENERATION

If sourcing is difficult, use AI to generate vocabulary lists:

Prompt Template:
"Generate a list of 100 {exam} vocabulary words at {difficulty} level
focusing on {topic}. For each word provide:
- English definition
- Chinese definition (for CET only)
- Example sentence in academic context
- Part of speech
- 2-3 synonyms
- 1-2 antonyms

Format as pipe-delimited: word|definition_en|definition_zh|example|pos|synonyms|antonyms"

Recommended Models:
• GPT-4 / Claude (high quality, higher cost)
• DeepSeek-Chat (good quality, lower cost - recommended)
• Qwen (Chinese exams, good for CET-4/6)

Cost Estimate:
• 10,000 words × $0.0001/word ≈ $1-5 total (using DeepSeek)

--------------------------------------------------------------------------------

QUALITY CHECKLIST

Before importing vocabulary files, verify:

[ ] File format matches template (YAML frontmatter + pipe-delimited)
[ ] All required fields present (word, definition_en, example, pos)
[ ] Chinese definitions included for CET-4/6
[ ] Example sentences are contextually appropriate
[ ] Difficulty level matches CEFR standards
[ ] Source attribution documented
[ ] No copyrighted content without permission
[ ] Word count meets target for exam type

--------------------------------------------------------------------------------

QUICK START

1. Generate a template:
   python scripts/vocab_template_generator.py --exam toefl --output toefl_sample.md

2. Fill in vocabulary entries (manually or via AI)

3. Validate format:
   python scripts/validate_vocab.py toefl_sample.md

4. Import to database:
   python -m core.ingestion.pipeline --vocab toefl_sample.md

5. Enrich with AI:
   python scripts/enrich_vocabulary.py --exam toefl --batch-size 100

--------------------------------------------------------------------------------

NEED HELP?

* Check existing files in content/vocab_expanded/ for examples
* Review README.md in content/vocab_expanded/
* Refer to main project documentation

================================================================================
"""
    print(guide)


def main():
    parser = argparse.ArgumentParser(
        description="Generate vocabulary templates and acquisition guide"
    )
    parser.add_argument(
        "--exam",
        choices=["toefl", "ielts", "gre", "cet4", "cet6"],
        help="Exam type for template generation"
    )
    parser.add_argument(
        "--source",
        help="Source name for the vocabulary list"
    )
    parser.add_argument(
        "--topic",
        help="Topic/domain for the vocabulary"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path for template"
    )
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Print vocabulary acquisition guide"
    )

    args = parser.parse_args()

    if args.guide or not args.exam:
        print_acquisition_guide()
        return

    if args.exam and args.output:
        generate_template(args.exam, args.source, args.topic, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
