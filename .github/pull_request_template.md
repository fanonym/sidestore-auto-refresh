## What changed

Describe the focused change and why it is needed.

## Verification

- [ ] `python -m unittest discover -s tests -v`
- [ ] `git diff --check`
- [ ] Patch scripts remain idempotent
- [ ] No pairing files, private keys, Apple credentials, signed personal IPAs, unnecessary device identifiers, or private logs are included

### CI evidence

Describe what was verified by build/tests.

### Real-device evidence

Device / iOS version and what was actually verified on-device, if applicable.

## Proof level

For 3.0.2.1, report Shortcuts refresh separately from the unused internal LC
Auto-refresh scheduler, and confirm the signing lifetime on LC Home. Use the
configuration and matrix in `docs/RELEASE_NOTES_v3.0.2.1.md`.

For historical native background-refresh changes, distinguish between:

- registration (`REGISTER_PASS`)
- accepted scheduling (`SCHEDULE_PASS`)
- actual scheduled execution (`TRIGGER`)
- completed refresh (`COMPLETE success=true`)

Do not describe scheduled PC-free refresh as proven unless the criteria in `docs/VERIFICATION.md` are satisfied.
