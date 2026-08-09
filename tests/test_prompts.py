#!/usr/bin/env python3
"""The prompt set on the wire must equal the prompt set in the pre-registration.

prompts.py is what the runners send; PROMPTS.md is what a reviewer reads. Nothing
enforces that they agree except this file. Every template string is required to appear
verbatim inside PROMPTS.md, with the single documented substitution ({position} in code
is written {{POSITION}} in the document).

If this fails, either the document drifted or someone edited a frozen prompt — both are
pre-registration violations, not test bugs.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prompts  # noqa: E402

DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PROMPTS.md")


def _doc_text() -> str:
    with open(DOC) as fh:
        return fh.read()


def _as_written(template: str) -> str:
    return template.replace("{position}", "{{POSITION}}")


def test_every_template_is_verbatim_in_the_document():
    doc = _doc_text()
    missing = []
    for cond, variants in prompts.CONDITIONS.items():
        for variant, template in variants.items():
            if _as_written(template) not in doc:
                missing.append(f"{cond}.{variant}")
    assert not missing, f"not verbatim in PROMPTS.md: {missing}"


def test_system_prompt_and_pushback_are_verbatim():
    doc = _doc_text()
    assert prompts.SYSTEM_PROMPT in doc
    assert prompts.C5_TURN2 in doc


def test_position_formats_are_verbatim():
    doc = _doc_text()
    for name, tmpl in prompts.FORMATS.items():
        assert tmpl.format(fen="{fen}", pgn="{pgn}", movelist="{movelist}") in doc, name


def test_c1_never_names_the_tactic():
    prompts.check_c1_exclusion_list()


def test_length_cap_present_everywhere_except_c3():
    cap = "Keep your answer under 150 words."
    for cond in ("C0", "C1", "C2"):
        for variant, template in prompts.CONDITIONS[cond].items():
            assert cap in template, f"{cond}.{variant} lost the length cap"
    # §6: the cap is deliberately absent from C3, a 32-piece board would be truncated.
    assert cap not in prompts.C3["a"]


def test_render_substitutes_only_the_position():
    pos = {"fen": "8/8/8/8/8/8/8/K6k w - - 0 1", "pgn": "x", "movelist": "y"}
    out = prompts.render("C2", "a", pos)
    assert out.startswith("Position (FEN): 8/8/8/8/8/8/8/K6k w - - 0 1")
    assert "Is anything hanging, and is there a mate in 1? Name the square." in out
    # C0 is position-free by construction.
    assert "Position (FEN)" not in prompts.render("C0", "a", None)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
