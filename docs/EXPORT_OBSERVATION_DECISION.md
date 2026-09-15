# Decision: supplied export-field measurements

Status: new reviewed policy `reddit-export-observation` 1.0.0. This decision
leaves AHIF 0.1.1, AHAS 1.0.4 and `ahas-conservative` 1.0.0 unchanged. Historical
metadata-only receipts remain accurate for their own scope. They did not
demonstrate prose-carrying integration.

## Eight separate claims

| Claim | What can establish it | This projection |
|---|---|---|
| 1. Text exists in a supplied field | Decode the supplied CSV field and identify its locator | Yes where present; blank/sentinel handled explicitly |
| 2. Conversion copied the field faithfully | Independent source→AHIF→AHAS exact string comparison | Checked separately from measurement transformations |
| 3. Field contains the entire original contribution | Source evidence about original object completeness | Unknown stays unknown; no full-body claim |
| 4. Contribution was publicly visible at an instant | Suitable lifecycle/access observation with a known instant | Neither file presence nor import time establishes it |
| 5. Wording existed at original creation time | Historical wording/revision evidence | Creation timestamps order events, not proven wording versions |
| 6. Source attributes record to selected export subject | Explicit account-export subject declaration and source-local scope | Source-account proxy; no cross-capture identity assertion |
| 7. Every word was personally authored by that person | Evidence beyond an export-account association | Not established; explicit parser exclusions and semantic quotation limits remain |
| 8. Language is known | Source language evidence or an explicit scope-bound supplier confirmation | Default `und`; generic measurements still run |

Claims 1 and 2 support measuring supplied evidence. They neither establish
claims 3–8 nor require all those claims to be true first. Useful generic counts
are not claims of complete original prose, personal authorship or public access.

## Frozen AHAS contract review

The actual schemas, loader, feature eligibility, renderer, methods and tests
were inspected together. References below name the frozen AHAS repository:

- `BUILD_SPEC.md:153,163,177,185` describes supplied contents/provenance,
  body availability, present-string/null-status rules and the limits of hashes.
- `schemas/record.schema.json:133` enforces present→string and other statuses→null.
  It has no separate online-lifecycle field.
- `io.py:328–350` checks input/account/time/identity consistency and sentinels;
  no public-visibility or personal-authorship claim is verified.
- `reporting.py:149,166` calls the report supplied account-history measurements
  and the enum supplied text status. `:18` warns that observed wording may
  differ from wording at creation. This supports the new explicit meaning of
  `present` as supplied analytical body availability.
- `features.py:64–88` separates generic usable-text counts from English features;
  `tests/test_text.py:97–103` covers unknown-language counts with English methods
  abstaining. `windows.py:14–18` retains the exact English/time/word guards.
- `activity.py:42–50` counts every distinct timed supplied event, including
  unavailable text. `BUILD_SPEC.md:193` retains missing-time records for text
  and reuse. Text exclusion need not erase an event.
- `text.py:343–345` and `features.py:98–109` measure titles separately even if
  body is unavailable. No empty body is needed to carry a title.
- `BUILD_SPEC.md:258–263` distinguishes explicit quote/code exclusions from an
  impossible guarantee of detecting all semantic quotation or copied wording.

There is no contradiction requiring a new engine/input release for this scope.
The conservative profile's refusal remains a policy boundary, not a universal
claim that supplied text is absent. The new profile intentionally loses
AHIF-only lifecycle/completeness/observation distinctions in AHAS fields and
preserves them in bound evidence/receipts instead of pretending to be lossless.

## Presentation decision

Frozen `pipeline.py:126–127` does not propagate source notes into result snapshot
metadata. It retains coverage notes through `:57`, but `reporting.py:160–171`
does not render them. Both native HTML and Markdown inherit this omission.
Thus manifest notes alone cannot make the projection interpretation visible.

Use a separately versioned interpretation cover, linked to the unchanged
canonical AHAS outputs and hashes. It states the eight-claim limits, parser and
field eligibility policy, body/title/event denominators, all exclusions, and
actual module availability. Do not edit the canonical report after generation.
The cover is an added presentation artifact, not a patched engine renderer.
If only titles are measurable, explain that frozen `pipeline.py:66–67` bases
the text module's overall status on body usability while reporting titles
separately.

## Explicit choices

Unknown or visible lifecycle may carry eligible supplied fields. Known
deleted/removed/restricted records retain metadata events but exclude retained
body and title in version 1.0.0. Any broader archival-text policy needs a later
explicit decision and applicable retention authority.

Unknown original completeness supports measurements of supplied fields. Known
partial, truncated or redacted content is excluded from textual projection;
the event remains. No materially different extraction regime is silently
pooled into a verified-full-body chronology.

Literal strings remain unchanged in AHIF and projected fields. Source body
format `Reddit-export-unknown` and plain title metadata remain unchanged in AHIF.
Both accepted fields receive an explicit tested CommonMark analysis
interpretation because AHAS has one snapshot-wide format. This can alter the
derived meaning of title syntax and is disclosed as policy. Unsupported HTML,
BBCode quote/code/url/img, spoiler and strike spellings refuse affected fields;
the policy is not a universal Reddit dialect recognizer. Native destination
URLs remain metadata, not invented prose.

At most one selected observation represents each logical event. Conflicting
wording/metadata/actor claims remain unresolved, rather than selecting a
convenient revision. Exact repeated wording under distinct keys stays distinct.
Unknown/coarse timestamps remain null in AHAS, with original facts bound in
the receipt. No clock time, English declaration or edit state is manufactured.

## Limits and evidence

This source-level decision is separate from execution evidence. Fresh tests,
real field-fidelity accounting, installed-loader/analyzer results, independent
same-scope direct-input numerical comparison, replay and invariance checks are
recorded by their actual runs. Engineering integration does not establish a
scientific pilot result or real-world detection accuracy. Module execution with
zero findings, insufficient data and unsupported projection are distinct.
