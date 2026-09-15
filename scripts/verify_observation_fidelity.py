#!/usr/bin/env python3
"""Independently account for selected CSV fields through AHIF and AHAS inputs.

No mapping functions from the observation projection are reused. The frozen
normalizer's source-to-AHIF check is followed by direct source-to-output string
comparisons and independent full-key alias checks. Receipts contain hashes and
private record locators, never original body/title strings.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.common import C, load, read_bundle, sha
from bridge.reddit import EXT, NS, PROFILE, parse_members, read_members, verify_fidelity

VERSION = "1.0.0"
RECEIPT_DOMAIN = b"AHIF:reddit-export-observation-receipt:1.0.0\n"
FIDELITY_DOMAIN = b"AHIF:observation-field-fidelity:1.0.0\n"


def _require(condition, reason):
    if not condition:
        raise ValueError("independent_fidelity_" + reason)


def _record_alias(key):
    return "ahas-r:" + sha(b"AHIF:projection-record-key:1\n" + C(key))


def verify(source, bundle, projection):
    """Return deterministic private field accounting; fail on any mismatch."""
    source_fields = verify_fidelity(source, bundle)
    members = read_members(source)
    raw = parse_members(members)
    manifest, observations, accounts, _ = read_bundle(bundle)
    _require(not accounts, "unexpected_accounts")
    root = Path(projection)
    receipt_bytes = (root / "projection-receipt.json").read_bytes()
    receipt = load(receipt_bytes)
    payload = receipt["payload"]
    _require(receipt["receipt_version"] == VERSION and payload["ahif_version"] == "0.1.1", "contract_version")
    _require(payload["projection_profile"]["id"] == "reddit-export-observation"
             and payload["projection_profile"]["version"] == VERSION, "projection_profile")
    _require(receipt["payload_sha256"] == sha(RECEIPT_DOMAIN + C(payload)), "receipt_digest")
    _require(payload["input"]["canonical_manifest_sha256"] == sha(C(manifest)), "bundle_binding")
    outputs = {f["path"]: f for f in payload["outputs"]}
    _require(len(outputs) == len(payload["outputs"]) and set(outputs) == {"records.jsonl", "snapshot.json"}, "output_inventory")
    for name, binding in outputs.items():
        data = (root / name).read_bytes()
        _require(binding["sha256"] == sha(data) and binding["byte_length"] == len(data), "output_digest")
    records = [load(line) for line in (root / "records.jsonl").read_bytes().splitlines() if line]
    projected = {r["id"]: r for r in records}
    _require(len(projected) == len(records), "duplicate_output_id")
    aliases = {a["alias"]: a for a in payload["aliases"]}
    _require(len(aliases) == len(payload["aliases"]), "duplicate_alias")
    for alias, entry in aliases.items():
        if entry["type"] == "record":
            _require(alias == _record_alias(entry["key"]), "alias_identity")
    decisions = {d["observation_id"]: d for d in payload["decisions"]}
    _require(len(decisions) == len(payload["decisions"]), "duplicate_decision")
    _require(set(decisions) == {r["observation_id"] for r in observations}, "decision_inventory")
    selected = {}
    for decision in decisions.values():
        if decision["decision"] in {"accepted", "text_excluded"}:
            out_id = decision["output_id"]
            _require(out_id in projected and out_id not in selected, "event_selection")
            selected[out_id] = decision
    _require(set(selected) == set(projected), "output_decision_inventory")
    expected_rows = {(name, n) for name, rows in raw.items() for n in range(1, len(rows) + 1)}
    seen = set()
    fields = []
    counts = Counter()
    for observation in observations:
        ext = observation["extensions"][EXT]
        row_position = (ext["member"], ext["row"])
        _require(row_position in expected_rows and row_position not in seen, "row_inventory")
        seen.add(row_position)
        name, number = row_position
        native = raw[name][number - 1]
        key = {"namespace": NS, "collection": PROFILE["collections"][name], "id_type": "native", "id": native["id"]}
        _require(observation["record_key"] == key, "source_key")
        decision = decisions[observation["observation_id"]]
        _require(decision["key"] == key and decision["source_id"] == observation["source_id"]
                 and decision["locator"] == observation["provenance"]["locator"], "decision_identity")
        action = decision["decision"]
        _require(action in {"accepted", "text_excluded", "event_excluded", "unresolved_conflict", "equivalent_capture"}, "unknown_decision")
        out_id = decision["output_id"]
        output = projected.get(out_id)
        if out_id is not None:
            _require(action in {"accepted", "text_excluded", "equivalent_capture"}, "excluded_output")
            _require(out_id == _record_alias(key) and output is not None, "output_identity")
            _require(aliases.get(out_id, {}).get("key") == key, "output_alias")
            governing = selected[out_id] if action == "equivalent_capture" else decision
        else:
            _require(action in {"event_excluded", "unresolved_conflict", "equivalent_capture"}, "missing_output")
            _require(bool(decision["blockers"]), "unexplained_event_exclusion")
            governing = decision
        field_rules = {f["field"]: f for f in governing["fields"]}
        _require(len(field_rules) == len(governing["fields"]), "duplicate_field_rule")
        for source_field, target_field in (("body", "text"), ("title", "title")):
            if source_field not in native:
                continue
            text = native[source_field]
            source_sha = sha(text.encode("utf-8"))
            marker = source_field == "body" and text in PROFILE["sentinels"]
            empty = text == ""
            counts["source_fields"] += 1
            counts["empty_source_fields"] += int(empty)
            counts["sentinel_body_fields"] += int(marker)
            rule = field_rules.get("ahas." + target_field)
            output_text = output[target_field] if output is not None else None
            retained = output_text is not None
            if retained:
                _require(isinstance(output_text, str) and output_text == text and not marker and not empty, "literal_source_output_mismatch")
                _require(rule is not None and rule["disposition"] == "copied_literal", "copy_disposition")
                _require(rule["source_sha256"] == source_sha and rule["output_sha256"] == source_sha
                         and rule["source_part_ids"] == [source_field], "copy_binding")
                disposition = "retained_literal"
                counts["retained_" + source_field + "_fields"] += 1
            elif output is not None:
                _require(rule is not None and rule["disposition"] == "omitted" and bool(rule["reason"]), "silent_field_drop")
                _require(rule["output_sha256"] is None, "null_output_binding")
                if not marker and not empty:
                    _require(rule["source_sha256"] == source_sha and rule["source_part_ids"] == [source_field], "omitted_source_binding")
                    _require(bool(rule["blockers"]), "unexplained_text_exclusion")
                disposition = "empty_source" if empty else "source_unavailability_marker" if marker else "policy_text_exclusion"
                counts["excluded_fields"] += 1
            else:
                disposition = "event_exclusion"
                counts["excluded_fields"] += 1
            fields.append({
                "observation_id": observation["observation_id"], "record_key": key,
                "locator": {"kind": "csv_row", "value": f"{name}#row={number};column={source_field}", "artifact_sha256": sha(members[name])},
                "source_field": source_field, "source_utf8_sha256": source_sha,
                "source_codepoints": len(text), "source_representation": "empty_field" if empty else "sentinel_marker" if marker else "source_field",
                "ahif_faithful": True, "ahif_utf8_sha256": source_sha,
                "event_decision": action, "output_id": out_id, "analytical_field": target_field,
                "projected_utf8_sha256": sha(output_text.encode("utf-8")) if retained else None,
                "disposition": disposition,
            })
    _require(seen == expected_rows, "row_inventory")
    _require(len(fields) == len(source_fields["fields"]), "field_inventory")
    for name in ("retained_body_fields", "retained_title_fields", "empty_source_fields", "sentinel_body_fields", "excluded_fields"):
        counts.setdefault(name, 0)
    counts.update(source_observations=len(observations), distinct_events=len({C(r["record_key"]) for r in observations}), projected_events=len(projected))
    result = {
        "status": "passed", "fidelity_version": VERSION,
        "source_members": [{"path": name, "sha256": sha(data), "byte_length": len(data)} for name, data in sorted(members.items())],
        "canonical_manifest_sha256": sha(C(manifest)),
        "projection_payload_sha256": receipt["payload_sha256"],
        "source_to_ahif_check_sha256": sha(C(source_fields)),
        "counts": dict(sorted(counts.items())),
        "fields": sorted(fields, key=lambda f: (f["locator"]["value"], f["observation_id"])),
        "scope": "Decoded literal source fields and declared full-key aliases; AHAS derived text is separately tested.",
    }
    return {"receipt_version": VERSION, "payload": result, "payload_sha256": sha(FIDELITY_DOMAIN + C(result))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "bundle", "projection", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    receipt = verify(args.source, args.bundle, args.projection)
    # The caller chooses an existing private parent; never overwrite a receipt.
    with args.out.open("xb") as handle:
        handle.write(C(receipt) + b"\n")
    print("Independent field fidelity passed; receipt written.")


if __name__ == "__main__":
    main()
