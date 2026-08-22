#!/usr/bin/env python3
"""Shared PDF-page scope helpers for contest-final audits."""

from __future__ import annotations

import re
from typing import Iterable


def compact_marker_text(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def page_has_any_marker(text: str, terms: Iterable[str]) -> bool:
    compact = compact_marker_text(text)
    return any(compact_marker_text(term) in compact for term in terms)


def page_has_heading_marker(text: str, terms: Iterable[str]) -> bool:
    """Return true only when a marker occupies a heading-like PDF text line."""

    markers = [compact_marker_text(term) for term in terms if compact_marker_text(term)]
    for raw_line in text.splitlines():
        line = compact_marker_text(raw_line)
        if not line:
            continue
        for marker in markers:
            if line == marker:
                return True
            pattern = rf"(?:\d+(?:\.\d+)*[.\):\u3001]?)?{re.escape(marker)}(?:[a-z0-9]|[\u4e00-\u9fff])?"
            if re.fullmatch(pattern, line, flags=re.I):
                return True
    return False


def find_marker_page(
    pages: list[str],
    terms: Iterable[str],
    start_at: int = 0,
    skip_terms: Iterable[str] = (),
    *,
    heading_only: bool = False,
) -> int | None:
    matcher = page_has_heading_marker if heading_only else page_has_any_marker
    for index in range(max(0, start_at), len(pages)):
        if skip_terms and page_has_any_marker(pages[index], skip_terms):
            continue
        if matcher(pages[index], terms):
            return index
    return None
