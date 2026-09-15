# Export-observation execution evidence

These files record the completed 2026-09-15 local engineering validation:

- `combined-tests.log`: 93 bridge tests (39 original conservative + 54 new).
- `format-tests.log`: 61 unchanged format tests in the AHAS workspace, no skips.
- `projection-tests.log`: the 31 focused projection tests, including fictional
  prose analysis and full canonical replay.
- `conservative-tests.log`: the unchanged 39-test conservative suite.
- `integration-aggregate.json`: nonidentifying counts and outcomes from the
  private source-field regression.
- `verification.json`: exact tested file hashes, preserved-file inventory and
  validation outcomes.

`verification.json` describes publication status **at its recorded execution
time**, before the later request to commit and push this work. Its `committed`
and `pushed` values remain historical and are not live repository status. The
receipt and its logs were preserved rather than rewritten for publication.
Before publication, all listed tested-file and preserved-file hashes were
checked again against the working tree; implementation bytes had not changed.

The [integration report](../../docs/EXPORT_OBSERVATION_REPORT.md) explains the
counts, exclusions, module availability and limits. Full source prose, account
maps, identifying receipts, baseline records and reports remain private outside
the repository. No new private analysis or scientific pilot was run to publish
this update.
