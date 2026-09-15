# Reddit export-observation projection 1.0.0

This is a new, deliberately lossy projection from frozen `reddit-export-csv`
1.0.0 / AHIF 0.1.1 into AHAS 1.0.4 input schema 1.0.0. It does not replace
`ahas-conservative` 1.0.0. The old profile, inputs and receipts stay historical.

## Meaning and exact scope

`status=present` means that a nonempty literal body field is supplied for this
analytical snapshot. It does not mean that the website publicly displayed it at
creation, capture or analysis time. Unknown lifecycle, visibility, content-as-of,
edit state and original-object completeness remain unchanged in AHIF and bound
in the receipt. These are measurements of supplied fields under a declared
parser interpretation, not verified-full-body or original-time comparisons.

One selected source must declare `reddit-export-csv` 1.0.0 and its source-local
`export_subject`. That proxy attributes records to the export subject; it does
not prove identity, consent, platform authenticity, or that a person personally
wrote every word. No handle or account is joined across sources. Selection is
non-temporal and has no common website as-of instant.

Full logical record keys define events independently of wording. For equivalent
observations use the frozen equivalence rule and lexicographically smallest
observation ID, retaining every alternative decision. Disagreements, including
competing actor claims or differing language declarations on otherwise
equivalent captures, remain unresolved conflicts. There is no newest-wins or
manual resolution. Equal text under distinct keys remains distinct events.

## Field admission and measured scope

Body: exactly one `body` source-field part, attributed `record_actor`, whose
format is `other` / `Reddit-export-unknown` or explicitly `commonmark`. Title:
exactly one separate `title` source-field part on a submission, format `plain`.
Both must have nonempty literal strings within the frozen AHAS limits. The
original content must be present, with completeness `unknown` or `complete`.
Unknown completeness never becomes complete. Mixed/unsupported structured
parts refuse textual projection for the record rather than being concatenated.

Known `deleted`, `removed`, or `restricted` lifecycle excludes both body and
title in this version, even if wording is retained. Partial/truncated/redacted
content, non-source-field fidelity, nonselected attribution, unsupported field
formats and recognized unsupported markup exclude affected fields. Multiple
blockers are recorded. Source metadata and ordinary eligible posting events are
retained: unavailable text does not erase activity. Empty exported fields do not
prove an originally empty body. Title-only uses `text:null,status:unavailable`
with the independently eligible title; it never invents `text:""`.

All accepted literal fields use the **frozen AHAS CommonMark analysis policy**.
This includes titles because the AHAS manifest has only one `text_format`.
A plain source title remains plain in AHIF; selecting a Markdown interpretation
for its analysis is an explicit, potentially lossy policy rather than a claim
about its original dialect. No source characters are rewritten in output.
Blockquotes, code, links, escaped syntax, headings and exclusion boundaries are
covered by fictional end-to-end tests. HTML tags/comments, BBCode
quote/code/url/img, Reddit spoilers and strike syntax matching the published
patterns are unsupported. Other Reddit-specific differences are not claimed
equivalent to CommonMark. Unmarked quotations cannot all be detected; AHAS's
existing retained-prose limitations apply. No personal-authorship claim follows.

AHAS makes its own derived LF/NFC/whitespace/markup transformations. Those are
not field-copy transformations. Retained token and code-point counts, generic
case/punctuation rates, reuse, source links and activity can be useful without
known language or full original-object completeness. They describe the selected
source-field regime, and must not be pooled as verified-full-body measurements.

## Optional language declaration

Absent a declaration, retained source-part tags are used only when compatible;
unknown or mixed tags use `und`. English is never inferred from the website,
prose, past snapshot, or account. A separate declaration requires its own
version, exact source ID, account key, sorted unique observation IDs, language,
`basis:"supplier_confirmation"` and the actual supplied statement. It applies
to both projected fields of those observations. The caller must possess that
explicit confirmation; generating a declaration is not confirmation.
It changes the projection identity, not AHIF observations. The receipt embeds
the declaration and its domain-separated canonical digest. Its schema digest is
bound by `profile.json`. No applicable declaration is assumed for real inputs.

## Metadata and refusal

Unknown/date-only/interval or unsupported precision timestamps map to null with
loss reasons. Creation timestamps never date the wording. Metadata ambiguity
omits the affected parent/community/thread/reference field with a reason. An
internal parent-after-child reference is omitted while both source event times
remain unchanged. Missing parents do not create records. Unsupported event
keys/kinds or selected-actor failures exclude events; conflicts remain distinct
from ordinary exclusion. Every observation has a decision and original-fact
inventory. Native destination links are receipt-only and never appended to text.

All emitted inputs pass the actual installed AHAS 1.0.4 schemas and loader with
unchanged defaults. A loader failure aborts publication of the local output
directory. The helper is trusted-fixture/offline integration code, not an
untrusted multi-tenant ingestion service; concurrency races are out of scope.

## Counts, identity and replay

`source_observations` counts supplied contribution observations, excluding
account profiles. `distinct_events` counts full logical keys. `projected_events`
includes metadata-only events. `text_bearing_events` counts nonnull bodies;
`text_excluded_events` counts projected null bodies, including title-only events.
`title_bearing_events` counts nonnull separate titles and may overlap either.
`event_excluded_events` and `unresolved_conflict_events` count distinct keys with
no output. These three event categories sum to `distinct_events`.
`equivalent_capture_observations` counts retained alternatives, never events.

Decision `accepted` means a body was admitted; `text_excluded` means the body
was omitted while its event remains, even when a separate title was admitted.
`event_excluded`, `unresolved_conflict` and `equivalent_capture` have their literal
meanings. Field dispositions separately state body/title admission and blockers.
Missing optional fields/time reasons are also recorded on accepted events; a
nonempty blocker list does not imply that the whole event was refused.

The snapshot identity uses its own versioned domain and binds profile digest,
selection, explicit language declaration, emitted records and snapshot metadata.
Record aliases retain the frozen full-key domain; they never hash only prose.
Operational paths and execution clocks are excluded. Raw source-byte hashes
remain source identities: changed CSV transport bytes can change source-local
IDs even if decoded strings agree. JSON property-order-only changes preserve
analytical identities, but raw manifest/file receipt hashes can change. The
receipt payload binds both raw inventory and canonical manifest identity, so
its digest deliberately changes with raw input bytes. Replay requires the
recorded environment/configuration, and does not assert universal byte identity.

## Required presentation and operation

AHAS's frozen report labels these as supplied-text statuses, but does not display
`source_notes` or `coverage.notes`. A separately versioned interpretation cover
must visibly accompany the canonical report and bind its hashes, receipt and
profile. It must state the observational interpretation, completeness/as-of and
attribution limits, parser policy, exclusions, and module availability. Merely
inserting notes into the manifest does not satisfy this requirement. The frozen
engine reports overall text insufficiency for title-only snapshots despite
separate title counts; the cover must explain that case if present.

The receipt and aliases can identify an account. Keep real prose, source-account
maps, receipts and outputs private. No rights/license/consent/source verification
is inferred. Follow applicable retention/source-use rules independently of
technical field admission. This profile does not authorize collection or
publication.

```sh
python -m bridge.export_observation project --bundle BUNDLE --out OUTPUT --selection SELECTION.json
python -m bridge.export_observation verify --bundle BUNDLE --projection OUTPUT
```

An explicitly confirmed declaration may be added with
`--language-declaration DECLARATION.json`. These commands create new outputs and
never overwrite prior bundles or historical receipts.
