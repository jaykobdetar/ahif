"""Fictional source-field checks for the separately versioned observation path.

These are engineering fixtures, with hand-enumerated parser outputs. No real
account evidence, inferred language, threshold changes or scientific pilot.
"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from bridge.common import ahif, load, read_bundle, sha, write_bundle
from bridge.export_observation import project, verify_projection
from bridge.projection import project as conservative_project, selection_for
from bridge.reddit import EXT, normalize, parse_time, verify_fidelity


FIX = Path(__file__).parent / "fixtures" / "prose"
EXPECTED = json.loads((FIX / "expected.json").read_text())


@pytest.fixture
def bundle(tmp_path):
    path = tmp_path / "bundle"
    normalize(FIX, path, subject="export_subject", category="synthetic")
    return path


def run(bundle, tmp_path, name="projected", **kwargs):
    manifest, *_ = read_bundle(bundle)
    destination = tmp_path / name
    receipt = project(bundle, destination,
                      selection_for(manifest["sources"][0]["source_id"]), **kwargs)
    return receipt["payload"], destination


def output_by_native(payload):
    by_alias = {row["id"]: row for row in payload["expanded_records"]}
    return {decision["key"]["id"]: by_alias[decision["output_id"]]
            for decision in payload["decisions"]
            if decision["output_id"] in by_alias}


def decision(payload, native):
    return next(item for item in payload["decisions"] if item["key"]["id"] == native)


def mutate(bundle, native, change):
    manifest, rows, accounts, _ = read_bundle(bundle)
    row = next(item for item in rows if item["record_key"]["id"] == native)
    change(row)
    row["observation_id"] = ahif.bound_id("record", row)
    write_bundle(bundle, manifest, rows, accounts)
    return row


def measured(path):
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.features import extract_records
    from account_history_analyzer.io import load_snapshot
    config = AnalysisConfig.from_toml()
    snapshot = load_snapshot(path / "records.jsonl", path / "snapshot.json", config)
    return snapshot, {row["id"]: row for row in extract_records(snapshot, config)}, config


def test_literal_source_profile_fidelity_and_known_parser_results(bundle, tmp_path):
    before = {p.name: p.read_bytes() for p in bundle.iterdir()}
    manifest, observations, _, _ = read_bundle(bundle)
    fidelity = verify_fidelity(FIX, bundle)
    assert len(fidelity["fields"]) == 5
    payload, output = run(bundle, tmp_path)
    projected = output_by_native(payload)
    snapshot, features, _ = measured(output)
    assert len(snapshot.records) == 4
    for observation in observations:
        native = observation["record_key"]["id"]
        target = projected[native]
        assert observation["lifecycle"]["state"] == "unknown"
        assert observation["lifecycle"]["edit_state"] == "unknown"
        assert observation["observed_at"]["status"] == "unknown"
        assert observation["visibility"] == "unknown"
        for part in observation["content"]["parts"]:
            field = "text" if part["role"] == "body" else "title"
            assert target[field] == part["text"]
            assert part["language"] == {"tag": "und", "basis": "unknown"}
            receipt_field = next(f for f in decision(payload, native)["fields"]
                                 if f["field"] == "ahas." + field)
            assert receipt_field["disposition"] == "copied_literal"
            assert receipt_field["source_sha256"] == sha(part["text"].encode())
            assert receipt_field["output_sha256"] == sha(target[field].encode())
        view = features[target["id"]]
        assert view["language"] == "und" and not view["masked_segments"]
        assert all(value is None for value in view["function_counts"].values())
        assert all(value["status"] == "not_run" for value in view["contractions"].values())
        if native != "p1":
            expected = EXPECTED[native]
            assert view["counts"]["retained_words"] == expected["words"]
            assert [s["text"] for s in view["segments"]] == expected["segments"]
            for name, count in expected.get("structure", {}).items():
                assert view["structure"][name] == count
    unicode_text = projected["900719925474099312345"]["text"]
    assert "e\u0301" in unicode_text and "\r\n" in unicode_text
    assert snapshot.manifest["text_format"] == "markdown"
    assert snapshot.manifest["default_language"] == "und"
    assert snapshot.manifest["capture_utc"] is None
    assert {p.name: p.read_bytes() for p in bundle.iterdir()} == before
    assert verify_projection(bundle, output)["status"] == "passed"


def test_title_only_missing_times_and_absent_parent_are_independent(bundle, tmp_path):
    from account_history_analyzer.activity import analyze_activity
    from account_history_analyzer.windows import style_eligible
    payload, output = run(bundle, tmp_path)
    rows = output_by_native(payload)
    snapshot, features, config = measured(output)
    title = rows["p1"]
    assert title["text"] is None and title["status"] == "unavailable"
    assert title["title"] == "Title remains separate."
    assert features[title["id"]]["counts"]["retained_words"] is None
    assert features[title["id"]]["title"]["counts"]["retained_words"] == 3
    assert "destination.example" not in (title["title"] or "")
    assert rows["c2"]["created_utc"] is None
    assert rows["900719925474099312345"]["created_utc"] is None
    assert all(row["parent_created_utc"] is None for row in rows.values())
    assert rows["c1"]["parent_id"] not in {r["id"] for r in rows.values()}
    assert all(not style_eligible(view, config) for view in features.values())
    activity = analyze_activity(snapshot, config)
    assert activity["event_count"] == 2
    assert activity["missing_timestamp_records"] == 2


def test_actual_frozen_analyzer_and_complete_recompute(bundle, tmp_path):
    payload, output = run(bundle, tmp_path)
    analysis = tmp_path / "analysis"
    common = ["--input", str(output / "records.jsonl"), "--manifest", str(output / "snapshot.json")]
    for command in (["analyze", *common, "--out", str(analysis)],
                    ["verify", *common, "--analysis-dir", str(analysis), "--recompute"]):
        process = subprocess.run([sys.executable, "-m", "account_history_analyzer", *command],
                                 text=True, capture_output=True, timeout=60)
        assert process.returncode == 0, process.stdout + process.stderr
    # AHAS analytical output contains floating measurements; the AHIF restricted
    # JSON profile applies to evidence/receipts, not the frozen engine result.
    results = json.loads((analysis / "results.json").read_text())
    modules = results["modules"]
    assert modules["text"]["status"] == "ok"
    assert modules["text"]["payload"]["body"]["counts"]["retained_words"] == 30
    assert modules["text"]["payload"]["titles"]["counts"]["retained_words"] == 3
    assert modules["text"]["payload"]["body"]["english_record_count"] == 0
    assert modules["activity"]["payload"]["event_count"] == 2
    assert modules["coverage"]["payload"]["unique_records"] == 4
    assert modules["coverage"]["payload"]["eligible_style_records"] == 0


@pytest.mark.parametrize("state", ["removed", "deleted", "restricted"])
def test_known_nonvisible_retained_words_excluded_but_events_retained(bundle, tmp_path, state):
    mutate(bundle, "c1", lambda r: r["lifecycle"].update(state=state))
    mutate(bundle, "p1", lambda r: r["lifecycle"].update(state=state))
    payload, output = run(bundle, tmp_path)
    rows = output_by_native(payload)
    assert len(rows) == 4
    for native in ("c1", "p1"):
        assert rows[native]["text"] is None and rows[native]["title"] is None
        assert rows[native]["status"] == (state if state in {"removed", "deleted"} else "unavailable")
        assert decision(payload, native)["decision"] == "text_excluded"
        assert decision(payload, native)["blockers"]
    snapshot, _, config = measured(output)
    from account_history_analyzer.activity import analyze_activity
    assert analyze_activity(snapshot, config)["event_count"] == 2


@pytest.mark.parametrize("case", ["partial", "truncated", "redacted", "other_author", "quote_part", "html", "bbcode", "spoiler", "strikethrough", "transformed", "unsupported_format"])
def test_known_text_blockers_preserve_metadata_event(bundle, tmp_path, case):
    def change(row):
        body = row["content"]["parts"][0]
        if case in {"partial", "truncated"}:
            row["content"]["completeness"] = case
        elif case == "redacted":
            row["content"].update(availability="redacted", completeness="partial", reason="fictional redaction")
        elif case == "other_author":
            body["attribution"]["relation"] = "other"
        elif case == "quote_part":
            extra = deepcopy(body)
            extra.update(part_id="third_party", role="quote", text="Borrowed wording.")
            extra["attribution"]["relation"] = "other"
            row["content"]["parts"].append(extra)
        elif case == "html":
            body["text"] = "<div>Retained HTML wording.</div>"
        elif case == "bbcode":
            body["text"] = "before [quote]Borrowed wording.[/quote] after"
        elif case == "spoiler":
            body["text"] = "before >!hidden wording!< after"
        elif case == "strikethrough":
            body["text"] = "before ~~struck wording~~ after"
        elif case == "transformed":
            body["fidelity"] = "transformed"
        else:
            body.update(format="other", format_variant="unreviewed-format")
    mutate(bundle, "c1", change)
    payload, _ = run(bundle, tmp_path)
    row = output_by_native(payload)["c1"]
    assert row["text"] is None and row["status"] == "unavailable"
    assert row["created_utc"] == "2026-02-01T01:02:03Z"
    assert decision(payload, "c1")["decision"] == "text_excluded"
    assert decision(payload, "c1")["blockers"]


def test_multiple_known_blockers_are_reported_together(bundle, tmp_path):
    def change(row):
        row["lifecycle"]["state"] = "removed"
        row["content"].update(availability="redacted", completeness="partial", reason="fictional redaction")
        body = row["content"]["parts"][0]
        body["attribution"]["relation"] = "other"
        body.update(format="html", text="<div>Borrowed words.</div>")
    mutate(bundle, "c1", change)
    payload, _ = run(bundle, tmp_path)
    blockers = decision(payload, "c1")["blockers"]
    assert len(blockers) >= 4
    assert len(blockers) == len(set(blockers))


def test_inverted_edit_time_is_accounted_for_without_aborting_other_events(bundle, tmp_path):
    def change(row):
        row["updated_at"] = parse_time("2026-01-01 00:00:00 UTC")
        row["lifecycle"]["edit_state"] = "edited"
    mutate(bundle, "c1", change)
    payload, output = run(bundle, tmp_path)
    rejected = decision(payload, "c1")
    assert rejected["decision"] == "event_excluded"
    assert rejected["output_id"] is None
    assert any("edit" in blocker and ("before" in blocker or "chronolog" in blocker)
               for blocker in rejected["blockers"])
    assert len(payload["expanded_records"]) == 3
    assert verify_projection(bundle, output)["status"] == "passed"


def test_missing_native_kind_is_an_event_refusal_with_inventory(bundle, tmp_path):
    mutate(bundle, "c1", lambda row: row.pop("native_kind"))
    payload, output = run(bundle, tmp_path)
    rejected = decision(payload, "c1")
    assert rejected["decision"] == "event_excluded"
    assert rejected["output_id"] is None
    assert "kind_unsupported" in rejected["blockers"]
    assert len(payload["expanded_records"]) == 3
    assert verify_projection(bundle, output)["status"] == "passed"


def test_repeated_capture_and_equal_text_keep_event_identity(bundle, tmp_path):
    manifest, rows, accounts, _ = read_bundle(bundle)
    original = next(r for r in rows if r["record_key"]["id"] == "c1")
    repeat = deepcopy(original)
    repeat["observed_at"] = parse_time("2026-03-01 00:00:00 UTC")
    repeat["observation_id"] = ahif.bound_id("record", repeat)
    separate = deepcopy(original)
    separate["record_key"]["id"] = "c3"
    separate["observation_id"] = ahif.bound_id("record", separate)
    rows.extend([repeat, separate])
    write_bundle(bundle, manifest, rows, accounts)
    payload, _ = run(bundle, tmp_path)
    decisions = payload["decisions"]
    assert len(decisions) == 6
    assert len(payload["expanded_records"]) == 5
    assert sum(d["decision"] == "equivalent_capture" for d in decisions) == 1
    c1 = [d for d in decisions if d["key"]["id"] == "c1"]
    assert len({d["output_id"] for d in c1}) == 1
    mapped = output_by_native(payload)
    assert mapped["c1"]["text"] == mapped["c3"]["text"]
    assert mapped["c1"]["id"] != mapped["c3"]["id"]


@pytest.mark.parametrize("conflict", ["wording", "actor"])
def test_conflicting_observations_never_resolved_by_last_write(bundle, tmp_path, conflict):
    manifest, rows, accounts, _ = read_bundle(bundle)
    competing = deepcopy(next(r for r in rows if r["record_key"]["id"] == "c1"))
    if conflict == "wording":
        competing["content"]["parts"][0]["text"] = "Different later wording."
    else:
        competing["actor"] = {"namespace": "urn:ahif:service:reddit", "collection": "accounts",
                              "id_type": "handle", "id": "other-fictional-subject"}
    competing["observation_id"] = ahif.bound_id("record", competing)
    rows.append(competing)
    write_bundle(bundle, manifest, rows, accounts)
    payload, _ = run(bundle, tmp_path)
    assert len(payload["expanded_records"]) == 3
    excluded = [d for d in payload["decisions"] if d["key"]["id"] == "c1"]
    assert len(excluded) == 2
    assert {d["decision"] for d in excluded} == {"unresolved_conflict"}
    assert all(d["output_id"] is None for d in excluded)


@pytest.mark.parametrize("identity", ["unknown", "handle"])
def test_unestablished_actor_does_not_become_export_subject(bundle, tmp_path, identity):
    def change(row):
        if identity == "unknown":
            row["actor"] = None
            for part in row["content"]["parts"]:
                part["attribution"]["relation"] = "unknown"
        else:
            row["actor"] = {"namespace": "urn:ahif:service:reddit", "collection": "accounts",
                            "id_type": "handle", "id": "fictional-name"}
    mutate(bundle, "c1", change)
    payload, _ = run(bundle, tmp_path)
    assert len(payload["expanded_records"]) == 3
    assert decision(payload, "c1")["decision"] == "event_excluded"
    assert decision(payload, "c1")["output_id"] is None


def test_unrecognized_source_profile_refuses_even_schema_valid_bundle(bundle, tmp_path):
    manifest, rows, accounts, _ = read_bundle(bundle)
    source = manifest["sources"][0]
    source["extensions"][EXT]["profile_sha256"] = "f" * 64
    source["source_id"] = ahif.bound_id("source", source)
    new_sid = source["source_id"]
    for row in rows:
        row["source_id"] = new_sid
        row["actor"]["id"] = new_sid + "#export-subject"
        row["observation_id"] = ahif.bound_id("record", row)
    for coverage in manifest["coverage"]:
        coverage["source_id"] = new_sid
        coverage["account_key"]["id"] = new_sid + "#export-subject"
    write_bundle(bundle, manifest, rows, accounts)
    with pytest.raises(ValueError, match="source_profile"):
        run(bundle, tmp_path)
    assert not (tmp_path / "projected").exists()


def test_optional_english_declaration_is_exactly_scope_bound(bundle, tmp_path):
    manifest, observations, _, _ = read_bundle(bundle)
    source_id = manifest["sources"][0]["source_id"]
    selected = next(r for r in observations if r["record_key"]["id"] == "c1")
    declaration = {"declaration_version": "1.0.0", "source_id": source_id,
                   "account_key": selection_for(source_id)["account_key"],
                   "observation_ids": [selected["observation_id"]],
                   "language": "en", "basis": "supplier_confirmation",
                   "statement": "For this fictional fixture, its author explicitly declares English."}
    baseline, _ = run(bundle, tmp_path, "und")
    declared, output = run(bundle, tmp_path, "en", language_declaration=declaration)
    rows = output_by_native(declared)
    assert rows["c1"]["language"] == "en"
    assert all(row["language"] == "und" for native, row in rows.items() if native != "c1")
    assert declared["ahas"]["canonical_snapshot_sha256"] != baseline["ahas"]["canonical_snapshot_sha256"]
    _, features, _ = measured(output)
    assert features[rows["c1"]["id"]]["contractions"]["dont_do_not"]["expanded"] == 0
    assert selected["content"]["parts"][0]["language"]["tag"] == "und"
    assert verify_projection(bundle, output)["status"] == "passed"
    for name, changed in [("source", {**declaration, "source_id": "sha256:" + "f" * 64}),
                          ("scope", {**declaration, "observation_ids": ["sha256:" + "e" * 64]}),
                          ("basis", {**declaration, "basis": "inferred_from_text"})]:
        with pytest.raises(Exception):
            run(bundle, tmp_path, "bad-" + name, language_declaration=changed)
        assert not (tmp_path / ("bad-" + name)).exists()


def reverse_properties(value):
    if isinstance(value, dict):
        return {key: reverse_properties(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reverse_properties(item) for item in value]
    return value


def test_relocation_property_order_and_operational_clock_contract(bundle, tmp_path):
    first, output = run(bundle, tmp_path, "first", executed_at="clock one")
    relocated_source = tmp_path / "relocated-source"
    shutil.copytree(FIX, relocated_source)
    second_bundle = tmp_path / "second-bundle"
    normalize(relocated_source, second_bundle, subject="export_subject", category="synthetic")
    assert {p.name: p.read_bytes() for p in bundle.iterdir()} == {p.name: p.read_bytes() for p in second_bundle.iterdir()}
    second, second_output = run(second_bundle, tmp_path, "second", executed_at="clock two")
    assert first == second
    manifest = load((second_bundle / "manifest.json").read_bytes())
    raw = b"".join(json.dumps(reverse_properties(load(line)), ensure_ascii=False).encode() + b"\n"
                   for line in (second_bundle / "records.jsonl").read_bytes().splitlines())
    (second_bundle / "records.jsonl").write_bytes(raw)
    descriptor = next(f for f in manifest["files"] if f["path"] == "records.jsonl")
    descriptor.update(sha256=sha(raw), byte_length=len(raw))
    (second_bundle / "manifest.json").write_text(json.dumps(reverse_properties(manifest), indent=2))
    reordered, reordered_output = run(second_bundle, tmp_path, "reordered", executed_at="clock three")
    assert reordered["ahas"]["canonical_snapshot_sha256"] == first["ahas"]["canonical_snapshot_sha256"]
    assert reordered["input"]["manifest_bytes"] != first["input"]["manifest_bytes"]
    for name in ("records.jsonl", "snapshot.json"):
        assert (output / name).read_bytes() == (second_output / name).read_bytes() == (reordered_output / name).read_bytes()
    assert verify_projection(second_bundle, reordered_output)["status"] == "passed"


def test_normalizer_operational_clock_never_enters_evidence_identity(tmp_path, monkeypatch):
    from bridge import reddit

    class FrozenDatetime(datetime):
        # Inherited strptime still parses actual supplied creation dates.
        current_year = 1985

        @classmethod
        def now(cls, tz=None):
            return cls(cls.current_year, 7, 12, 13, 14, 15, tzinfo=tz)

        @classmethod
        def today(cls):
            return cls.now()

    monkeypatch.setattr(reddit, "datetime", FrozenDatetime)
    first = tmp_path / "past-clock"
    second = tmp_path / "future-clock"
    assert reddit.datetime.now().year == 1985
    assert reddit.datetime.today().year == 1985
    normalize(FIX, first, subject="export_subject", category="synthetic")
    FrozenDatetime.current_year = 2095
    assert reddit.datetime.now().year == 2095
    assert reddit.datetime.today().year == 2095
    normalize(FIX, second, subject="export_subject", category="synthetic")
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {
        p.name: p.read_bytes() for p in second.iterdir()}
    _, rows, _, _ = read_bundle(second)
    assert next(r for r in rows if r["record_key"]["id"] == "c1")["created_at"]["value"] == "2026-02-01T01:02:03Z"
    assert all(r["observed_at"]["status"] == "unknown" for r in rows)


def test_frozen_conservative_profile_keeps_its_text_refusals(bundle, tmp_path):
    manifest, *_ = read_bundle(bundle)
    receipt = conservative_project(bundle, tmp_path / "conservative",
                                   selection_for(manifest["sources"][0]["source_id"]))
    assert receipt["payload"]["projection_profile"]["id"] == "ahas-conservative"
    assert receipt["payload"]["expanded_records"] == []
    assert all(d["decision"] == "quarantined" for d in receipt["payload"]["decisions"])


def test_projection_replay_detects_literal_output_tampering(bundle, tmp_path):
    _, output = run(bundle, tmp_path)
    path = output / "records.jsonl"
    path.write_bytes(path.read_bytes().replace(b"Orchard notes", b"Orchard edits"))
    with pytest.raises(ValueError):
        verify_projection(bundle, output)
