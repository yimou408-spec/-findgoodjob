import re


_INLINE_MARKDOWN_PATTERNS = (
    (re.compile(r"\*\*\*(.+?)\*\*\*", re.DOTALL), r"\1"),
    (re.compile(r"\*\*(.+?)\*\*", re.DOTALL), r"\1"),
    (re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", re.DOTALL), r"\1"),
    (re.compile(r"__(.+?)__", re.DOTALL), r"\1"),
    (re.compile(r"(?<!_)_(?!\s)(.+?)(?<!\s)_(?!_)", re.DOTALL), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
)

_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_STAR_BULLET_PATTERN = re.compile(r"(^|\n)([ \t]*)[*]+[ \t]+")
_PLUS_BULLET_PATTERN = re.compile(r"(^|\n)([ \t]*)\+[ \t]+")
_EXCESSIVE_BLANK_LINES_PATTERN = re.compile(r"\n{3,}")


def normalize_model_output(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    for pattern, replacement in _INLINE_MARKDOWN_PATTERNS:
        normalized = pattern.sub(replacement, normalized)

    normalized = _HEADING_PATTERN.sub("", normalized)
    normalized = _STAR_BULLET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}", normalized)
    normalized = _PLUS_BULLET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}", normalized)
    normalized = _EXCESSIVE_BLANK_LINES_PATTERN.sub("\n\n", normalized)
    return normalized.strip()


def normalize_streaming_content(text: str) -> str:
    return normalize_model_output(text)
