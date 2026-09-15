"""Deterministic context-bearing derivatives of frozen AHAS report files.

This trusted-files helper does not run analysis or verify its canonical outputs.
The original analysis directory remains the input to AHAS verification.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
import re

from .common import C, new_destination, sha, write_json

VERSION = "1.0.0"
COUNT_LABELS = {
    "source_observations": "Source observations",
    "distinct_events": "Distinct events",
    "projected_events": "Projected events",
    "text_bearing_events": "Text-bearing events",
    "title_bearing_events": "Title-bearing events",
    "text_excluded_events": "Events with text excluded",
    "event_excluded_events": "Events excluded entirely",
    "unresolved_conflict_events": "Events with unresolved conflicts",
}
CONTEXT_FIELDS = {
    "profile_id", "profile_version", "projection_payload_sha256", "counts",
    "limitations", "language_policy", "chronology_policy",
}
NOTICE = (
    "These are measurements of supplied source fields, not verified whole-body "
    "prose, a complete posting history, public visibility, or personal authorship."
)
CHRONOLOGY = (
    "Chronology uses supplied creation dates applied to export-observed wording; "
    "that wording may have been edited later."
)
DERIVATIVE = (
    "The unchanged original canonical AHAS report remains separate. AHAS "
    "verification applies to the original analysis artifacts; this presentation "
    "derivative is not a canonical AHAS report."
)


def _context(value):
    if not isinstance(value, dict) or set(value) != CONTEXT_FIELDS:
        raise ValueError("presentation_context_fields")
    for name in ("profile_id", "profile_version", "language_policy", "chronology_policy"):
        if not isinstance(value[name], str) or not value[name].strip():
            raise ValueError("presentation_context_" + name)
    digest = value["projection_payload_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("presentation_projection_digest")
    counts = value["counts"]
    if not isinstance(counts, dict) or set(counts) != set(COUNT_LABELS):
        raise ValueError("presentation_count_fields")
    if any(type(number) is not int or number < 0 for number in counts.values()):
        raise ValueError("presentation_count_value")
    limits = value["limitations"]
    if not isinstance(limits, list) or any(not isinstance(s, str) or not s.strip() for s in limits):
        raise ValueError("presentation_limitations")
    # Reject values outside the frozen restricted JSON profile before writing.
    C(value)
    return value


def _markdown(value):
    # Numeric entities keep user-supplied HTML and Markdown punctuation inert,
    # including raw HTML, links, images, tables, and multiline block syntax.
    return "".join(
        ch if ch.isalnum() or ch == " " else f"&#{ord(ch)};"
        for ch in value
    )


def _sections(context):
    profile = context["profile_id"] + " / " + context["profile_version"]
    policies = [("Profile", profile),
                ("Projection payload SHA-256", context["projection_payload_sha256"]),
                ("Language policy", context["language_policy"]),
                ("Chronology policy", context["chronology_policy"])]
    html = [
        '<section aria-label="Source observation context" '
        'style="border:4px solid #8b5500;background:#fff3d6;color:#241700;'
        'padding:1.5rem;margin:1rem auto;max-width:76rem">',
        '<h1>Source observation context</h1>',
        *["<p><strong>" + escape(s) + "</strong></p>" for s in (NOTICE, CHRONOLOGY)],
        "<p>" + escape(DERIVATIVE) + "</p>",
        "<dl>",
    ]
    html.extend("<dt>" + label + "</dt><dd>" + escape(text) + "</dd>" for label, text in policies)
    html.append("</dl><h2>Selection counts</h2><ul>")
    html.extend("<li>" + label + ": " + str(context["counts"][key]) + "</li>" for key, label in COUNT_LABELS.items())
    html.append("</ul><h2>Limitations</h2><ul>")
    html.extend("<li>" + escape(text) + "</li>" for text in context["limitations"])
    html.append("</ul></section>")

    md = ["# Source observation context", "", "**" + NOTICE + "**", "",
          "**" + CHRONOLOGY + "**", "", DERIVATIVE, ""]
    md.extend("- **" + label + ":** " + _markdown(text) for label, text in policies)
    md.extend(["", "## Selection counts", ""])
    md.extend("- " + label + ": " + str(context["counts"][key]) for key, label in COUNT_LABELS.items())
    md.extend(["", "## Limitations", ""])
    md.extend("- " + _markdown(text) for text in context["limitations"])
    md.extend(["", "---", "", ""])
    return "\n".join(html).encode("utf-8"), "\n".join(md).encode("utf-8")


def _binding(name, data):
    return {"path": name, "sha256": sha(data), "byte_length": len(data)}


def present(analysis_dir, destination, context: dict):
    """Create report derivatives and a deterministic receipt in a fresh directory.

    The caller supplies context bound to a projection receipt payload. This
    helper validates its shape, not its truth or the analysis verification.
    """
    context = _context(context)
    root = Path(analysis_dir)
    original = {name: (root / name).read_bytes() for name in ("report.html", "report.md")}
    for data in original.values():
        data.decode("utf-8", errors="strict")
    html = original["report.html"]
    if (html.count(b"<body>") != 1 or html.count(b"</body>") != 1
            or html.index(b"<body>") >= html.index(b"</body>")):
        raise ValueError("unexpected_ahas_html_body")
    html_section, md_section = _sections(context)
    derived = {
        "report.html": html.replace(b"<body>", b"<body>" + html_section, 1),
        "report.md": md_section + original["report.md"],
    }
    receipt = {
        "presentation_id": "ahas-source-observation-context",
        "presentation_version": VERSION,
        "projection_payload_sha256": context["projection_payload_sha256"],
        "context": context,
        "context_sha256": sha(C(context)),
        "original_reports": [_binding(name, data) for name, data in sorted(original.items())],
        "derived_reports": [_binding(name, data) for name, data in sorted(derived.items())],
        "canonical_analysis_modified": False,
        "analysis_verification_performed_by_helper": False,
    }
    with new_destination(destination) as output:
        for name, data in derived.items():
            (output / name).write_bytes(data)
        write_json(output / "presentation-receipt.json", receipt)
    return receipt
