"""Emotions of a Fish voice: the model starts a sentence with an intonation tag — «[твёрдо и холодно] Давайте
вернёмся к делу.» — and Fish (S2 models) speaks it that way. Fish doesn't read the tag aloud (checked with
SpeechKit on Russian and English tags); a tag works until the end of its sentence.

The agent's «спектр эмоций»: allowed tags (only they reach Fish — anything else in brackets is dropped) and
forbidden ones (told to the model as intonations it must never use). Tags never get into the transcript.
"""
import re

# suggestions for the agent form; checked on the voice «Рената»: «твёрдо и холодно», «angry», «сочувственно»
# change the delivery clearly, «раздражённо» hardly does, «шёпотом» gives a half-whisper
PRESETS = ["спокойно", "тепло", "радостно", "сочувственно", "удивлённо", "твёрдо и холодно", "angry", "шёпотом",
           "виновато", "воодушевлённо", "игриво", "устало", "раздражённо", "грустно", "испуганно"]

TAG = re.compile(r"\[\s*([^\[\]\n]{1,40}?)\s*\]\s*")


def parse(value) -> list[str]:
    """'тепло, радостно' or a list → ['тепло', 'радостно']."""
    items = value if isinstance(value, list) else str(value or "").split(",")
    out = []
    for t in items:
        t = re.sub(r"\s+", " ", str(t).strip().strip("[]").strip())
        if t and _key(t) not in {_key(x) for x in out}:
            out.append(t)
    return out


def _key(tag: str) -> str:
    return tag.strip().lower().replace("ё", "е")


def strip(text: str) -> str:
    """Text without intonation tags — what is saved to the transcript."""
    if "[" not in text:
        return text
    return re.sub(r"[ \t]{2,}", " ", TAG.sub("", text)).strip()


def for_fish(text: str, allowed: list[str]) -> str:
    """The sentence for Fish: allowed tags stay (as written in the agent), all other bracketed text goes."""
    if "[" not in text:
        return text
    keys = {_key(t): t for t in allowed}

    def keep(m):
        tag = keys.get(_key(m.group(1)))
        return f"[{tag}] " if tag else ""
    return TAG.sub(keep, text).strip()


def instructions(allowed: list[str], forbidden: list[str]) -> str:
    """Rules for the model's prompt ('' when the agent has no allowed emotions)."""
    if not allowed:
        return ("\n\nНе используй квадратные скобки и пометки интонации — синтезатор говорит ровным тоном."
                if forbidden else "")
    tags = ", ".join(f"[{t}]" for t in allowed)
    text = ("\n\nИнтонация голоса. Перед предложением, которое нужно сказать с особой интонацией, ставь тег в "
            f"квадратных скобках — только один из этих: {tags}. Это единственная разрешённая разметка, тег не "
            "произносится. Тег действует до конца предложения — если интонация нужна дольше, ставь его перед "
            "каждым таким предложением. Без тега — спокойный доброжелательный тон; не ставь теги без причины. "
            "Выбирай интонацию по тому, что и как говорит собеседник: благодарит — тепло, расстроен или "
            "жалуется — сочувственно, грубит — твёрдо и сдержанно, не переходя на оскорбления; подбирай из "
            "разрешённых самый близкий тег.")
    if forbidden:
        text += " Никогда не говори так: " + ", ".join(forbidden) + " — даже если собеседник провоцирует."
    return text
