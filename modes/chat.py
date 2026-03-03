"""
Free chat mode — conversational English practice with AI.
Corrects errors inline, adapts to CEFR level, tracks conversation history.
Zero cost when no API key (shows offline message).
"""

from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ai.client import AIClient
from core.user_model.profile import UserModel, UserProfile
from cli.display import print_header

console = Console()

_TOPIC_STARTERS = {
    "toefl": [
        "Let's talk about your university experience. What's the most challenging course you've taken?",
        "Tell me about a time you had to solve a difficult problem. What did you do?",
        "What do you think is the most important skill for a scientist or engineer to have?",
        "Describe your ideal research project. What would you study and why?",
        "How has technology changed the way students learn? Give specific examples.",
        "Do you prefer studying alone or in groups? What are the advantages of each?",
        "Describe a professor or teacher who had a significant impact on your academic development.",
        "What do you think universities should do to better prepare students for the workforce?",
        "If you could change one thing about your university's curriculum, what would it be and why?",
        "How do you think artificial intelligence will change higher education in the next decade?",
        "Describe a time when you had to work with people from different cultural backgrounds.",
        "What are the most important qualities of a good research paper?",
        "Do you think gap years between high school and university are beneficial? Why or why not?",
        "How do you manage stress during exam periods? What strategies work best for you?",
        "What is the relationship between academic success and real-world achievement?",
    ],
    "gre": [
        "Do you think standardized tests accurately measure academic ability? Why or why not?",
        "Some argue that specialization is more valuable than broad knowledge. What's your view?",
        "Describe a scientific discovery that you find particularly fascinating and explain its significance.",
        "Is it more important for a researcher to be creative or rigorous? Defend your position.",
        "How should universities balance teaching fundamental theory versus practical applications?",
        "Do you agree that the pursuit of knowledge is inherently valuable, regardless of practical application?",
        "What are the ethical responsibilities of scientists when their research has potential harmful applications?",
        "Is peer review an effective mechanism for ensuring scientific integrity? What are its limitations?",
        "Some philosophers argue that objective truth is unattainable. Do you agree?",
        "How does confirmation bias affect scientific research, and how can it be mitigated?",
        "Should governments prioritize funding basic research or applied research? Defend your view.",
        "Is it possible to be both a specialist and a generalist in today's academic environment?",
        "How has the replication crisis affected your confidence in published research?",
        "Do you think interdisciplinary research is more valuable than single-discipline research?",
        "What is the relationship between creativity and analytical thinking in academic work?",
    ],
    "ielts": [
        "What are the advantages and disadvantages of studying abroad?",
        "How is your hometown changing, and do you think these changes are positive?",
        "Do you think people today have a better work-life balance than previous generations?",
        "What role should governments play in funding scientific research?",
        "How has social media affected the way people communicate?",
        "Do you think it is better to live in a big city or a small town? Why?",
        "What are the main causes of environmental pollution in your country?",
        "How important is it for young people to learn a foreign language?",
        "Do you think the gap between rich and poor is increasing or decreasing? What are the causes?",
        "What are the advantages and disadvantages of remote working?",
        "How has the role of women in society changed over the past 50 years?",
        "Do you think tourism has more positive or negative effects on local communities?",
        "What can individuals do to reduce their carbon footprint?",
        "How important is it to preserve traditional cultures in a globalized world?",
        "Do you think governments should invest more in public transportation? Why?",
    ],
    "cet": [
        "请用英语描述你的大学生活。你最喜欢哪门课程？为什么？",
        "你认为大学生应该如何平衡学习和课外活动？",
        "谈谈你对网络学习的看法。它有哪些优缺点？",
        "你认为什么样的工作最适合你？请描述你的理想职业。",
        "中国传统文化在现代社会中扮演什么角色？",
        "你认为人工智能会对就业市场产生什么影响？",
        "谈谈你对环境保护的看法。个人能做些什么？",
        "你认为大学生应该在毕业后先工作还是继续深造？",
        "描述一次让你印象深刻的旅行经历。",
        "你认为社交媒体对年轻人的影响是积极的还是消极的？",
        "谈谈你对中国高铁发展的看法。它如何改变了人们的生活？",
        "你认为学习英语对中国学生最大的挑战是什么？",
        "描述一个你敬佩的人，并解释原因。",
        "你认为城市化对中国农村地区有什么影响？",
        "谈谈你对志愿服务的看法。你有过志愿服务的经历吗？",
    ],
    "general": [
        "Tell me about a book, paper, or article that changed how you think about something.",
        "What's a common misconception about your field of study?",
        "If you could have a conversation with any scientist in history, who would it be and why?",
        "Describe a complex concept from your field as if explaining it to a high school student.",
        "What's the most interesting thing you've learned recently?",
        "What hobby or activity do you enjoy outside of your studies? How did you get into it?",
        "If you could live in any country for a year, where would you choose and why?",
        "What do you think is the biggest challenge facing your generation?",
        "Describe a time when you changed your mind about something important.",
        "What skill would you most like to develop over the next year?",
        "If you could solve one global problem, what would it be and how would you approach it?",
        "What does success mean to you personally?",
        "Describe a cultural difference you've noticed between China and other countries.",
        "What technology do you think will have the biggest impact on society in the next 20 years?",
        "If you could go back in time and give your younger self one piece of advice, what would it be?",
    ],
}

# Exam-specific mode metadata for UI
EXAM_MODES = {
    "toefl": {
        "name": "Academic Discussion",
        "description": "Practice campus & academic topics. Aim for complex sentences and academic vocabulary.",
        "tips": ["Use specific examples", "Employ academic vocabulary", "Structure your response clearly"],
    },
    "ielts": {
        "name": "Speaking Practice",
        "description": "Simulates IELTS Speaking. Answer in full sentences, develop your ideas with examples.",
        "tips": ["Give extended answers", "Use a range of vocabulary", "Speak naturally and fluently"],
    },
    "gre": {
        "name": "Analytical Dialogue",
        "description": "Discuss abstract ideas and arguments. Use precise vocabulary and logical structure.",
        "tips": ["Use precise academic vocabulary", "Present logical arguments", "Acknowledge counterarguments"],
    },
    "cet": {
        "name": "Oral Practice",
        "description": "日常话题 + 学术话题，练习流利表达，注意中式英语纠错。",
        "tips": ["Avoid direct translation from Chinese", "Use natural English expressions", "Practice fluency"],
    },
    "general": {
        "name": "Free Conversation",
        "description": "Open-ended chat. Focus on fluency and natural expression.",
        "tips": ["Be yourself", "Ask follow-up questions", "Expand on your answers"],
    },
}


def run_chat_session(
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    exam: Optional[str] = None,
    topic: Optional[str] = None,
) -> dict:
    """
    Run a free conversation session.
    - AI responds at user's CEFR level
    - Gently corrects grammar errors inline
    - Type 'quit' or empty line twice to end
    """
    if not ai:
        console.print(Panel(
            "[yellow]No API key configured.[/yellow]\n"
            "Free chat requires Claude API access.\n"
            "Add your key to config.yaml → api_key",
            title="[yellow]AI Required[/yellow]",
            border_style="yellow",
        ))
        return {}

    exam = exam or profile.target_exam or "general"
    session_id = user_model.start_session(profile.user_id, "chat")
    start_time = time.time()

    print_header(
        "自由对话  ·  Free Conversation",
        subtitle=f"Exam: {exam.upper()} · CEFR {profile.cefr_level}",
    )

    console.print(Panel(
        f"[bold]Chat with your AI English coach.[/bold]\n\n"
        f"  • Responses are pitched at [cyan]CEFR {profile.cefr_level}[/cyan]\n"
        f"  • Grammar errors will be gently noted\n"
        f"  • Type [bold]quit[/bold] or press Enter twice to end\n"
        f"  • Type [bold]/topic[/bold] for a new conversation starter",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Pick opening topic
    import random
    starters = _TOPIC_STARTERS.get(exam, _TOPIC_STARTERS["general"])
    opening = topic or random.choice(starters)

    console.print(f"\n[bold cyan]Coach:[/bold cyan] {opening}\n")

    messages = [{"role": "assistant", "content": opening}]
    stats = {"turns": 0, "words_written": 0}
    blank_streak = 0

    while True:
        try:
            user_input = input(f"[{profile.name}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            blank_streak += 1
            if blank_streak >= 2:
                break
            continue
        blank_streak = 0

        if user_input.lower() in ("quit", "exit", "q", "bye"):
            break

        if user_input.lower() == "/topic":
            new_topic = random.choice(starters)
            console.print(f"\n[bold cyan]Coach:[/bold cyan] {new_topic}\n")
            messages = [{"role": "assistant", "content": new_topic}]
            continue

        if user_input.lower() == "/help":
            console.print(
                "[dim]Commands: quit · /topic (new topic) · /help[/dim]\n"
            )
            continue

        messages.append({"role": "user", "content": user_input})
        stats["words_written"] += len(user_input.split())

        with console.status("[dim]...[/dim]"):
            response = ai.chat(
                messages=messages,
                cefr_level=profile.cefr_level,
                correct_errors=True,
            )

        messages.append({"role": "assistant", "content": response})
        stats["turns"] += 1

        console.print(f"\n[bold cyan]Coach:[/bold cyan] {response}\n")

        # Keep context window manageable (last 10 turns)
        if len(messages) > 20:
            messages = messages[-20:]

    # Wrap up
    duration = int(time.time() - start_time)
    user_model.end_session(session_id, duration, stats["turns"], 1.0)
    user_model.update_profile(profile)

    console.print(
        f"\n[bold]Session complete![/bold]  "
        f"Turns: [cyan]{stats['turns']}[/cyan]  ·  "
        f"Words written: [cyan]{stats['words_written']}[/cyan]\n"
    )
    console.print(f"[dim]{ai.usage_summary()}[/dim]\n")

    return stats
