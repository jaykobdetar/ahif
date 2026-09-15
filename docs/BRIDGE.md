# Offline Reddit export bridge 1.0.0

This page documents the original conservative metadata-only projection. The
separate [export-observation profile](EXPORT_OBSERVATION.md) now supports
explicitly scoped supplied-field text measurements without changing this profile.

AHIF **0.1.1 remains frozen**. This implementation adds a source profile, a
normalizer and an explicit AHAS projection outside that versioned directory.
The [execution report](BRIDGE_REPORT.md) states what was actually tested.

## Supported contracts

| Boundary | Exact support |
|---|---|
| Source | The observed UTF-8 CSV layout in [reddit-export-csv 1.0.0](../profiles/reddit-export-csv/1.0.0/profile.json), as two files in a directory or exact root members of a ZIP. Only `comments.csv` and `posts.csv` are opened. |
| Evidence | AHIF 0.1.1, full structural and semantic checking, canonical manifest/records, source hashes and locators. No raw members included. |
| Selection | One explicitly selected source-local export subject, all supplied records considered without date sampling. Unknown and other actors/sources excluded with reasons. Equivalent observations select one; conflicts quarantine the key. |
| Projection | [ahas-conservative 1.0.0](../profiles/ahas-conservative/1.0.0/profile.json): metadata-only unavailable records. AHAS record/snapshot schemas 1.0.0 and installed engine 1.0.4, with unchanged defaults. |
| Receipt | [Projection receipt 1.0.0](../profiles/ahas-conservative/1.0.0/receipt.schema.json), including exact input hashes, selection, every decision, aliases, field dispositions, outputs, expanded loader values and engine/configuration identities. |

**Retained prose is not supported for projection by this profile.** The observed
CSV has no explicit lifecycle/completeness declaration, native author ID, edit
flag or per-record language. It preserves source fields without turning those
unknowns into visible, complete, English or unedited claims. Native body markup
uses AHIF `other` with a declared dialect label, not an invented CommonMark claim.

No support is claimed for live Reddit retrieval, X/forum converters, HTML/BBCode
conversion, quote/signature segmentation, manual conflict overrides, account
reconciliation across captures, arbitrary ZIP layouts, raw-evidence publication,
scientific authorship detection or a hostile ingestion service. A source-local
export subject is a caller-supplied attribution scope, not a verified person.

## Run locally

Use Python 3.12 with the existing AHAS 1.0.4 environment and the dependencies in
`requirements-bridge-test.txt`. No engine installation or update happens in these
commands. From this repository root, define `PYTHON` as that environment's Python
and set `SOURCE`, `PRIVATE`, and `ENGINE` to local paths. `PRIVATE` must be a new
private work directory outside the repository. For example:

```bash
mkdir -m 700 "$PRIVATE"
"$PYTHON" -m bridge.cli normalize --source "$SOURCE" --subject export_subject \
  --out "$PRIVATE/bundle" --fidelity-out "$PRIVATE/fidelity.json"
```

Use `--subject unknown` when even the single-export-subject attribution is not
established. Such evidence is valid but cannot be projected by this profile.
`--category synthetic` is only for fictional input, never a way to anonymize real
input. Archive filenames, local paths and execution time never become evidence.

The normalize summary returns a `source_id`; copy it exactly into `SOURCE_ID`:

```bash
"$PYTHON" -m bridge.cli project --bundle "$PRIVATE/bundle" \
  --source-id "$SOURCE_ID" --out "$PRIVATE/projection"
"$PYTHON" -m bridge.cli verify --bundle "$PRIVATE/bundle" --output "$PRIVATE/projection"
"$PYTHON" -m bridge.cli fidelity --source "$SOURCE" --bundle "$PRIVATE/bundle"
"$ENGINE/.venv/bin/ahas" analyze --input "$PRIVATE/projection/records.jsonl" \
  --manifest "$PRIVATE/projection/snapshot.json" --out "$PRIVATE/analysis"
"$ENGINE/.venv/bin/ahas" verify --input "$PRIVATE/projection/records.jsonl" \
  --manifest "$PRIVATE/projection/snapshot.json" --analysis-dir "$PRIVATE/analysis" --recompute
```

Use the analyzer's existing `scripts/offline_exec.py` wrapper when enforcing
kernel-level network denial, as done in the private integration. A zero-record
projection can be valid; insufficient data remains an ordinary analysis outcome.
No sample guards are relaxed. Existing destinations are refused. Invalid input
returns exit 2; valid evidence with quarantined observations returns exit 0 and
explicit counts. Invalid AHAS loader chronology or resource limits fail the whole
projection before its destination is published locally.

The optional `--selection` JSON accepts exactly `selection_for(source_id)` from
`bridge.projection`: version, source ID, source-local account key, declared
non-temporal scope and as-of policy. It provides a reproducible selection file;
it is not an arbitrary filter or override language.

## Receipt and identity

Source/profile versions and the profile binding algorithm are in each versioned
profile README. Source descriptors bind only the two selected CSV artifacts and
caller declarations. Text fidelity receipts verify every body/title field,
including markers and blanks, using its logical CSV row and column. The original
CSV bytes remain in the unchanged local source, not copied into the AHIF bundle.

Projection identity binds selection, profile and emitted values. Actual manifest
and member-byte hashes remain separate in the receipt. Moving directories,
reordering JSON object keys or changing operational receipt timestamps does not
change analytical identity. A transport byte change can still change the receipt.
Evidence equality deliberately ignores only documented capture positions;
it never substitutes text equality for a native record key.

Receipts contain identifying keys/locators and may contain exact output values.
Treat them, the bundle, source-account aliases and full analysis reports as
private. Operational paths/timestamps are outside the receipt payload hash. The
`verify` command recomputes selection/projection and compares outputs through the
actual loader; a self-consistent edited receipt alone does not pass verification.

## Tests and integration runner

```bash
"$PYTHON" scripts/check_bridge.py --engine-root "$ENGINE"
```

This writes **new** evidence under `qa/bridge/`. Existing adoption and standalone
receipts remain unchanged. It runs fictional bridge cases, checks the original
format in a temporary copy, and verifies the actual engine source against the
linked baseline. The original standalone format-only check still skips its one
parent-workspace integration test; new bridge tests directly exercise AHAS.

`scripts/private_integration.py --help` documents the private regression runner.
It requires an existing source, prior inputs, prior conversion receipt, prior
converter file (hashed/read-only) and frozen engine root. Run it under that engine's
`offline_exec.py`. It uses only the matching source and prior direct-input route,
not other studies. It writes exact argv, exits, timings, hashes, fidelity records,
ID substitutions and full reports outside this repository. It does not publish.

## Minimal incoming record and next work

A source row supplies its native string ID and the exact CSV columns; text, date
and parent can be blank/uncertain. The enclosing source binds bytes and an explicit
subject declaration. AHIF adds required structural fields with honest unknowns.
Raw evidence, native accounts, account profiles, language, edit state, source
verification and completeness claims are not invented requirements.

For useful prose analysis, a separately versioned profile needs defensible source
lifecycle/as-of and completeness evidence, explicit language provenance where
available, and tested markup/attribution handling. The current evidence already
stores these unknowns coherently. No core AHIF revision is justified by this run.
