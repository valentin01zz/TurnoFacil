"""Turns a published legal document (plain text with a few Markdown marks) into safe HTML.

Supports what the documents use: "#"/"##"/"###" headings, "- " list items, "**bold**", tables are
not supported. Everything is escaped first, so a document can never inject markup.
"""

import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

BOLD = re.compile(r"\*\*(.+?)\*\*")


def inline(text):
    return BOLD.sub(r"<strong>\1</strong>", escape(text))


def render_document(body):
    html = []
    paragraph = []
    items = []

    def flush():
        if paragraph:
            html.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()
        if items:
            html.append("<ul>" + "".join(f"<li>{inline(item)}</li>" for item in items) + "</ul>")
            items.clear()

    for raw in body.splitlines():
        line = raw.strip()
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if not line:
            flush()
        elif heading:
            flush()
            # The page title is the h1; document headings start at h2.
            level = len(heading.group(1)) + 1
            html.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif line.startswith("- "):
            if paragraph:
                flush()
            items.append(line[2:])
        elif items and raw.startswith("  "):
            items[-1] += " " + line
        else:
            if items:
                flush()
            paragraph.append(line)
    flush()
    return mark_safe("\n".join(html))
