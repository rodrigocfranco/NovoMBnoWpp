"""Split long messages into WhatsApp-compatible chunks."""


def split_message(text: str, max_length: int = 4096) -> list[str]:
    """Split text into parts that fit within WhatsApp's character limit.

    Splits at natural break points in priority order:
    1. Paragraph break (``\\n\\n``)
    2. Line break (``\\n``)
    3. Sentence end (``. ``)
    4. Word boundary (`` ``)

    Args:
        text: The text to split.
        max_length: Maximum characters per part (default 4096).

    Returns:
        List of text parts, each within max_length.
    """
    if len(text) <= max_length:
        return [text]

    parts: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            parts.append(remaining)
            break

        chunk = remaining[:max_length]
        min_cut = max_length // 4

        # Try paragraph break
        cut = chunk.rfind("\n\n")
        if cut != -1 and cut >= min_cut:
            parts.append(remaining[:cut].rstrip())
            remaining = remaining[cut + 2 :].lstrip()
            continue

        # Try line break
        cut = chunk.rfind("\n")
        if cut != -1 and cut >= min_cut:
            parts.append(remaining[:cut].rstrip())
            remaining = remaining[cut + 1 :].lstrip()
            continue

        # Try sentence end
        cut = chunk.rfind(". ")
        if cut != -1 and cut >= min_cut:
            parts.append(remaining[: cut + 1].rstrip())
            remaining = remaining[cut + 2 :].lstrip()
            continue

        # Try word boundary
        cut = chunk.rfind(" ")
        if cut != -1 and cut >= min_cut:
            parts.append(remaining[:cut].rstrip())
            remaining = remaining[cut + 1 :].lstrip()
            continue

        # Force split (extreme edge case — no break points)
        parts.append(remaining[:max_length])
        remaining = remaining[max_length:]

    return parts
