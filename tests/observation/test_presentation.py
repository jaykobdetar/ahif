"""Fictional report derivatives; no scientific analysis or private inputs."""
from copy import deepcopy

import pytest
from markdown_it import MarkdownIt

from bridge.common import C, load, sha
from bridge.observation_presentation import COUNT_LABELS, present


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / "analysis"
    source.mkdir()
    (source / "report.html").write_bytes(b"<!doctype html><html><head></head><body><main>Fictional original.</main></body></html>\n")
    (source / "report.md").write_bytes(b"# Original fictional report\n\nKept exactly.\n")
    context = {
        "profile_id": "fictional-profile",
        "profile_version": "1.0.0",
        "projection_payload_sha256": "a" * 64,
        "counts": dict(zip(COUNT_LABELS, [10, 9, 8, 7, 2, 1, 1, 0])),
        "limitations": ["Source visibility is unknown.", "Personal authorship is unverified."],
        "language_policy": "Explicit en analysis policy; source language unknown.",
        "chronology_policy": "Use supplied creation dates for observed wording.",
    }
    return source, tmp_path / "presentation", context


def test_context_counts_original_bytes_and_bindings(inputs):
    source, output, context = inputs
    original = {p.name: p.read_bytes() for p in source.iterdir()}
    receipt = present(source, output, context)
    assert receipt == load((output / "presentation-receipt.json").read_bytes())
    assert receipt["presentation_version"] == "1.0.0"
    assert receipt["projection_payload_sha256"] == "a" * 64
    assert receipt["context_sha256"] == sha(C(context))
    assert receipt["analysis_verification_performed_by_helper"] is False
    for section, directory in [("original_reports", source), ("derived_reports", output)]:
        for item in receipt[section]:
            data = (directory / item["path"]).read_bytes()
            assert item["sha256"] == sha(data)
            assert item["byte_length"] == len(data)
    assert {p.name: p.read_bytes() for p in source.iterdir()} == original
    html = (output / "report.html").read_bytes()
    start, end = html.index(b"<section"), html.index(b"</section>") + len(b"</section>")
    assert html[:start] + html[end:] == original["report.html"]
    assert html[:start].endswith(b"<body>")
    assert (output / "report.md").read_bytes().endswith(original["report.md"])
    for name in ("report.html", "report.md"):
        text = (output / name).read_text()
        for fragment in ("supplied source fields", "complete posting history", "public visibility",
                         "personal authorship", "export-observed wording", "edited later",
                         "not a canonical AHAS report"):
            assert fragment in text
        for key, label in COUNT_LABELS.items():
            assert f"{label}: {context['counts'][key]}" in text


def test_supplied_strings_remain_inert_in_html_and_markdown(inputs):
    source, output, context = inputs
    attack = '<script>alert("x")</script> ![x](https://evil.invalid/a)\n# injected'
    context["profile_id"] = attack
    context["language_policy"] = attack
    context["chronology_policy"] = attack
    context["limitations"] = [attack]
    present(source, output, context)
    html = (output / "report.html").read_text()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    rendered = MarkdownIt("commonmark", {"html": True}).render((output / "report.md").read_text())
    assert "<script>" not in rendered
    assert "<img" not in rendered
    assert '<a href="https://evil' not in rendered
    assert "<h1>injected" not in rendered
    assert "&lt;script&gt;" in rendered


def test_deterministic_and_refuses_overwrite(inputs, tmp_path):
    source, output, context = inputs
    present(source, output, context)
    second = tmp_path / "other"
    reordered = dict(reversed(list(context.items())))
    present(source, second, reordered)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == {p.name: p.read_bytes() for p in second.iterdir()}
    with pytest.raises(ValueError, match="output_exists"):
        present(source, output, context)


@pytest.mark.parametrize("html", [b"<body class='x'></body>", b"<body><body></body>", b"<body>", b"</body><body>"])
def test_unexpected_html_leaves_no_destination(inputs, html):
    source, output, context = inputs
    (source / "report.html").write_bytes(html)
    with pytest.raises(ValueError, match="unexpected_ahas_html_body"):
        present(source, output, context)
    assert not output.exists()


@pytest.mark.parametrize("mutation", [
    lambda c: c.pop("language_policy"),
    lambda c: c.update(extra="unexpected"),
    lambda c: c.update(profile_version=1),
    lambda c: c.update(projection_payload_sha256="bad"),
    lambda c: c["counts"].update(projected_events=True),
    lambda c: c["counts"].update(projected_events=-1),
    lambda c: c["counts"].pop("distinct_events"),
    lambda c: c.update(limitations=[None]),
])
def test_invalid_context_refused(inputs, mutation):
    source, output, context = inputs
    context = deepcopy(context)
    mutation(context)
    with pytest.raises(ValueError, match="presentation_"):
        present(source, output, context)
    assert not output.exists()
