"""Independent literal-field checks use only fictional source files."""
import csv
from pathlib import Path
import shutil

import pytest

from bridge.common import C, ahif, load, read_bundle, sha, write_bundle, write_json
from bridge.export_observation import project, selection_for
from bridge.reddit import normalize
from scripts.verify_observation_fidelity import FIDELITY_DOMAIN, RECEIPT_DOMAIN, verify

FIXTURE = Path(__file__).parent / "fixtures/prose"


def prepare(tmp_path, source=FIXTURE, mutate=None):
    bundle = tmp_path / "bundle"
    normalized = normalize(source, bundle, subject="export_subject", category="synthetic")
    if mutate:
        manifest, rows, accounts, _ = read_bundle(bundle)
        mutate(rows)
        for row in rows:
            row["observation_id"] = ahif.bound_id("record", row)
        write_bundle(bundle, manifest, rows, accounts)
    output = tmp_path / "projection"
    project(bundle, output, selection_for(normalized["source_id"]))
    return bundle, output


def revise_projection(output, change):
    records = [load(line) for line in (output / "records.jsonl").read_bytes().splitlines()]
    receipt = load((output / "projection-receipt.json").read_bytes())
    change(records, receipt["payload"])
    data = b"".join(C(row) + b"\n" for row in records)
    (output / "records.jsonl").write_bytes(data)
    for item in receipt["payload"]["outputs"]:
        if item["path"] == "records.jsonl":
            item.update(sha256=sha(data), byte_length=len(data))
    receipt["payload_sha256"] = sha(RECEIPT_DOMAIN + C(receipt["payload"]))
    write_json(output / "projection-receipt.json", receipt)


def test_every_fictional_source_field_accounted_and_no_prose_in_receipt(tmp_path):
    bundle, output = prepare(tmp_path)
    receipt = verify(FIXTURE, bundle, output)
    payload = receipt["payload"]
    assert receipt["payload_sha256"] == sha(FIDELITY_DOMAIN + C(payload))
    assert payload["counts"] == {
        "distinct_events": 4, "empty_source_fields": 1, "excluded_fields": 1,
        "projected_events": 4, "retained_body_fields": 3, "retained_title_fields": 1,
        "sentinel_body_fields": 0, "source_fields": 5, "source_observations": 4,
    }
    assert all(f["ahif_faithful"] for f in payload["fields"])
    assert any(f["record_key"]["id"] == "900719925474099312345" for f in payload["fields"])
    for member in ("comments.csv", "posts.csv"):
        with (FIXTURE / member).open(newline="") as source:
            for row in csv.DictReader(source):
                for name in ("body", "title"):
                    if row.get(name):
                        assert row[name].encode() not in C(receipt)


def test_tampered_literal_fails_even_with_refreshed_output_receipt_hashes(tmp_path):
    bundle, output = prepare(tmp_path)
    def change(records, payload):
        next(r for r in records if r["text"])["text"] = "Different words."
    revise_projection(output, change)
    with pytest.raises(ValueError, match="literal_source_output_mismatch"):
        verify(FIXTURE, bundle, output)


def test_silent_title_drop_fails_even_with_refreshed_hashes(tmp_path):
    bundle, output = prepare(tmp_path)
    def change(records, payload):
        row = next(r for r in records if r["title"] is not None)
        row["title"] = None
        decision = next(d for d in payload["decisions"] if d["output_id"] == row["id"])
        decision["blockers"] = []
        field = next(f for f in decision["fields"] if f["field"] == "ahas.title")
        field.update(disposition="omitted", reason="unjustified omission", output_sha256=None, blockers=[])
    revise_projection(output, change)
    with pytest.raises(ValueError, match="unexplained_text_exclusion"):
        verify(FIXTURE, bundle, output)


def test_native_identity_checked_independently_of_projected_alias(tmp_path):
    def mutate(rows):
        next(r for r in rows if r["record_key"]["id"] == "c1")["record_key"]["id"] = "other"
    bundle, output = prepare(tmp_path, mutate=mutate)
    with pytest.raises(ValueError, match="source_key"):
        verify(FIXTURE, bundle, output)


def test_sentinels_and_known_partial_text_have_explicit_accounting(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    shutil.copyfile(FIXTURE / "posts.csv", source / "posts.csv")
    with (FIXTURE / "comments.csv").open(newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames
        rows = list(reader)
    rows[0]["body"] = "[removed]"
    with (source / "comments.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    def mutate(observations):
        row = next(r for r in observations if r["record_key"]["id"] == "c2")
        row["content"].update(completeness="partial", reason="Fictional known partial field.")
    bundle, output = prepare(tmp_path, source, mutate)
    receipt = verify(source, bundle, output)
    assert receipt["payload"]["counts"]["sentinel_body_fields"] == 1
    assert receipt["payload"]["counts"]["retained_body_fields"] == 1
    dispositions = {(f["record_key"]["id"], f["source_field"]): f["disposition"] for f in receipt["payload"]["fields"]}
    assert dispositions[("c1", "body")] == "source_unavailability_marker"
    assert dispositions[("c2", "body")] == "policy_text_exclusion"


def test_source_change_fails_frozen_source_to_ahif_check(tmp_path):
    bundle, output = prepare(tmp_path)
    source = tmp_path / "source"
    shutil.copytree(FIXTURE, source)
    with (source / "comments.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError):
        verify(source, bundle, output)


@pytest.mark.parametrize("conflict", [False, True])
def test_repeated_source_rows_each_accounted_without_duplicate_output_events(tmp_path, conflict):
    source = tmp_path / "source"
    source.mkdir()
    shutil.copyfile(FIXTURE / "posts.csv", source / "posts.csv")
    with (FIXTURE / "comments.csv").open(newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames
        rows = list(reader)
    duplicate = dict(rows[0])
    if conflict:
        duplicate["body"] = "Different fictional revision."
    rows.append(duplicate)
    with (source / "comments.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    bundle, output = prepare(tmp_path, source)
    receipt = verify(source, bundle, output)
    counts = receipt["payload"]["counts"]
    assert counts["source_observations"] == 5
    assert counts["source_fields"] == 6
    assert counts["distinct_events"] == 4
    assert counts["projected_events"] == (3 if conflict else 4)
    event_fields = [f for f in receipt["payload"]["fields"] if f["record_key"]["id"] == "c1"]
    assert len(event_fields) == 2
    if conflict:
        assert all(f["event_decision"] == "unresolved_conflict" for f in event_fields)
    else:
        assert {f["event_decision"] for f in event_fields} == {"accepted", "equivalent_capture"}
