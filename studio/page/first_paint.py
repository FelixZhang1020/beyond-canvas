"""Write the Chinese into the markup, so the first paint is already right.

Every label is authored in English inside `src/10-app.html` and swapped to
Chinese by script at DOMContentLoaded. On this machine the swap is invisible.
Over the classroom's public link it is not: the page is one file of nearly a
megabyte, the script that does the swapping is the last thing in it, and the
English markup is on screen for as long as the rest of the file takes to
arrive. A teacher opening the studio reads English for several seconds.

So the build writes the Chinese in first. The bytes that paint are already the
ones a teacher should read, and no network is slow enough to show the wrong
language. English is still there and still one tap away; it is now the side
that flashes, which is the right way round for a Chinese art centre.

`locales/zh.js` stays the only place Chinese is written. What this module makes
is a derived copy -- mechanical, one way, and checked twice: a label with no
Chinese stops the build by name, and `tests/page/first-paint.test.mjs` compares
every rendered label against the same table JavaScript itself reads, which is a
different method from the scanner below and so can actually disagree with it.
"""
from __future__ import annotations

import re
from html import escape

TABLE = "Studio.strings.zh"
ELEMENT = re.compile(r'<(\w+)\b([^>]*\bdata-t="([\w.\-]+)"[^>]*)>([^<]*)</\1>')
HINT = re.compile(r'<(\w+)\b([^>]*\bdata-t-ph="([\w.\-]+)"[^>]*)>')
SPOKEN = re.compile(r'<(\w+)\b([^>]*\bdata-t-aria="([\w.\-]+)"[^>]*)>')
PLACEHOLDER = re.compile(r'placeholder="[^"]*"')
SPOKEN_LABEL = re.compile(r'aria-label="[^"]*"')
NAME = re.compile(r'[A-Za-z_$][\w$]*|\d+')
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def _string(source: str, start: int) -> tuple[str, int]:
    """Read one JavaScript string literal, returning its value and what follows."""
    quote, out, i = source[start], [], start + 1
    while i < len(source):
        ch = source[i]
        if ch == "\\":
            nxt = source[i + 1]
            if nxt == "u":
                out.append(chr(int(source[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append(ESCAPES.get(nxt, nxt))
            i += 2
            continue
        if ch == quote:
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    raise ValueError("a string literal that never closes")


def chinese_table(source: str) -> dict[str, str]:
    """The plain string entries of `Studio.strings.zh`, by their key.

    Only the top level: `colours` and `book` hold nested objects whose inner
    names (`title`, `pages`) collide with real keys, and a scan that flattened
    them would quietly hand the page the wrong words.
    """
    i = source.index("{", source.index(TABLE))
    table: dict[str, str] = {}
    depth, key, after_colon = 0, None, False
    while i < len(source):
        ch = source[i]
        if ch == "/" and source[i + 1] in "/*":
            end = source.index("\n", i) if source[i + 1] == "/" else source.index("*/", i) + 1
            i = end + 1
            continue
        if ch in "{[":
            depth += 1
            i += 1
            continue
        if ch in "}]":
            depth -= 1
            if depth == 0:
                return table
            i += 1
            continue
        if depth == 1 and ch in "\"'":
            text, i = _string(source, i)
            if after_colon and key is not None:
                table[key] = text
            elif not after_colon:
                key = text
            continue
        if depth == 1 and ch == ":":
            after_colon = True
        elif depth == 1 and ch == ",":
            after_colon, key = False, None
        elif depth == 1 and not after_colon and (name := NAME.match(source, i)):
            key = name.group(0)
            i = name.end()
            continue
        i += 1
    raise ValueError(f"{TABLE} is never closed")


def fill(markup: str, table: dict[str, str]) -> str:
    """Replace every label, example and spoken label with its Chinese."""
    missing: list[str] = []

    def label(match: re.Match[str]) -> str:
        tag, attrs, key = match.group(1), match.group(2), match.group(3)
        if key not in table:
            missing.append(key)
            return match.group(0)
        return f"<{tag}{attrs}>{escape(table[key], quote=False)}</{tag}>"

    def hint(match: re.Match[str]) -> str:
        tag, attrs, key = match.group(1), match.group(2), match.group(3)
        if key not in table:
            missing.append(key)
            return match.group(0)
        written = f'placeholder="{escape(table[key])}"'
        attrs = (PLACEHOLDER.sub(lambda _: written, attrs, count=1) if PLACEHOLDER.search(attrs)
                 else f"{attrs} {written}")
        return f"<{tag}{attrs}>"

    def spoken(match: re.Match[str]) -> str:
        tag, attrs, key = match.group(1), match.group(2), match.group(3)
        if key not in table:
            missing.append(key)
            return match.group(0)
        written = f'aria-label="{escape(table[key])}"'
        attrs = (SPOKEN_LABEL.sub(lambda _: written, attrs, count=1) if SPOKEN_LABEL.search(attrs)
                 else f"{attrs} {written}")
        return f"<{tag}{attrs}>"

    filled = SPOKEN.sub(spoken, HINT.sub(hint, ELEMENT.sub(label, markup)))
    if missing:
        raise ValueError("no Chinese for: " + ", ".join(sorted(set(missing))))
    return filled
