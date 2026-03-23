from __future__ import annotations

import re
from pathlib import Path

from core.vocab.catalog import VOCAB_HEADERS, parse_vocab_markdown

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
OUTPUT_DIR = CONTENT_DIR / "vocab_selected"

GENERAL_PATH = OUTPUT_DIR / "general_vocab1000.md"
TOEFL_BASE_PATH = CONTENT_DIR / "vocab" / "toefl_awl.md"
TOEFL_PATH = CONTENT_DIR / "vocab_expanded" / "toefl_awl_academic.md"
TOEFL_STEM_PATH = CONTENT_DIR / "vocab_expanded" / "toefl_stem_complete.md"
IELTS_BASE_PATH = CONTENT_DIR / "vocab" / "ielts_academic.md"
IELTS_PATH = CONTENT_DIR / "vocab_expanded" / "ielts_academic_complete.md"
CET_PATHS = [
    CONTENT_DIR / "vocab" / "cet4_core.md",
    CONTENT_DIR / "vocab" / "cet6_core.md",
    CONTENT_DIR / "vocab_expanded" / "cet4_official_complete.md",
    CONTENT_DIR / "vocab_expanded" / "cet6_official_complete.md",
]
GRE_BASE_PATH = CONTENT_DIR / "vocab" / "gre_highfreq.md"
GRE_SELECTED_PATHS = [
    OUTPUT_DIR / "gre_baron334.md",
    OUTPUT_DIR / "gre_baron753.md",
    OUTPUT_DIR / "gre_taklee.md",
]
GRE_SPRINT_PATH = OUTPUT_DIR / "gre_qitao1787.md"

TOEFL_READING_TOKENS = CONTENT_DIR / "reading"
TOEFL_LISTENING_TOKENS = CONTENT_DIR / "listening"
IELTS_READING_TOKENS = CONTENT_DIR / "reading"
IELTS_LISTENING_TOKENS = CONTENT_DIR / "listening"

ACADEMIC_CORE_KEYWORDS = {
    "analysis", "analyze", "approach", "assess", "assumption", "concept",
    "context", "data", "define", "derive", "demonstrate", "evidence",
    "evaluate", "factor", "function", "hypothesis", "identify", "indicate",
    "interpret", "issue", "method", "model", "policy", "principle",
    "process", "research", "response", "role", "section", "significant",
    "source", "specific", "structure", "system", "theory", "variable", "vary",
}

TOEFL_SELECTED_PREFERRED = {
    "analyze", "approach", "assess", "assume", "concept", "context", "data",
    "define", "derive", "evidence", "factor", "function", "identify", "indicate",
    "interpret", "issue", "method", "policy", "principle", "process", "research",
    "role", "significant", "source", "specific", "structure", "theory", "vary",
}

TOEFL_LISTENING_KEYWORDS = {
    "available", "benefit", "cause", "effect", "environment", "factor", "function",
    "involve", "major", "occur", "period", "process", "require", "respond",
    "role", "section", "similar", "source", "system",
}

TOEFL_READING_KEYWORDS = {
    "analysis", "approach", "concept", "context", "data", "define", "derive",
    "evidence", "factor", "identify", "indicate", "interpret", "method",
    "policy", "principle", "process", "research", "significant", "source",
    "specific", "structure", "theory", "vary",
}

TOEFL_WRITING_KEYWORDS = {
    "assess", "assume", "benefit", "coherent", "consequence", "consider",
    "context", "contrast", "demonstrate", "ensure", "evaluate", "evident",
    "issue", "policy", "principle", "significant", "specific",
}

IELTS_SELECTED_PREFERRED = {
    "adequate", "allocate", "alter", "anticipate", "appropriate", "aspect",
    "attribute", "coherent", "complex", "consequence", "considerable",
    "contrast", "contribute", "crucial", "demonstrate", "distinct", "diverse",
    "emerge", "emphasize", "ensure", "evaluate", "evident", "facilitate",
}

IELTS_LISTENING_KEYWORDS = {
    "accommodate", "adjacent", "allocate", "appropriate", "approximately",
    "commence", "complex", "comprise", "concentrate", "ensure", "feature",
    "include", "maintain", "provide", "schedule", "service", "support",
}

IELTS_READING_KEYWORDS = {
    "adequate", "ambiguous", "apparent", "aspect", "attribute", "coherent",
    "coincide", "consequence", "considerable", "constitute", "contrast",
    "controversy", "conventional", "crucial", "decline", "demonstrate",
    "distinct", "diverse", "dominate", "emerge", "evaluate", "evident",
    "facilitate",
}

IELTS_TASK1_KEYWORDS = {
    "approximately", "contrast", "decline", "demonstrate", "diminish", "exceed",
    "increase", "proportion", "rate", "remain", "significant", "trend", "vary",
}

IELTS_TASK2_KEYWORDS = {
    "advocate", "allocate", "appropriate", "aspect", "coherent", "consequence",
    "considerable", "contrast", "contribute", "controversy", "crucial",
    "despite", "distinct", "diverse", "dominate", "emphasize", "ensure",
    "evaluate", "facilitate",
}

GENERAL_PRODUCTIVE_KEYWORDS = {
    "approach", "consider", "concern", "conduct", "concept", "context",
    "evident", "establish", "feature", "issue", "obtain", "policy",
    "practice", "project", "respond", "significant", "support",
}

CET_WRITING_KEYWORDS = {
    "appropriate", "benefit", "consider", "develop", "environment", "important",
    "improve", "issue", "method", "opportunity", "policy", "practice",
    "process", "significant", "support",
}

MANUAL_ZH = {
    "accord": "一致；符合",
    "adequate": "足够的；适当的",
    "allocate": "分配；拨给",
    "apparent": "明显的；表面上的",
    "approach": "方法；途径",
    "aspect": "方面；层面",
    "assess": "评估；评价",
    "assume": "假设；认为",
    "attribute": "把…归因于；属性",
    "coherent": "连贯的；一致的",
    "commit": "投入；承诺；犯下",
    "concept": "概念；观念",
    "concern": "关切；涉及",
    "conduct": "实施；进行；行为",
    "consider": "考虑；认为",
    "considerable": "相当大的；可观的",
    "constant": "持续的；恒定的",
    "context": "背景；语境",
    "contrite": "懊悔的；悔罪的",
    "contrast": "对比；反差",
    "conundrum": "难题；谜题",
    "contrive": "设法做到；策划",
    "converge": "汇聚；趋同",
    "contribute": "贡献；促成",
    "craven": "怯懦的；畏缩的",
    "crucial": "关键的；至关重要的",
    "circumstances": "情况；环境",
    "data": "数据；资料",
    "decorum": "礼仪；得体",
    "deference": "尊重；顺从",
    "delineate": "勾勒；描述清楚",
    "denigrate": "诋毁；贬低",
    "deride": "嘲弄；讥笑",
    "desiccate": "使干涸；使枯燥",
    "desultory": "杂乱无章的；散漫的",
    "deterrent": "威慑物；遏制因素",
    "diatribe": "抨击；怒斥",
    "dichotomy": "二分法；对立面",
    "diffidence": "缺乏自信；羞怯",
    "demonstrate": "证明；展示",
    "distinct": "明显不同的；清楚的",
    "embellish": "润饰；修饰",
    "elicit": "引出；诱出",
    "emulate": "效仿；赶超",
    "empirical": "经验主义的；以观察为依据的",
    "endemic": "地方性的；特有的",
    "engender": "引起；产生",
    "enhance": "增强；提升",
    "enervate": "使衰弱；使无力",
    "ephemeral": "短暂的；朝生暮死的",
    "equanimity": "镇定；平和",
    "equivocate": "含糊其辞；模棱两可",
    "erudite": "博学的",
    "esoteric": "深奥的；只有内行懂的",
    "eulogy": "颂词；悼词",
    "euphemism": "委婉语",
    "exacerbate": "恶化；加剧",
    "exculpate": "开脱；证明无罪",
    "evident": "明显的；清楚的",
    "establish": "建立；确立",
    "evaluate": "评估；评价",
    "effrontery": "厚颜无耻；放肆",
    "feature": "特征；特点",
    "forestall": "预先阻止；抢先一步",
    "frugality": "节俭；俭省",
    "futile": "徒劳的；无效的",
    "identify": "识别；确定",
    "impair": "损害；削弱",
    "impassive": "冷漠的；无表情的",
    "impede": "阻碍；妨碍",
    "impermeable": "不能渗透的；不透水的",
    "imperturbable": "沉着冷静的",
    "impervious": "不受影响的；不可渗透的",
    "implacable": "无法安抚的；不肯罢休的",
    "inadvertently": "无意中；不经意地",
    "inchoate": "初具雏形的；未完全形成的",
    "incongruity": "不协调；不一致",
    "inconsequential": "不重要的；无足轻重的",
    "indeterminate": "不确定的",
    "indigence": "贫困；贫穷",
    "indolent": "懒惰的；不活跃的",
    "inert": "惰性的；迟钝的",
    "irresolute": "犹豫不决的",
    "instance": "例子；实例",
    "intend": "打算；意图",
    "itinerary": "行程；路线",
    "issue": "问题；议题",
    "laconic": "言简意赅的；简短的",
    "lassitude": "倦怠；无精打采",
    "method": "方法；方式",
    "mendacious": "说谎的；虚假的",
    "metamorphosis": "变形；蜕变",
    "meticulous": "一丝不苟的；极其细致的",
    "misanthrope": "厌世者；愤世嫉俗的人",
    "mitigate": "减轻；缓和",
    "mollify": "安抚；缓和",
    "morose": "郁郁寡欢的；阴沉的",
    "mundane": "平凡的；世俗的",
    "negate": "否定；抵消",
    "neophyte": "新手；新信徒",
    "obdurate": "顽固的；冷酷无情的",
    "obsequious": "谄媚的；逢迎的",
    "obviate": "消除；排除",
    "occlude": "阻塞；遮断",
    "officious": "好管闲事的；过分殷勤的",
    "onerous": "繁重的；棘手的",
    "opprobrium": "耻辱；辱骂",
    "oscillate": "摆动；摇摆",
    "ostentatious": "炫耀的；卖弄的",
    "placate": "安抚；平息",
    "plasticity": "可塑性；适应性",
    "platitude": "陈词滥调",
    "plethora": "过多；过剩",
    "plummet": "暴跌；垂直落下",
    "porous": "多孔的；有漏洞的",
    "pragmatic": "务实的；实用主义的",
    "preamble": "前言；序言",
    "precarious": "不稳固的；危险的",
    "precipitate": "促成；使仓促发生",
    "precursor": "先驱；前兆",
    "presumptuous": "专横的；放肆的",
    "prevaricate": "支吾其词；说谎",
    "pristine": "原始纯净的；崭新的",
    "probity": "正直；廉洁",
    "problematic": "有问题的；难处理的",
    "propitiate": "安抚；讨好",
    "propriety": "得体；礼节",
    "proscribe": "禁止；谴责",
    "pungent": "辛辣的；尖锐的",
    "qualified": "有资格的；有限制的",
    "quibble": "吹毛求疵；诡辩",
    "quiescent": "静止的；沉寂的",
    "rarefied": "高雅的；稀薄的",
    "recalcitrant": "桀骜不驯的；顽抗的",
    "recant": "撤回声明；公开放弃",
    "recluse": "隐士；隐居者",
    "recondite": "深奥难懂的",
    "refractory": "难管教的；顽固的",
    "rescind": "废除；撤销",
    "resolve": "解决；下定决心",
    "reticent": "沉默寡言的；有保留的",
    "reverent": "恭敬的；虔诚的",
    "sage": "智者；贤人",
    "salubrious": "有益健康的",
    "sanction": "批准；制裁",
    "satiate": "使充分满足；使厌腻",
    "saturate": "浸透；使饱和",
    "sporadic": "零星的；偶发的",
    "stigma": "污名；耻辱",
    "stint": "节省；限制",
    "stipulate": "明确规定；约定",
    "stolid": "冷漠的；迟钝的",
    "subpoena": "传票；传唤令",
    "subside": "平息；减弱",
    "substantiate": "证实；使具体化",
    "supersede": "取代；代替",
    "tractable": "易处理的；温顺的",
    "transgression": "违反；越轨行为",
    "truculence": "凶狠；好斗",
    "vacillate": "摇摆不定；犹豫",
    "venerate": "尊敬；崇敬",
    "veracious": "诚实的；真实的",
    "verbose": "冗长的；啰嗦的",
    "viable": "可行的；能存活的",
    "viscous": "黏稠的",
    "vituperative": "辱骂的；恶言相向的",
    "volatile": "易变的；易挥发的",
    "minute": "极小的；细微的",
    "obtain": "获得；取得",
    "passage": "段落；文章片段",
    "policy": "政策；方针",
    "practice": "实践；惯例",
    "process": "过程；流程",
    "project": "项目；计划",
    "property": "属性；性质",
    "research": "研究；调查",
    "response": "回应；反应",
    "role": "角色；作用",
    "scarce": "稀缺的；不足的",
    "significant": "显著的；重要的",
    "source": "来源；源头",
    "specific": "具体的；特定的",
    "structure": "结构；构造",
    "theory": "理论；学说",
    "vary": "变化；不同",
    "allocate": "分配；拨给",
    "appropriate": "合适的；恰当的",
    "attribute": "把…归因于；属性",
    "coherent": "连贯的；一致的",
    "contrast": "对比；对照",
    "contribute": "促成；贡献",
    "crucial": "关键的；至关重要的",
    "distinct": "明显不同的；清晰的",
    "adequate": "足够的；适当的",
    "considerable": "相当大的；可观的",
    "hypothesis": "假设",
    "theory": "理论",
    "interpret": "解释；诠释",
    "derive": "推导；获得",
    "factor": "因素",
    "function": "功能；作用",
    "environment": "环境",
    "benefit": "益处；好处",
    "major": "主要的；重大的",
    "period": "时期；阶段",
    "similar": "相似的",
    "available": "可获得的；可用的",
}


def load_rows(path: Path, source_name: str) -> list[dict[str, str]]:
    _, rows = parse_vocab_markdown(md_file=path)
    loaded = []
    for index, row in enumerate(rows):
        item = {header: str(row.get(header, "")).strip() for header in VOCAB_HEADERS}
        if not item["word"] or not item["definition_en"]:
            continue
        item["__source_name"] = source_name
        item["__order"] = index
        item["__text"] = " ".join(
            [
                item["word"],
                item["definition_en"],
                item["definition_zh"],
                item["example"],
                item["part_of_speech"],
                item["synonyms"],
                item["antonyms"],
            ]
        ).lower()
        loaded.append(item)
    return loaded


def merge_rows(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    merged = dict(existing)
    for header in VOCAB_HEADERS:
        current_value = merged.get(header, "")
        incoming_value = incoming.get(header, "")
        if not current_value and incoming_value:
            merged[header] = incoming_value
    return merged


def apply_manual_zh(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    enriched = []
    for row in rows:
        item = dict(row)
        word = item["word"].strip().lower()
        if word and not item.get("definition_zh"):
            item["definition_zh"] = MANUAL_ZH.get(word, "")
        enriched.append(item)
    return enriched


def infer_part_of_speech(word: str, definition: str) -> str:
    text = (definition or "").strip().lower()
    lower_word = (word or "").strip().lower()
    if not text:
        return ""
    if lower_word.endswith("ly"):
        return "adverb"
    noun_starts = (
        "a ", "an ", "the ", "someone ", "someone who", "something ", "something that",
        "one who", "the trait", "the quality", "the state", "state of", "lack of",
        "absence of", "the act", "the use", "the property", "model of", "a person",
    )
    verb_starts = (
        "be ", "become ", "make ", "cause ", "give ", "assist ", "move ", "walk ",
        "run ", "find ", "grant ", "close ", "grow ", "evade ", "regard ",
        "cancel ", "take ", "keep ", "pay ", "lessen ", "increase ", "bring ",
        "seize ", "rub ", "command ", "stress ", "describe ", "fill ", "promote ",
        "leave ", "yield ", "pronounce ", "formally ", "call ", "burst ",
    )
    adjective_starts = (
        "of or relating to", "marked by", "having ", "characterized by", "full of",
        "liable to", "capable of", "understandable only", "brief and", "not ",
        "being ", "promoting ", "prone to", "easy to", "difficult to", "extremely ",
        "very ", "related to", "showing ", "given to", "incapable of",
    )
    if text.startswith(noun_starts):
        return "noun"
    if text.startswith(verb_starts):
        return "verb"
    if text.startswith(adjective_starts):
        return "adjective"
    if lower_word.endswith(("tion", "sion", "ity", "ness", "ment", "ance", "ence", "ism", "ship")):
        return "noun"
    if lower_word.endswith(("ous", "ive", "able", "ible", "al", "ic", "id", "ate", "ile")):
        return "adjective"
    return ""


def apply_inferred_pos(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    enriched = []
    for row in rows:
        item = dict(row)
        if not item.get("part_of_speech"):
            item["part_of_speech"] = infer_part_of_speech(item.get("word", ""), item.get("definition_en", ""))
        enriched.append(item)
    return enriched


def normalize_part_of_speech_label(value: str) -> str:
    text = (value or "").strip().lower()
    mapping = {
        "adj": "adjective",
        "adjective": "adjective",
        "adv": "adverb",
        "adverb": "adverb",
        "noun": "noun",
        "n": "noun",
        "verb": "verb",
        "v": "verb",
        "verb/adj": "verb/adjective",
    }
    return mapping.get(text, text)


def is_abstract_noun(word: str, definition: str) -> bool:
    lower_word = (word or "").strip().lower()
    text = (definition or "").strip().lower()
    if not text:
        return False
    abstract_suffixes = ("ity", "ness", "tion", "sion", "ance", "ence", "ism", "ship", "tude", "dom", "ment")
    concrete_hints = ("person", "people", "place", "road", "piece", "writ", "substance", "mixture", "citadel", "line of travel")
    if any(hint in text for hint in concrete_hints):
        return False
    if lower_word.endswith(abstract_suffixes):
        return True
    abstract_hints = (
        "state", "quality", "trait", "feeling", "lack of", "absence of", "process",
        "condition", "behavior", "approval", "respect", "poverty", "dishonor",
        "aggressiveness", "integrity", "problem", "remark", "decision", "idea",
    )
    return any(hint in text for hint in abstract_hints)


def generate_example_sentence(word: str, pos: str, definition: str) -> str:
    normalized = normalize_part_of_speech_label(pos)
    lower_word = (word or "").strip()
    if normalized == "adjective":
        templates = [
            "The committee described the proposal as {word} after reviewing the evidence.",
            "Several historians considered the explanation {word} rather than convincing.",
            "The reviewer called the author's tone {word} throughout the essay.",
        ]
        return templates[hash(lower_word) % len(templates)].format(word=lower_word)
    if normalized == "adverb":
        templates = [
            "The minister responded {word} when asked to explain the discrepancy.",
            "She spoke {word} during the interview despite the hostile questions.",
        ]
        return templates[hash(lower_word) % len(templates)].format(word=lower_word)
    if normalized == "verb":
        templates = [
            "The committee refused to {word} the flawed recommendation without further evidence.",
            "Researchers may {word} earlier assumptions when new data emerges.",
            "A skilled negotiator can {word} tension before the dispute escalates.",
        ]
        return templates[hash(lower_word) % len(templates)].format(word=lower_word)
    if normalized == "noun" and is_abstract_noun(lower_word, definition):
        templates = [
            "The dispute soon became an example of {word} rather than cooperation.",
            "The report presented the episode as a clear case of {word}.",
            "The hearing descended into {word} after both sides rejected compromise.",
        ]
        return templates[hash(lower_word) % len(templates)].format(word=lower_word)
    return ""


def generate_context_sentence(word: str, pos: str, definition: str) -> str:
    normalized = normalize_part_of_speech_label(pos)
    lower_word = (word or "").strip()
    if normalized == "adjective":
        return f"In graduate seminars, a {lower_word} claim often weakens the credibility of an otherwise promising argument."
    if normalized == "adverb":
        return f"Even when challenged by conflicting evidence, the spokesperson answered {lower_word}, which shaped how the audience judged her reliability."
    if normalized == "verb":
        return f"In critical reading passages, authors often {lower_word} earlier theories to show how a debate shifts when new evidence appears."
    if normalized == "noun" and is_abstract_noun(lower_word, definition):
        return f"In academic writing, a single moment of {lower_word} can reshape how readers interpret the author's motive and evidence."
    return ""


def generate_collocations(word: str, pos: str, definition: str) -> str:
    normalized = normalize_part_of_speech_label(pos)
    lower_word = (word or "").strip()
    if normalized == "adjective":
        return f"{lower_word} claim; {lower_word} tone; {lower_word} response"
    if normalized == "adverb":
        return f"respond {lower_word}; speak {lower_word}; act {lower_word}"
    if normalized == "verb":
        return f"{lower_word} a claim; {lower_word} an argument; {lower_word} the evidence"
    if normalized == "noun" and is_abstract_noun(lower_word, definition):
        return f"a sense of {lower_word}; show {lower_word}; marked by {lower_word}"
    if normalized == "noun":
        return f"study {lower_word}; define {lower_word}; analyze {lower_word}"
    return ""


def apply_generated_usage(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    enriched = []
    for row in rows:
        item = dict(row)
        pos = item.get("part_of_speech", "")
        definition = item.get("definition_en", "")
        if not item.get("example"):
            item["example"] = generate_example_sentence(item.get("word", ""), pos, definition)
        if not item.get("context_sentence"):
            if item.get("example"):
                generated = generate_context_sentence(item.get("word", ""), pos, definition)
                item["context_sentence"] = generated or item["example"]
        if not item.get("collocations"):
            item["collocations"] = generate_collocations(item.get("word", ""), pos, definition)
        enriched.append(item)
    return enriched


def enrich_from_preferred(rows: list[dict[str, str]], preferred_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    index = {row["word"].strip().lower(): row for row in preferred_rows if row.get("word")}
    enriched = []
    for row in rows:
        preferred = index.get(row["word"].strip().lower())
        enriched.append(merge_rows(preferred, row) if preferred else row)
    return enriched


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for row in rows:
        word = row["word"].strip().lower()
        if not word:
            continue
        if word not in seen:
            seen[word] = dict(row)
            order.append(word)
        else:
            seen[word] = merge_rows(seen[word], row)
    return [seen[word] for word in order]


def collect_tokens(pattern: str, directory: Path) -> set[str]:
    tokens: set[str] = set()
    for path in sorted(directory.glob(pattern)):
        text = path.read_text(encoding="utf-8")
        tokens.update(re.findall(r"[A-Za-z][A-Za-z'-]+", text.lower()))
    return tokens


def rank_rows(
    rows: list[dict[str, str]],
    *,
    keywords: set[str] | None = None,
    passage_tokens: set[str] | None = None,
    preferred_words: set[str] | None = None,
    source_bonus: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    keywords = keywords or set()
    passage_tokens = passage_tokens or set()
    preferred_words = preferred_words or set()
    source_bonus = source_bonus or {}

    ranked = []
    for index, row in enumerate(rows):
        word = row["word"].lower()
        text = row["__text"]
        score = source_bonus.get(row["__source_name"], 0)
        if word in preferred_words:
            score += 40
        if word in passage_tokens:
            score += 18
        for keyword in keywords:
            if keyword == word:
                score += 10
            elif keyword in text:
                score += 3
        if row.get("example"):
            score += 2
        if row.get("definition_zh"):
            score += 8
        if row.get("part_of_speech"):
            score += 6
        if row.get("synonyms"):
            score += 4
        ranked.append((score, index, row))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2]["word"]))
    return [row for _, _, row in ranked]


def select_rows(
    rows: list[dict[str, str]],
    limit: int,
    *,
    keywords: set[str] | None = None,
    passage_tokens: set[str] | None = None,
    preferred_words: set[str] | None = None,
    source_bonus: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    chosen: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rank_rows(
        rows,
        keywords=keywords,
        passage_tokens=passage_tokens,
        preferred_words=preferred_words,
        source_bonus=source_bonus,
    ):
        word = row["word"].lower()
        if word in seen:
            continue
        seen.add(word)
        chosen.append(row)
        if len(chosen) >= limit:
            return chosen
    return chosen


def append_support(primary: list[dict[str, str]], support: list[dict[str, str]], support_limit: int) -> list[dict[str, str]]:
    primary_words = {row["word"].lower() for row in primary}
    support_rows = [row for row in support if row["word"].lower() not in primary_words]
    return dedupe_rows(primary + support_rows[:support_limit])


def extend_to_target(
    primary: list[dict[str, str]],
    target_count: int,
    *support_groups: list[dict[str, str]],
) -> list[dict[str, str]]:
    result = dedupe_rows(primary)
    seen = {row["word"].lower() for row in result}
    if len(result) >= target_count:
        return result[:target_count]
    for support in support_groups:
        for row in support:
            word = row["word"].lower()
            if word in seen:
                continue
            result.append(row)
            seen.add(word)
            if len(result) >= target_count:
                return result
    return result


def write_markdown(path: Path, metadata: dict[str, object], rows: list[dict[str, str]]) -> None:
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    header = "|".join(VOCAB_HEADERS)
    lines.append(header)
    for row in rows:
        values = []
        for header_name in VOCAB_HEADERS:
            values.append(str(row.get(header_name, "")).replace("\n", " ").strip())
        lines.append("|".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    general_rows = apply_generated_usage(apply_inferred_pos(apply_manual_zh(load_rows(GENERAL_PATH, "general"))))
    toefl_rows = apply_generated_usage(apply_inferred_pos(apply_manual_zh(dedupe_rows(load_rows(TOEFL_BASE_PATH, "toefl_base") + load_rows(TOEFL_PATH, "toefl") + load_rows(TOEFL_STEM_PATH, "toefl")))))
    ielts_rows = apply_generated_usage(apply_inferred_pos(apply_manual_zh(dedupe_rows(load_rows(IELTS_BASE_PATH, "ielts_base") + load_rows(IELTS_PATH, "ielts")))))
    cet_rows = apply_generated_usage(apply_inferred_pos(dedupe_rows([row for path in CET_PATHS for row in load_rows(path, "cet")])))
    gre_selected_rows = apply_generated_usage(apply_inferred_pos(apply_manual_zh(dedupe_rows(load_rows(GRE_BASE_PATH, "gre_base") + [row for path in GRE_SELECTED_PATHS for row in load_rows(path, "gre_selected")]))))
    gre_sprint_raw_rows = apply_generated_usage(apply_inferred_pos(apply_manual_zh(load_rows(GRE_SPRINT_PATH, "gre_sprint"))))
    gre_sprint_rows = enrich_from_preferred(gre_sprint_raw_rows, gre_selected_rows)
    shared_academic_rows = dedupe_rows(toefl_rows + ielts_rows)
    general_enriched_rows = apply_generated_usage(apply_inferred_pos(apply_manual_zh(dedupe_rows(general_rows + shared_academic_rows + cet_rows + gre_selected_rows))))

    toefl_reading_tokens = collect_tokens("toefl_*.md", TOEFL_READING_TOKENS)
    toefl_listening_tokens = collect_tokens("toefl_*.md", TOEFL_LISTENING_TOKENS)
    ielts_reading_tokens = collect_tokens("ielts_*.md", IELTS_READING_TOKENS)
    ielts_listening_tokens = collect_tokens("ielts_*.md", IELTS_LISTENING_TOKENS)

    general_academic_support = select_rows(
        general_enriched_rows,
        380,
        keywords=ACADEMIC_CORE_KEYWORDS | TOEFL_READING_KEYWORDS | IELTS_READING_KEYWORDS,
        passage_tokens=toefl_reading_tokens | toefl_listening_tokens | ielts_reading_tokens | ielts_listening_tokens,
        source_bonus={"general": 3},
    )
    general_productive_rows = select_rows(
        general_enriched_rows,
        280,
        keywords=GENERAL_PRODUCTIVE_KEYWORDS | TOEFL_WRITING_KEYWORDS | IELTS_TASK2_KEYWORDS,
        preferred_words={"consider", "concern", "concept", "conduct", "context", "issue", "project", "support"},
        source_bonus={"general": 3},
    )

    books = {
        "general_core_foundation.md": {
            "metadata": {
                "exam": "general",
                "difficulty": "B1-B2",
                "source": "project_curated_professional",
                "topic": "general",
                "name": "通用核心基础词",
                "description": "面向商业云版的通用英语起步词书，覆盖高频基础词与常见抽象表达。",
                "book_group": "核心词",
                "recommended_order": 10,
                "icon": "🧭",
                "color": "#06b6d4",
                "series": "专业词书",
                "skill_focus": "综合",
                "stage": "起步",
                "source_label": "项目策展词书（General Vocabulary 1000 精选整理）",
            },
            "rows": select_rows(
                general_enriched_rows,
                520,
                keywords=GENERAL_PRODUCTIVE_KEYWORDS | ACADEMIC_CORE_KEYWORDS,
                preferred_words={"consider", "concern", "concept", "issue", "policy", "project", "research"},
                source_bonus={"general": 3},
            ),
        },
        "general_academic_bridge.md": {
            "metadata": {
                "exam": "general",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "通用学术桥接词",
                "description": "从 TOEFL / IELTS 学术词和通用高频词中抽出跨考试通用的学术桥接词。",
                "book_group": "学术桥接",
                "recommended_order": 20,
                "icon": "🎓",
                "color": "#0ea5e9",
                "series": "专业词书",
                "skill_focus": "学术",
                "stage": "进阶",
                "source_label": "项目策展词书（TOEFL / IELTS 学术词交叉整理）",
            },
            "rows": select_rows(
                dedupe_rows(shared_academic_rows + general_academic_support),
                220,
                keywords=ACADEMIC_CORE_KEYWORDS,
                preferred_words=TOEFL_SELECTED_PREFERRED | IELTS_SELECTED_PREFERRED,
                source_bonus={"toefl": 6, "toefl_base": 8, "ielts": 6, "ielts_base": 8, "general": 2},
            ),
        },
        "general_productive_plus.md": {
            "metadata": {
                "exam": "general",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "general",
                "name": "通用表达进阶词",
                "description": "偏向 speaking / writing 的主动表达词书，适合通用用户和转考用户提升输出能力。",
                "book_group": "口语词汇",
                "recommended_order": 30,
                "icon": "💬",
                "color": "#14b8a6",
                "series": "专业词书",
                "skill_focus": "口语",
                "stage": "进阶",
                "source_label": "项目策展词书（General 高频词主动表达向整理）",
            },
            "rows": general_productive_rows,
        },
        "toefl_selected_core.md": {
            "metadata": {
                "exam": "toefl",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "TOEFL 精选核心词",
                "description": "面向托福起步阶段，优先覆盖学术阅读、讲座和基础写作最常见的核心词。",
                "book_group": "精选词",
                "recommended_order": 110,
                "icon": "🎯",
                "color": "#2563eb",
                "series": "专业词书",
                "skill_focus": "综合",
                "stage": "起步",
                "source_label": "项目策展词书（TOEFL Academic 567 精选）",
            },
            "rows": select_rows(
                toefl_rows,
                180,
                keywords=ACADEMIC_CORE_KEYWORDS | TOEFL_READING_KEYWORDS | TOEFL_WRITING_KEYWORDS,
                preferred_words=TOEFL_SELECTED_PREFERRED,
                source_bonus={"toefl": 8, "toefl_base": 12},
            ),
        },
        "toefl_complete_curated.md": {
            "metadata": {
                "exam": "toefl",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "TOEFL 全面词书",
                "description": "托福综合词书，先保留现有学术词，再补入通用高频支撑词，适合完整备考路径。",
                "book_group": "全面词",
                "recommended_order": 120,
                "icon": "📘",
                "color": "#1d4ed8",
                "series": "专业词书",
                "skill_focus": "综合",
                "stage": "进阶",
                "source_label": "项目策展词书（TOEFL Academic + General 高频支撑）",
            },
            "rows": extend_to_target(
                toefl_rows,
                887,
                general_academic_support,
                general_enriched_rows,
                general_rows,
            ),
        },
        "toefl_reading_focus.md": {
            "metadata": {
                "exam": "toefl",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "TOEFL 阅读常考词",
                "description": "优先贴合当前 TOEFL 阅读素材中的学术高频词、逻辑词与研究语境词。",
                "book_group": "阅读高频",
                "recommended_order": 130,
                "icon": "📖",
                "color": "#3b82f6",
                "series": "专业词书",
                "skill_focus": "阅读",
                "stage": "强化",
                "source_label": "项目策展词书（结合内置 TOEFL Reading 语料）",
            },
            "rows": select_rows(
                dedupe_rows(toefl_rows + general_academic_support),
                240,
                keywords=ACADEMIC_CORE_KEYWORDS | TOEFL_READING_KEYWORDS,
                passage_tokens=toefl_reading_tokens,
                preferred_words=TOEFL_SELECTED_PREFERRED,
                source_bonus={"toefl": 8, "toefl_base": 12, "general": 3},
            ),
        },
        "toefl_listening_focus.md": {
            "metadata": {
                "exam": "toefl",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "TOEFL 听力常考词",
                "description": "围绕讲座、校园对话和说明性表达整理的托福听力常考词书。",
                "book_group": "听力高频",
                "recommended_order": 140,
                "icon": "🎧",
                "color": "#60a5fa",
                "series": "专业词书",
                "skill_focus": "听力",
                "stage": "强化",
                "source_label": "项目策展词书（结合内置 TOEFL Listening 语料）",
            },
            "rows": select_rows(
                dedupe_rows(toefl_rows + general_academic_support),
                220,
                keywords=TOEFL_LISTENING_KEYWORDS | ACADEMIC_CORE_KEYWORDS,
                passage_tokens=toefl_listening_tokens,
                preferred_words={"available", "benefit", "environment", "factor", "function", "process", "respond", "role"},
                source_bonus={"toefl": 8, "toefl_base": 12, "general": 3},
            ),
        },
        "toefl_writing_focus.md": {
            "metadata": {
                "exam": "toefl",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "TOEFL 写作词汇",
                "description": "偏向独立写作和学术讨论输出的托福写作词书，覆盖论证、让步、比较和结论表达。",
                "book_group": "写作词汇",
                "recommended_order": 150,
                "icon": "✍️",
                "color": "#2563eb",
                "series": "专业词书",
                "skill_focus": "写作",
                "stage": "强化",
                "source_label": "项目策展词书（TOEFL Academic + 高价值输出词）",
            },
            "rows": select_rows(
                dedupe_rows(toefl_rows + general_productive_rows + general_academic_support),
                220,
                keywords=TOEFL_WRITING_KEYWORDS | ACADEMIC_CORE_KEYWORDS,
                preferred_words={"assess", "assume", "benefit", "concept", "context", "demonstrate", "evaluate", "issue", "policy", "significant"},
                source_bonus={"toefl": 8, "toefl_base": 12, "general": 3},
            ),
        },
        "ielts_selected_core.md": {
            "metadata": {
                "exam": "ielts",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "IELTS 精选核心词",
                "description": "面向雅思起步和提分阶段，优先覆盖阅读与写作最常见的学术核心词。",
                "book_group": "精选词",
                "recommended_order": 210,
                "icon": "🎯",
                "color": "#10b981",
                "series": "专业词书",
                "skill_focus": "综合",
                "stage": "起步",
                "source_label": "项目策展词书（IELTS Academic 240 精选）",
            },
            "rows": select_rows(
                ielts_rows,
                140,
                keywords=IELTS_READING_KEYWORDS | IELTS_TASK2_KEYWORDS,
                preferred_words=IELTS_SELECTED_PREFERRED,
                source_bonus={"ielts": 8, "ielts_base": 12},
            ),
        },
        "ielts_complete_curated.md": {
            "metadata": {
                "exam": "ielts",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "IELTS 全面词书",
                "description": "雅思综合词书，覆盖现有学术词并补入通用高频支撑词，适合长期完整备考。",
                "book_group": "全面词",
                "recommended_order": 220,
                "icon": "📗",
                "color": "#059669",
                "series": "专业词书",
                "skill_focus": "综合",
                "stage": "进阶",
                "source_label": "项目策展词书（IELTS Academic + General 高频支撑）",
            },
            "rows": extend_to_target(
                ielts_rows,
                594,
                general_academic_support,
                general_enriched_rows,
                general_rows,
            ),
        },
        "ielts_listening_focus.md": {
            "metadata": {
                "exam": "ielts",
                "difficulty": "B1-B2",
                "source": "project_curated_professional",
                "topic": "general",
                "name": "IELTS 听力场景词",
                "description": "围绕报名、预约、校园、社区和服务场景整理的雅思听力高频词书。",
                "book_group": "听力高频",
                "recommended_order": 230,
                "icon": "🎧",
                "color": "#34d399",
                "series": "专业词书",
                "skill_focus": "听力",
                "stage": "强化",
                "source_label": "项目策展词书（结合内置 IELTS Listening 语料）",
            },
            "rows": select_rows(
                dedupe_rows(ielts_rows + general_enriched_rows),
                220,
                keywords=IELTS_LISTENING_KEYWORDS,
                passage_tokens=ielts_listening_tokens,
                preferred_words={"accommodate", "adjacent", "allocate", "appropriate", "approximately", "commence", "ensure"},
                source_bonus={"ielts": 7, "ielts_base": 12, "general": 4},
            ),
        },
        "ielts_reading_focus.md": {
            "metadata": {
                "exam": "ielts",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "IELTS 阅读常考词",
                "description": "偏向雅思阅读中高频出现的学术、逻辑与信息匹配类词汇。",
                "book_group": "阅读高频",
                "recommended_order": 240,
                "icon": "📖",
                "color": "#10b981",
                "series": "专业词书",
                "skill_focus": "阅读",
                "stage": "强化",
                "source_label": "项目策展词书（结合内置 IELTS Reading 语料）",
            },
            "rows": select_rows(
                dedupe_rows(ielts_rows + general_academic_support),
                220,
                keywords=IELTS_READING_KEYWORDS | ACADEMIC_CORE_KEYWORDS,
                passage_tokens=ielts_reading_tokens,
                preferred_words=IELTS_SELECTED_PREFERRED,
                source_bonus={"ielts": 8, "ielts_base": 12, "general": 3},
            ),
        },
        "ielts_writing_task1.md": {
            "metadata": {
                "exam": "ielts",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "IELTS 写作 Task 1 词汇",
                "description": "服务于图表、流程图和数据概述表达的雅思写作 Task 1 词书。",
                "book_group": "写作词汇",
                "recommended_order": 250,
                "icon": "📊",
                "color": "#22c55e",
                "series": "专业词书",
                "skill_focus": "写作",
                "stage": "强化",
                "source_label": "项目策展词书（IELTS Task 1 报告表达向整理）",
            },
            "rows": select_rows(
                dedupe_rows(ielts_rows + general_enriched_rows),
                150,
                keywords=IELTS_TASK1_KEYWORDS,
                preferred_words={"approximately", "contrast", "decline", "demonstrate", "diminish", "exceed"},
                source_bonus={"ielts": 8, "ielts_base": 12, "general": 4},
            ),
        },
        "ielts_writing_task2.md": {
            "metadata": {
                "exam": "ielts",
                "difficulty": "B2-C1",
                "source": "project_curated_professional",
                "topic": "academic",
                "name": "IELTS 写作 Task 2 词汇",
                "description": "覆盖观点讨论、原因结果、让步反驳和解决方案表达的雅思写作 Task 2 词书。",
                "book_group": "写作词汇",
                "recommended_order": 260,
                "icon": "📝",
                "color": "#16a34a",
                "series": "专业词书",
                "skill_focus": "写作",
                "stage": "强化",
                "source_label": "项目策展词书（IELTS Task 2 输出表达向整理）",
            },
            "rows": select_rows(
                dedupe_rows(ielts_rows + general_productive_rows + general_academic_support),
                180,
                keywords=IELTS_TASK2_KEYWORDS | ACADEMIC_CORE_KEYWORDS,
                preferred_words=IELTS_SELECTED_PREFERRED,
                source_bonus={"ielts": 8, "ielts_base": 12, "general": 3},
            ),
        },
        "cet_bridge_core.md": {
            "metadata": {
                "exam": "cet",
                "difficulty": "B1-B2",
                "source": "project_curated_professional",
                "topic": "general",
                "name": "CET 桥接核心词",
                "description": "整合现有 CET 词源，再补入通用高频支撑词，适合作为四级到六级的桥接词书。",
                "book_group": "核心词",
                "recommended_order": 310,
                "icon": "📚",
                "color": "#f59e0b",
                "series": "专业词书",
                "skill_focus": "综合",
                "stage": "起步",
                "source_label": "项目策展词书（CET 现有词源 + General 高频支撑）",
            },
            "rows": extend_to_target(
                cet_rows,
                299,
                select_rows(general_enriched_rows, 220, keywords=GENERAL_PRODUCTIVE_KEYWORDS | CET_WRITING_KEYWORDS, source_bonus={"general": 3}),
                general_enriched_rows,
                general_rows,
            ),
        },
        "cet_writing_focus.md": {
            "metadata": {
                "exam": "cet",
                "difficulty": "B1-B2",
                "source": "project_curated_professional",
                "topic": "general",
                "name": "CET 写作高频词",
                "description": "面向 CET 作文与翻译输出，优先覆盖评价、建议、对比、影响和解决方案表达。",
                "book_group": "写作词汇",
                "recommended_order": 320,
                "icon": "✏️",
                "color": "#f97316",
                "series": "专业词书",
                "skill_focus": "写作",
                "stage": "强化",
                "source_label": "项目策展词书（CET 输出表达向整理）",
            },
            "rows": select_rows(
                dedupe_rows(cet_rows + general_enriched_rows),
                170,
                keywords=CET_WRITING_KEYWORDS,
                preferred_words={"appropriate", "benefit", "environment", "improve", "issue", "opportunity", "policy", "practice", "support"},
                source_bonus={"cet": 8, "general": 3},
            ),
        },
        "gre_selected_core.md": {
            "metadata": {
                "exam": "gre",
                "difficulty": "C1",
                "source": "project_curated_professional",
                "topic": "general",
                "name": "GRE 精选核心词",
                "description": "优先保留 Barron 高频核心词并补足常见变体，适合作为 GRE Verbal 起步词书。",
                "book_group": "精选词",
                "recommended_order": 410,
                "icon": "🎯",
                "color": "#7c3aed",
                "series": "专业词书",
                "skill_focus": "填空+阅读",
                "stage": "起步",
                "source_label": "项目策展词书（GRE 高频核心精选）",
            },
            "rows": select_rows(
                gre_selected_rows,
                420,
                preferred_words={row["word"].lower() for row in gre_selected_rows[:334]},
                source_bonus={"gre_selected": 8, "gre_base": 12},
            ),
        },
        "gre_highfreq_curated.md": {
            "metadata": {
                "exam": "gre",
                "difficulty": "C1",
                "source": "project_curated_professional",
                "topic": "general",
                "name": "GRE 高频词书",
                "description": "覆盖当前项目内可导入的 GRE 高频主词库，适合系统刷词与填空基础积累。",
                "book_group": "高频词",
                "recommended_order": 420,
                "icon": "🧠",
                "color": "#8b5cf6",
                "series": "专业词书",
                "skill_focus": "填空+阅读",
                "stage": "进阶",
                "source_label": "项目策展词书（GRE 高频主词库整理）",
            },
            "rows": gre_selected_rows,
        },
        "gre_sprint_advanced.md": {
            "metadata": {
                "exam": "gre",
                "difficulty": "C1",
                "source": "project_curated_professional",
                "topic": "general",
                "name": "GRE 冲刺扩展词",
                "description": "面向高分冲刺阶段的扩展词书，覆盖更大范围的低频和难词。",
                "book_group": "冲刺词",
                "recommended_order": 430,
                "icon": "🚀",
                "color": "#a855f7",
                "series": "专业词书",
                "skill_focus": "填空+阅读",
                "stage": "冲刺",
                "source_label": "项目策展词书（GRE 冲刺扩展词整理）",
            },
            "rows": gre_sprint_rows,
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, payload in books.items():
        rows = dedupe_rows(payload["rows"])
        write_markdown(OUTPUT_DIR / filename, payload["metadata"], rows)
        print(f"{filename}\t{len(rows)}")


if __name__ == "__main__":
    main()
