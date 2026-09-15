# Account History Interchange Format (AHIF)

A versioned evidence format for supplied account-history records. **The reviewed contract is draft 0.1.1.** It preserves logical events separately from repeated observations, attributed text parts, uncertain timestamps, source provenance and coverage limitations.

This standalone repository contains the format specification, machine-readable schemas, fictional examples, offline checker, validation tests and review receipts. It does not collect data or convert AHIF into analysis input. AHAS 1.0.4 requires a later explicit projection; its engine and private evidence are not included here.

## Contract

- [Specification](docs/ahif/0.1.1/SPEC.md) and [field dictionary](docs/ahif/0.1.1/FIELDS.md)
- [Record](docs/ahif/0.1.1/schemas/record.schema.json), [manifest](docs/ahif/0.1.1/schemas/manifest.schema.json), [account](docs/ahif/0.1.1/schemas/account.schema.json) and [shared definitions](docs/ahif/0.1.1/schemas/ahif.schema.json)
- [Adoption report](docs/ahif/0.1.1/ADOPTION.md), [changes and open issues](docs/ahif/0.1.1/CHANGES.md), [case matrix](docs/ahif/0.1.1/REVIEW_MATRIX.md)
- [Future AHAS projection map and refusal rules](docs/ahif/0.1.1/AHAS_COMPATIBILITY.md)
- [Fictional examples](docs/ahif/0.1.1/examples) and [negative test fixtures](docs/ahif/0.1.1/fixtures/negative-cases.json)

A minimal bundle has only `manifest.json` and `records.jsonl`. Unknown author, timestamp, language or completeness can remain unknown. Raw evidence and account profile observations are optional. Repeated observations do not create additional posting events, and equal text does not merge separate events.

## Validate a bundle

Use Python 3.12 and install the pinned reference dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python docs/ahif/0.1.1/reference/validate_bundle.py docs/ahif/0.1.1/examples/review-cases --canonical
```

Omit `--canonical` to permit the documented noncanonical transport representations. Validation is offline after dependency installation. The checker is for small, stable, already-extracted fixture directories; it is not a production untrusted-ingestion service and establishes neither authenticity nor completeness.

## Run standalone tests

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_contract.py
```

This runs 60 format tests and explicitly skips the one original AHAS integration test that requires the parent analyzer workspace. It also validates six canonical bundles, verifies the preserved package checksums and checks byte-identical schema/example regeneration. Fresh standalone results are written to [qa/standalone-verification.json](qa/standalone-verification.json) and [qa/standalone-tests.log](qa/standalone-tests.log).

## Historical evidence and packaging

The entire reviewed `docs/ahif/` tree was copied byte-for-byte, including the original 0.1.0 proposal and its receipts. The original 61-test adoption result belongs to the AHAS workspace and is preserved as historical evidence; it is not presented as a standalone integration result. The original `reference/run_checks.py` and commands in the preserved adoption README require that workspace. Use `scripts/check_contract.py` here.

The [standalone source inventory](qa/source-inventory.json) binds every copied file. Historical documents and handoff prompts are records of the proposal/review, not new instructions or external-action authorizations. No record semantics, hash domains, examples or versioned schemas were changed during packaging. No private account exports, credentials, source-account mappings, studies or AHAS engine files are included.
