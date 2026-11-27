"""Convert a downloaded IRS / GOV.UK page to Markdown, keeping the text verbatim and dropping site chrome.

Used to prepare the real public documents in benchmark/corpus/public_v*/. The output starts at the first
line containing START (or equal to it, when START begins with "=") and stops before the first line containing
any END marker. Headings, paragraphs, list items and tables are kept; scripts, navigation, headers, footers,
forms and asides are dropped.

Usage: python benchmark/html_to_markdown.py IN.html OUT.md START END [END ...]
"""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path

SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "form", "aside", "button"}
HEAD = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### "}
BLOCK = ("p", "div", "li", "dt", "dd", "section", "article")


class Markdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.cur = ""
        self.prefix = ""
        self.skip = 0
        self.row: list[str] | None = None
        self.cell: str | None = None
        self.rows_in_table = 0

    def flush(self, prefix: str = "") -> None:
        text = " ".join(self.cur.split())
        if text:
            self.lines.append(prefix + text)
        self.cur = ""

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "table":
            self.flush()
            self.lines.append("")
            self.rows_in_table = 0
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = ""
        elif tag in HEAD or tag in BLOCK:
            self.flush(self.prefix)
            self.prefix = HEAD.get(tag, "* " if tag == "li" else "")
        elif tag == "br":
            if self.cell is not None:
                self.cell += " "
            else:
                self.cur += " "

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("td", "th") and self.row is not None and self.cell is not None:
            self.row.append(" ".join(self.cell.split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.lines.append("| " + " | ".join(self.row) + " |")
            if self.rows_in_table == 0:
                self.lines.append("|" + "---|" * len(self.row))
            self.rows_in_table += 1
            self.row = None
        elif tag == "table":
            self.lines.append("")
        elif tag in HEAD or tag in BLOCK[:5]:
            self.flush(self.prefix)
            self.prefix = ""
            if tag in HEAD or tag == "p":
                self.lines.append("")

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell += data
        else:
            self.cur += data


def convert(raw: str, start: str, ends: list[str]) -> str:
    p = Markdown()
    p.feed(raw[raw.find("<main") :] if "<main" in raw else raw)
    p.flush()
    lines, keep = [], False
    for line in p.lines:
        if not keep and (line.strip() == start[1:] if start.startswith("=") else start in line):
            keep = True
        if keep and any(e in line for e in ends):
            break
        if keep and line.strip() not in ("*", "#", "##", "###"):
            lines.append(line.rstrip())
    text = "\n".join(lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip() + "\n"


def main() -> None:
    src, out, start, ends = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4:]
    text = convert(src.read_text(encoding="utf-8", errors="replace"), start, ends)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(out.name, len(text.split()), "words")


if __name__ == "__main__":
    main()
