# Bridge 1.0.0 — changes, rationale and open issues

This is the first local implementation release candidate. No AHIF 0.1.0/0.1.1
schema, frozen example, historical receipt, AHAS source/configuration or prior
study was edited. The versioned adoption documents retain their original
future-work statements. New claims live in `BRIDGE.md` and `BRIDGE_REPORT.md`.

## Adopted implementation decisions

| Change | Why |
|---|---|
| Add observed-layout Reddit CSV source profile 1.0.0 | Real input has two specific contribution tables, bare string IDs, native title/body columns and explicit UTC spelling. This is not a universal Reddit export promise. |
| Require caller `export_subject` or `unknown` declaration | The CSV has no native author ID. A source-local subject records supplied export context without deriving a permanent account from a filename. |
| Preserve exact body/title field strings and locators | CSV decoding must retain punctuation, case, Unicode composition, quotes, code, CRLF and embedded newlines. Every original body/title is checked, including blanks and sentinels; unexpected extra normalized text parts are rejected. |
| Keep exact sentinel interpretation separate from authored parts | The prior route used exact `[removed]`/`[deleted]` markers. The new profile declares that convention and retains marker literals. Whitespace-surrounded strings are not silently stripped or interpreted. |
| Retain unknown lifecycle/completeness/language/edit state | Retained text does not establish current visibility or textual completeness. A missing edit field is not false; English-looking wording is not a language declaration. |
| Use `other` + `Reddit-export-unknown` for body markup | AHIF has no generic `markdown` enum. The first fixture check caught an invalid enum in new code; using the existing `other` branch avoids claiming CommonMark compatibility or changing the format. |
| Map the actual short native thread-link route | The first private comparison found that `link` uses `/r/COMMUNITY/comments/POST`, without a slug. The rule now accepts that observed route and checks agreement with the permalink. A targeted test covers it. |
| Resolve parent collection only with a supported thread root | An unrecognized or conflicting thread locator cannot silently establish a bare parent ID's collection. Missing targets remain references, not invented rows. |
| Add metadata-only conservative projection 1.0.0 | The frozen compatibility policy refuses nonvisible/unknown lifecycle with retained text. Eight real removed comments fit; 239 observations remain evidence with explicit refusals. |
| Separate event keys, observations and account scope | Repeated captures never inflate the timeline; same text at different native IDs remains distinct. Source-local/handle matching never proves continuity. |
| Ignore only named capture positions for equivalence | Observation/capture locators may vary without a new event. Actor, text, lifecycle, time, revision and remaining evidence must agree. Any unresolved disagreement quarantines the selected key. Competing same-source actor claims also quarantine. |
| Bind policy prose and receipt schema in profile digests | Policy changes must affect provenance. Profiles hash their parsed JSON plus README digest, and projection also binds its receipt schema digest. |
| Bind exact input files separately from analytical identity | Moving directories, changing operational timestamps or JSON property order must not invent analytical changes. Actual byte changes still remain detectable in the receipt. |
| Verify actual loader output and full recomputation | Schema-only success is insufficient. The implementation uses AHAS 1.0.4's real defaults, input guards, chronology checks and normal verification. |
| Compare the same narrow prior-input subset | Prior bare IDs/account alias and inherited `und` are explicitly substituted. All resulting record fields and complete numerical results agree in the matched scope. The old full reports are not claimed identical. |

## Execution history

The private integration keeps three separate destinations. Attempt 01 failed
before analysis when the old route's parent reference exposed the missing short
thread-link rule. Attempt 02 passed after the mapping correction. Attempt 03 is
the final successful run after profile binding documentation was finalized.
Earlier destinations and their receipts were retained. New final test receipts
are in `qa/bridge/`; original draft and packaging receipts are unchanged.

## Open issues / unsupported work

- The supplied export lacks the evidence needed by this conservative contract for
  retained-prose analysis. A separately reviewed archive/as-of policy or richer
  supplied evidence is needed; there is no `force present` flag.
- Reddit's body dialect and embedded attribution require a separately versioned,
  tested text projection. This implementation neither segments quotations nor
  certifies original authorship of text in a contribution field.
- Source authenticity, marker meaning in an adversarial/fabricated file, consent,
  licensing, missingness and lifetime completeness are not proven by hashes.
- Changing export layouts need new source-profile versions. No native stable
  account ID or cross-capture reconciliation is inferred.
- The helper is bounded and offline but has not been hardened for concurrent,
  hostile ingestion. It inherits the reference checker's documented filesystem
  and resource limitations. Raw inclusion is not implemented here.
- Reproducibility was demonstrated in the pinned Linux/Python environment; no
  cross-platform numerical guarantee or scientific accuracy claim is made.

The real source fits AHIF's existing unknown/other/partial representations.
**No core format contradiction was found, and no AHIF schema revision is proposed.**
