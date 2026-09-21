# Unified v3.0.2: authentication Re-sign repair candidate

Status: review candidate, not a device-tested release. Do not treat parser or
isolated guard tests as an iOS build or as proof of safe self-replacement.

Base builder: v3.0.2 / 35c6c28c98e7261afe6049a133a9ae542d666d57.
Embedded SideStore: ff25922e5c13ccfafd83bda5092910d848ebd409.

## Problem and implementation

The Unified resolveResign handler returns the user's Boolean choice but does
not start installation. The caller calls that choice didResign and finishes
authentication. The candidate records the choice, returns false (no resign has
occurred yet), skips the redundant post-auth prompt, and starts host repair
after SignInOperation.execute returns. A failed repair therefore propagates
to the auth session instead of being swallowed by validateCodeSign.

The existing AppManager.resign API accepts optional supplied pipeline handler
and context. Its original callers keep their original behavior. The repair
uses headless prompts in the same authentication sheet, keeps the RefreshGroup
for cancellation, and reports completion only after the native callback.
Host replacement can terminate the process before that callback; a disconnect
must not be interpreted as success. No persistent post-relaunch attestation is
implemented in this candidate.

Only this explicit repair context uses the active certificate rather than the
certificate serial remembered on InstalledApp. The current active host bundle
is staged instead of a possibly stale app cache. Ordinary refresh stays
profile-only. There is no additional app-detail button in this candidate.

## Preconditions and checks

- InstalledApp must be the active host, with its effective ID and team matching
  the running host's provisioning profile and current account.
- Active certificate must be unexpired, exportable as P12, and listed by the
  portal for that team; no certificate creation or revocation is added.
- Team and active serial are checked again during execution.
- Host and extension bundle IDs, application identifiers, team entitlements,
  Keychain groups and App Groups must remain identical. Extension removal
  prompts are rejected during repair.
- All embedded app pipelines share an exclusive host-repair gate, including
  scheduled refresh. Service mutations are blocked during the active auth
  task, except session responses and cancellation.
- Generated output is checked before packaging/sending and again immediately
  before installation. Strict checks may refuse a valid but unusual setup;
  do not weaken them to force installation.

## Build

Apply the accompanying patch at the builder repository root, on a branch
created from v3.0.2. The existing LiveContainer embedded SideStore build
workflow now applies scripts/patch_v3_host_resign.py twice after the other
source-generation adapters. The second invocation checks replay integrity.

Run the workflow on that branch. Download LiveContainer-SideStore-AutoRefresh-IPA.
The output still needs device signing; CI intentionally disables Apple signing.
Keep the pinned source revisions. Do not run this patch before the other
adapters or rerun the older manifest-based adapters after applying it.

## Validation still required

1. Full pinned Xcode 26.4 build and existing repository/packaging checks.
2. Review the final generated source, including actor/sendability checks and
   actual SideSign API compatibility (parser checks do not cover these).
3. On a backed-up test device: same-team in-place upgrade, data/pairing
   preservation, old-versus-active certificate mismatch repair, cancellation,
   session interruption, and scheduled-refresh contention.
4. After relaunch, verify the actual installed host profile and executable
   signing identity; a changed expiration date alone is insufficient.

The .sidestorebackup account export is not a full application data or pairing
backup. Installation with the saved signing identity remains a separate step;
this patch does not provide a signing/installer tool or decrypt that backup.
