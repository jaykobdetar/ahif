# Export-observation integration report

Executed **2026-09-15** using `reddit-export-observation` 1.0.0, unchanged AHIF
0.1.1 and installed AHAS 1.0.4 with its frozen numerical configuration. This is
a bounded offline conversion regression, not a scientific pilot or validation
of identity/authorship detection. No language declaration was supplied.

## Outcome

The path carries real literal source fields into useful existing measurements:
**210 body-bearing events, 10,777 retained body words, and 298 separately measured
title words.** All **247** supplied contributions remain analytical posting events.
Unknown completeness, visibility, observation time, editing and language were
preserved; they were not changed to complete, visible, original-time or English.

The [decision record](EXPORT_OBSERVATION_DECISION.md) explains why AHAS's supplied
text status supports this interpretation. The [profile](../profiles/reddit-export-observation/1.0.0/README.md)
defines its losses and refusals. The [usage guide](EXPORT_OBSERVATION.md) contains
reproducible commands and supported/non-supported boundaries.

## Complete source accounting

The source contains 194 comment rows and 53 submission rows. Each of the 247
rows has one private decision with its logical key, observation ID, CSV locator,
field dispositions, multiple applicable blockers and bound original facts.

| Event accounting | Count |
|---|---:|
| Source observations | 247 |
| Distinct logical contribution keys | 247 |
| Accepted body-bearing events | 210 |
| Body-excluded events retained as metadata | 37 |
| Events excluded entirely | 0 |
| Unresolved conflict events | 0 |
| Equivalent alternative captures in this source | 0 |
| Total projected posting events | 247 |
| Events with separately retained titles | 44 |

The 37 omitted bodies partition into **17 exact source removal markers**, **7
blank source body fields**, **12 bodies containing recognized unsupported BBCode**
and **1 containing unsupported strikethrough**. The 210 admitted bodies comprise
185 comments and 25 submissions. These counts follow the declared rules; no
admission target was used. Sound event metadata remains available for activity.

Nine retained titles belong to removed submissions and are excluded under this
version's explicit nonvisible-writing policy. The other 44 titles remain separate,
including seven title-only submissions and titles whose bodies use unsupported
markup. No empty body was manufactured. No known partial/redacted, unsupported
HTML/spoiler, event identity or timestamp exclusion occurred in this real source;
fictional tests cover those refusals.

Missing metadata also receives reasons: all 247 edit times remain unknown, and
33 comment parent references remain unknown. Such reasons can coexist with an
accepted body. The complete [aggregate blocker counts](../qa/export-observation/integration-aggregate.json)
are **overlapping reasons**, not an additional partition of excluded rows.

## Fidelity and independent comparison

All **300** source fields were independently checked: 247 bodies and 53 titles.
The check compared decoded CSV strings through locators and full logical key
aliases against AHIF, then against analytical inputs wherever retained. It
accounted for blank fields and literal sentinels separately. **254 fields** were
copied literally (210 bodies + 44 titles); **46** were explicitly omitted (17
markers + 7 blank bodies + 13 unsupported bodies + 9 removed-record titles).
Case, punctuation, Unicode and line endings were not rewritten in input fields.
AHAS's derived LF/NFC/markup/token transformations are a separate tested stage.

A separate validation implementation read the original two CSV members directly,
independently constructed all 247 AHAS record fields and applied the same declared
selection, parser and unknown-language regime. It did not copy candidate records
or select rows from projection decisions. Account/experiment identity and snapshot
coverage metadata were deliberately shared after checking their policy settings.
**Every loaded record field, the entire numerical results object, and all 13
checksum-listed canonical artifacts matched.** Both analyses passed ordinary full
recomputation, reproducing 14 files including `checksums.json`.

This is equality on the same supplied-field scope and interpretation. It is not
equality with the historical eight-event comparison, the old full direct-input
snapshot, or any scientific study. The independent baseline is purposefully
limited to this export's exact timestamp layout and unique source IDs; it refuses
other layouts instead of pretending to be a second general converter.

## Module outcomes

| Module | Actual availability and result |
|---|---|
| Coverage | `ok`: 247 unique supplied events; no account-history completeness percentage. |
| Text | `ok`: 210 usable bodies, 10,777 body words; 44 separate titles, 298 title words. Generic counts/rates available with `und`. |
| Activity | `ok`: all 247 distinct events have supplied timestamps. Text exclusions do not narrow this event scope. |
| Reuse | `ok`: three exact groups and two near-match pairs; five descriptive findings (three exact, two shingle-based). These are wording observations, not identity or causal conclusions. |
| Links | `ok`: 44 supplied HTTP(S) occurrences across 28 records; executed malformed/unsafe counts are zero. Native destination metadata is not added to these text-derived statistics. |
| Interactions | `ok`: 161 supplied parent links remain unresolved externally; zero available parent-time differences because parent context is missing. This is unavailable timing, not measured zero latency. |
| English-specific style | `insufficient_data`: zero eligible English records and zero comparisons. Language remains `und`; this is abstention, not an executed negative style finding. |
| AI-text detection | `not_run`, `not_implemented_in_v1`. No classifier added. |

Unsupported projection fields (13 markup bodies and the explicit retention
exclusions) are distinct from module insufficiency and from executed zero counts.
No candidate boundary or high score was required for conversion correctness.

## Executed checks and preservation

- **93 bridge tests passed:** 39 unchanged conservative tests and 54 new tests.
- **61 unchanged format tests passed** in the actual AHAS workspace, with no skips.
- Positive fictional end-to-end analysis/replay produced independently expected
  **30 body words and 3 title words**. Cases cover quotes, inline/fenced code,
  links, autolinks, escaped syntax, headings, hard boundaries and literal Unicode.
- Normalizer output remained identical with mocked operational years 1985 and
  2095. New normalization also reproduced the historical bundle byte-for-byte.
- Relocation, reordered selection properties and changed projection clocks
  preserved payload/analytical identity. Reordering evidence JSON properties
  preserved analytical input bytes while correctly changing raw receipt hashes.
- Both real analyses passed full canonical replay. The context-bearing HTML and
  Markdown derivatives have their own checked hashes; originals remain unchanged.
- Historical conservative projection replay still passed on the unchanged
  historical bundle and receipt. Its eight-event metadata-only result remains
  accurate for that original scope.
- AHIF versioned schemas/examples/history, old profiles/implementation/receipts,
  AHAS engine/input schemas/config/resources and supplied private inputs remain
  unchanged. New runtime inventories bind the implementation used for execution.

Fresh test logs, preservation evidence and sanitized execution aggregates are in
[qa/export-observation](../qa/export-observation). Original receipts were not
overwritten. An earlier successful new-profile run was retained; the final run
adds explicit implementation inventories and confirms the same numerical result.
During fictional test development, one draft expected word count was corrected
before execution and one competing-actor fixture was corrected after AHIF
properly rejected its internally inconsistent attribution. Final executed logs
record the corrected cases; neither was a real-source data correction.

## Private artifacts and presentation

The new private run contains the source-normalized bundles, projection receipts,
all 247 decisions, identity maps, the 300-field fidelity receipt, independent
baseline comparisons, both complete analyses, canonical replay logs, presentation
derivatives, exact executed arguments and a runnable `rerun.sh`. These contain
identifying information and remain outside the repositories. Only aggregate
counts, code, fictional fixtures and nonidentifying test evidence are included here.

Use the context-bearing presentation when reviewing results. It visibly explains
supplied-field availability, unknown completeness/as-of/visibility, source-account
attribution limits, explicit CommonMark interpretation, exclusions and language
abstention. Bare frozen reports omit arbitrary projection notes; adding manifest
notes alone would not meet this presentation requirement.

## Limits and remaining work

The supplied export is not authenticated, and field fidelity does not establish
complete original contributions. Creation-time ordering can contain later edited
wording. The parser's explicit quote/code exclusions cannot identify every unmarked
quotation. No consent, redistribution license, online visibility or permanent
account identity was inferred. The reference tools are bounded offline helpers,
not a production hostile-ingestion service.

Broader dialect support, known-nonvisible archival wording, other sources, verified
full-body comparisons and applicable language declarations require their own
reviewed evidence/policies. Existing generic measurements already work for this
declared source-field regime. No thresholds, penalties, scientific studies or
frozen engine behavior were changed to achieve it.
