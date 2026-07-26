import re
from typing import List

BLOCKED_PATTERNS: List[str] = [
    r'\bfuck(?:ing|er|ed|s)?\b',
    r'\bshit(?:ty|s)?\b',
    r'\bass(?:hole|hat)?\b',
    r'\bbitch\b',
    r'\bdick\b',
    r'\bcock\b',
    r'\bcunt\b',
    r'\bpiss(?:ed|ing)?\b',
    r'\bdamn(?:ed|ing)?\b',
    r'\bbastard\b',
    r'\bcrap\b',
    r'\bslut\b',
    r'\bwhore\b',
    r'\bnigg[ae]r\b',
    r'\bspic\b',
    r'\bchink\b',
    r'\bkike\b',
    r'\bfag(?:got|s)?\b',
    r'\bretard(?:ed|s)?\b',
    r'\bkill\s+yours(?:elf|elves)\b',
    r'\bharm\s+yours(?:elf|elves)\b',
]

_compiled_regex = re.compile(
    '|'.join(BLOCKED_PATTERNS),
    re.IGNORECASE
)


def contains_prohibited_content(text: str) -> bool:
    if not text:
        return False
    return bool(_compiled_regex.search(text))


def get_filter_error_message() -> str:
    return "Your content contains prohibited language. Please revise and resubmit."
