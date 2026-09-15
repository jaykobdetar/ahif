# Offline Reddit bridge — adoption and execution report

**Implementation:** source normalizer and source profile 1.0.0, conservative
projection/receipt 1.0.0, CLI, fixtures and tests. AHIF remains **0.1.1**; AHAS
remains **1.0.4**, with input schemas **1.0.0** and unchanged numerical defaults.
This report records local implementation and validation before repository publication.
Publication is separate from the executions recorded below.

## Actual private integration

| Result | Observed outcome |
|---|---:|
| Source contribution files | 194 comments + 53 posts |
| Canonically valid AHIF observations / distinct supplied native keys | 247 / 247 |
| Body/title fields checked at original CSV locators | 300 |
| Selected AHAS records | 8 removed comments, metadata only |
| Quarantined observations | 239 (`lifecycle_content_unrepresentable`) |
| Usable projected body text | None |
| Prior subset comparison | All record fields equal after declared substitutions |
| Numerical comparison | Complete `results.json` equal in the matched scope |
| Normal AHAS recomputation | 14 canonical artifacts reproduced |

The original two CSV hashes matched the preserved direct-input conversion receipt.
All input/prior-route files checked before and after execution remained unchanged.
The prior converter was read and hashed, not rerun. No Pilot 3–6 account data was
ingested or analyzed. Source-category classification was `user_supplied`; unknown
language stayed `und`. No account-level English declaration was transferred.

The frozen lifecycle rule is decisive: this export retains text but supplies no
explicit visible/as-of state. The nine removed posts also retain titles and are
therefore refused. The other eight removal markers contain no retained text and
fit the metadata-only map. Valid evidence and valid AHAS input do not imply enough
text for analysis. AHAS reported `insufficient_data` for **text, reuse and style**;
activity, coverage, interactions and links completed. AI detection remained
`not_run`. No thresholds or sample guards were changed.

Repeated normalization produced identical canonical bundle bytes. Relocation and
selection JSON key ordering left projection payload and output bytes identical;
operational timestamps/paths remained outside analytical identity. Fictional tests
also changed manifest JSON property order and the operational clock explicitly.

The comparison used the same eight logical events from the preserved prior
unknown-language route. It retained original body/title/time/edit/parent values,
replaced bare IDs/account aliases with the declared AHIF aliases, and made inherited
`und` explicit. Snapshot metadata was fixed to the same narrowed scope. The full
old history and its reports were **not** claimed byte-identical. Exact substitutions,
source identities, commands, exits and reports remain in the private receipt.

## Actual validation

- **39 bridge tests passed** in [tests.log](../qa/bridge/tests.log), including literal
  Unicode/CRLF/code/quote fidelity, missing parents, huge string IDs, date uncertainty,
  source/handle identity scope, repeats, conflicts, actor disputes, unsupported
  content, invalid sources, receipt tampering and direct-AHIF refusal by AHAS.
- **60 format tests passed; one historical parent-dependent test was explicitly
  skipped** in a temporary copy. The new bridge suite directly exercises actual
  AHAS schemas and loader. Six canonical original bundles and regeneration passed.
- **92 preserved contract files** remained byte-identical to the standalone inventory.
- **70 engine/config/schema/resource files** matched linked analyzer commit
  `6f465bd95fa3c12df41235986a96a04cf6c332d0`.
- All **11 final integration commands exited 0** under the existing Linux seccomp
  network-denial wrapper. The unchanged `ahas analyze` and `ahas verify --recompute`
  commands used default configuration. The extra prior-subset analysis was a
  regression comparison of the same input scope, not a pilot or parameter study.

[Machine-readable validation](../qa/bridge/verification.json) and the
[sanitized integration summary](../qa/bridge/private-integration-summary.json)
record actual environment, profile bindings, engine/configuration hashes, command
exits and limits. Two additional final-code checks reverified all source text fields and replayed the projection successfully. Historical receipts were not overwritten. The final profile
bindings were exercised in private integration attempt 03; earlier attempts remain
separate, as described in the [change log](BRIDGE_CHANGES.md).

For reproducible command syntax and the supported/non-supported contracts, see
[BRIDGE.md](BRIDGE.md). The private execution receipt contains exact real argv;
public documentation deliberately uses path variables.

## What an incoming record needs

The source supplies its native string ID and exact CSV fields. Body/title wording
is preserved when available. Date, parent, language, native account identity,
editing, completeness and verification can remain unknown. The bundle requires
no included raw evidence or account profile file. An explicit export-subject
choice creates only a source-local attribution scope.

Further useful prose analysis requires a separately reviewed source/as-of and
completeness policy plus tested markup/attribution handling. There is no converter
for X, forums or arbitrary HTML, no identity-reconciliation service and no source
verification claim. The observed source exposes an evidence limitation, not an
AHIF contradiction; no core schema change is proposed.
