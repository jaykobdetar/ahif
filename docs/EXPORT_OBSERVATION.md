# Offline source-field analysis

`reddit-export-observation` **1.0.0** is a separately reviewed projection into
the unchanged AHAS 1.0.4 engine and its input schemas 1.0.0. AHIF remains draft
0.1.1. The original `ahas-conservative` 1.0.0 profile remains metadata-only.

Read the [decision record](EXPORT_OBSERVATION_DECISION.md),
[profile contract](../profiles/reddit-export-observation/1.0.0/README.md),
[machine-readable policy](../profiles/reddit-export-observation/1.0.0/profile.json),
[receipt schema](../profiles/reddit-export-observation/1.0.0/receipt.schema.json),
and [executed integration report](EXPORT_OBSERVATION_REPORT.md).

## Supported scope

- One supplied local Reddit export subject, the reviewed two-member CSV layout,
  and unchanged observations from `reddit-export-csv` 1.0.0.
- Literal retained source body/title strings. Unknown completeness permits
  **source-field measurements**, not verified full-contribution length claims.
- A declared CommonMark **analysis interpretation** using the frozen parser.
  Source dialect and AHIF format labels are not rewritten. Titles receive the
  same declared interpretation in their separate field.
- Unknown public visibility, capture/as-of time, edit state and language remain
  unknown. `status=present` describes supplied analytical body availability.
- At most one observation per logical contribution. Equivalent captures collapse;
  competing wording or attribution remains unresolved. Matching text at different
  contribution IDs does not merge events.
- Metadata events can remain in activity when body text is excluded. Titles never
  become fabricated empty bodies. Per-field blockers and losses remain auditable.

Known partial/truncated/redacted text, unsupported field ownership/format, and
recognized HTML, BBCode, spoiler and strikethrough spellings are excluded from
this text regime. Known removed/deleted/restricted writing, including retained
titles, is excluded by this version's explicit retention policy. No claim about
its current online state is substituted. Ordinary unmarked copying cannot all
be detected; parser exclusion is not personal-authorship verification.

There is no arbitrary Reddit dialect renderer, source authentication, permission
inference, native destination link projection, cross-capture identity resolver,
live collector, other-platform converter, database, classifier or new pilot.
Source-use and retention constraints apply independently of technical support.

## Small incoming contract

The normalizer still needs only the reviewed contribution CSV members and an
explicit declaration that the export is for the selected subject. A new projection
consumes the validated AHIF manifest/observations plus its exact source-local
selection. No author identifier, language, completeness, original wording,
public visibility or observation timestamp is fabricated to make text eligible.

Optional language declarations use a separate [schema](../profiles/reddit-export-observation/1.0.0/language-declaration.schema.json).
They bind the source, account key and explicit observation IDs, with supplier
confirmation and a statement of basis. Omit the declaration if none was provided.
An old account-level English claim is not an applicable declaration for a new run.

## Run focused tests

Use Python 3.12 with the existing pinned AHAS 1.0.4 environment and bridge test
dependencies. From this repository (the examples below place the analyzer at
`$AHAS_ROOT`):

```bash
PYTHONDONTWRITEBYTECODE=1 "$AHAS_ROOT/.venv/bin/python" -m pytest \
  -p no:cacheprovider tests/bridge tests/observation -q
```

The fictional suite includes a complete analysis/replay, hand-enumerated parser
counts, quote/code/link boundaries, Unicode/line endings, title-only rows,
unknown/coarse times, conflicts, repeated captures, identical separate events,
language declarations and refusals. Original format tests and receipts are
preserved; fresh execution belongs under `qa/export-observation/`.

## Project an existing bundle

After normalizing using the existing [source CLI](BRIDGE.md), retain its selection
JSON and run from the AHIF checkout:

```bash
"$AHAS_ROOT/.venv/bin/python" -m bridge.export_observation project \
  --bundle "$PRIVATE/bundle" --selection "$PRIVATE/selection.json" \
  --out "$PRIVATE/observation-projection"
"$AHAS_ROOT/.venv/bin/python" -m bridge.export_observation verify \
  --bundle "$PRIVATE/bundle" --projection "$PRIVATE/observation-projection"
"$AHAS_ROOT/.venv/bin/python" scripts/verify_observation_fidelity.py \
  --source "$SOURCE_EXPORT" --bundle "$PRIVATE/bundle" \
  --projection "$PRIVATE/observation-projection" \
  --out "$PRIVATE/private-field-fidelity.json"
```

Every output destination must be new. These local reference tools are for bounded,
already supplied files, not production hostile ingestion. The fidelity checker
reads only the two whitelisted CSV members and compares every body/title field,
including markers and blank fields. Raw source copying is checked separately from
AHAS's documented derived normalization, tokenization and exclusions.

## Reproduce the supplied-export regression

The regression runner normalizes twice, compares the historical unchanged bundle,
replays the old conservative receipt, projects under changed operational clocks,
changes JSON property order, independently constructs direct AHAS records from CSV,
compares all analytical record fields, analyzes both identical scopes, performs
full canonical replay, and compares every canonical artifact. It emits a separate
presentation with visible interpretation limits, a private fidelity receipt and
a safe aggregate summary. It refuses to write evidence within either repository.

```bash
"$AHAS_ROOT/.venv/bin/python" "$AHAS_ROOT/scripts/offline_exec.py" \
  "$AHAS_ROOT/.venv/bin/python" scripts/private_observation_integration.py \
  --source "$SOURCE_EXPORT" \
  --existing-bundle "$PRIOR_PRIVATE/bundle-a" \
  --existing-conservative "$PRIOR_PRIVATE/projection-a" \
  --engine-root "$AHAS_ROOT" --out "$NEW_PRIVATE_RUN"
```

These variables identify local private inputs, not published datasets. Exact
executed absolute arguments are in the private execution receipt and rerun file.
The direct baseline is intentionally a bounded independent check of this supplied
layout; unsupported dates or duplicate source IDs stop that baseline instead of
inventing a conflict resolution. The general projection tests cover those cases.
Snapshot experiment identity/coverage are deliberately shared for comparison;
record fields are independently derived. No numerical equality is claimed with
the previous eight-event subset or an old full-history report.

## Present and verify results

The engine's canonical reports remain untouched. Its renderer does not show
arbitrary `source_notes` or coverage notes, so those fields alone are inadequate.
The runner emits `presentation/report.html` and `report.md` with prominent context
and a deterministic presentation receipt. This derivative is explicitly **not**
the canonical AHAS report. Verify the original `analysis-projected` directory with
the usual `ahas verify --recompute`; check the derivative against its own receipt.

For separate workflows, use `bridge.observation_presentation.present()` with a
context bound to the verified projection payload, explicit counts, language policy,
chronology policy and limitations. Do not present the bare engine report as the
complete reviewed observation-profile presentation.

## Identity and reproducibility

Relocation and operational clock values do not change normalized bytes, analytical
inputs or projection payload identity. JSON object property order may change raw
file hashes and therefore the evidence-bound receipt payload. It must not change
observation IDs or the analytical snapshot. These are different invariance claims.
The source ID binds exact CSV bytes; altered CSV transport creates a different
source-local capture identity even when decoded strings agree.

## Changes and open issues

This adds one projection profile, an optional scope-bound declaration, an
independent validation baseline, fidelity checking and a context-bearing report
derivative. It changes no AHIF schema, old projection rule, numerical method,
threshold, detector penalty, historical receipt or prior study.

Remaining work includes reviewed handling of other source dialects, explicit
archival-text retention policy for known nonvisible writing, independent source
verification, separately authorized language declarations and production input
hardening. These are not prerequisites for the documented generic measurements
of eligible supplied fields. A full-body comparison would require separate
evidence of completeness; current field-copy fidelity does not provide it.
