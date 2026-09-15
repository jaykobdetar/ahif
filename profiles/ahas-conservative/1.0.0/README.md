# AHAS conservative export projection 1.0.0

This implements the metadata-only subset of the frozen 0.1.1 compatibility map.
It does not broaden the historical design document's text eligibility. An
ordinary snapshot selects exactly one source descriptor and its export subject.
All observations (including optional account observations) receive a decision.
Unknown actors, other sources/accounts and account-profile rows are excluded;
unknown identity continuity is never resolved by matching a handle. Eligible
records group by the full native key, not text or observation ID. The equivalence
and conflict rules in `profile.json` retain alternative observations in AHIF.
A competing actor claim for the same key in the selected source quarantines that key, rather than disappearing through the actor filter. No temporal, kind or text sampling option is hidden in this version.

The only projected rows have unavailable content, no retained parts and lifecycle
deleted/removed/unknown/restricted. They become deleted/removed/unavailable with
null text/title. Visible unavailable content also becomes unavailable, retaining
the visibility discrepancy in field losses. Retained text with nonvisible
lifecycle refuses `lifecycle_content_unrepresentable`; visible retained content
refuses `text_projection_unsupported`. Partial/redacted/ambiguous content stays
in evidence. No bypass flag or implicit archive-as-of policy is provided.

Created/edit timestamps use the frozen map; coarse timestamps map null with an
explicit non-temporal omission. Edit state is exact; loader chronology rejection
fails the whole output. Community, permalink and resolved parent/thread aliases
are mapped when compatible. Unsupported metadata is omitted explicitly. Links,
metrics, parts and provenance never enter prose. Every AHAS target field and every
AHIF top-level field has a receipt disposition. Full source values remain bound
by the input bundle inventory and observation IDs. These receipts are private.

Projection uses the installed AHAS **1.0.4**, its actual schemas, loader and default
configuration. Receipt binds installed contract hashes, implementation/config
identities, expanded records/manifest and canonical snapshot digest. It fails on
wrong engine version, schema/loader failure, identity collision or input limits.
No configuration override is accepted. Engine source is never copied or patched.

Input canonical manifest identity is separate from actual member-byte hashes.
Relocation and object-key serialization order do not change analytical identity.
Changing selection/profile or emitted analytical values does. Operational receipt
`executed_at`/paths live outside the projection payload hash. They cannot serve as
source timestamps. Receipt verification reruns the projection and compares the
payload, outputs and actual loader digest, not just the receipt's own hash.

This is a bounded offline helper for trusted local files, using the fixture-oriented
AHIF checker. It is not a hostile multi-user ingestion service. No race-proof
filesystem access, archive authenticity, source verification, authorship accuracy
or completeness certification is claimed. More complete source evidence and a
separately versioned/tested text profile are necessary for prose analysis.

## Profile binding

The profile digest is SHA-256 of canonical `{profile: <parsed profile.json>,
readme_sha256: <SHA-256 of README.md bytes>, receipt_schema_sha256: <SHA-256 of
canonical parsed receipt.schema.json>}`. Canonicalization uses the frozen AHIF
restricted JSON serializer, without a final LF. Policy prose and receipt schema
changes therefore change the profile binding. Release revisions require a new
version; implementation development receipts are retained separately.
