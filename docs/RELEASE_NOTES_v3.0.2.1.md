# Stable baseline 3.0.2.1

This release freezes the deployment owner's verified iPad setup. It reuses the
existing successful build; closure changes documentation, its configuration test,
and the release dispatch guard only. Application and network code stay unchanged.

## Immutable build identity

| Component | Pin / identity |
| --- | --- |
| IPA builder commit | `b9590618dac5a791d2faffa9365d00bbfaa50776` |
| GitHub Actions build | [36748073104](https://github.com/fanonym/sidestore-auto-refresh/actions/runs/36748073104) |
| Embedded SideStore | `ff25922e5c13ccfafd83bda5092910d848ebd409` |
| minimuxer | `98c3c79982f813878e922ab42f9545314a700f0c` |
| idevice | `61c27041f8d3d0be4cc3e046ee04501649c9d66e` |
| JKTCP | `0.1.6`, pinned commit `e674e1eee6d5943e13b1eba0bd24a9dd0b2fa020` |
| LiveContainer | `12377cf3b91d51739a33f14a302e5f522b238593` |
| SideSign | `a731c0d5a9a6617c7b385ae493e07ffb7f81cd5d` |
| IPA SHA-256 | `95539dfa2d409d8c7a20cefb44be01116ce31c24df3b40d7dae0cf92f739c2c7` |

Release audit independently downloaded the IPA from this run and matched its
SHA-256 to the value above. The artifact builder-commit record also matches.
The original CI repository suite recorded **190 tests, OK (1 skipped)**.

The release/documentation commit is a descendant of the IPA builder commit;
it must not be described as the commit that compiled this unchanged binary.
The release tag identifies the frozen source plus documentation.

## Recommended deployment

- **RPP-only pairing**.
- LocalDevVPN **Tunnel `10.7.0.1` / Device-Peer `10.7.0.2`**.
- **Use Local VPN ON**; **Remote Pairing Port Override `0`**.
- SideInstaller DNS: **Automatic** is suitable for normal operation.
- Internal LC Auto-refresh: **OFF / unused / not recommended for this deployment**.
- True Hairpin and CoreDevice/`62078`: **historical/experimental**, not the
  recommended route. Existing implementations are retained without modification.

## Recommended Refresh via Shortcuts

1. Optionally disconnect the specific active external VPN.
2. Disable LocalDevVPN.
3. Wait 2 seconds.
4. Enable LocalDevVPN.
5. Wait 10 seconds.
6. Run **Refresh All Apps**.
7. Wait 10 seconds.
8. Disable LocalDevVPN.

Automation: **Time of Day, Daily, Run Immediately, Show When Run OFF**;
notifications optional. LocalDevVPN is needed only during the refresh window.
Restore WireGuard/CyberGhost manually as needed. See the
[README workflow](../README.md#recommended-refresh-via-shortcuts).

Path: `Shortcuts -> Refresh All Apps -> RPPairing -> RSD -> provisioning/profile install -> REFRESH_VERIFIED`.
Check signing lifetime on **LC Home**. LC logs do not populate in this deployment;
a shortcut launch alone is not proof of refresh.

## Device test matrix

These results were reported by the deployment owner for this exact baseline;
they are not new device tests performed during documentation closure.

| Scenario | Result |
| --- | --- |
| Home Wi-Fi | PASS |
| Wi-Fi 2 | PASS |
| Mobile hotspot (iPad connected over Wi-Fi) | PASS |
| Sleep/wake | PASS |
| Shortcuts refresh | PASS |

This evidence does not establish cellular-only operation, internal LC scheduler
reliability, universal account/device compatibility, or completion of unrelated
historical issue acceptance checklists. Exact iPad model/OS are not recorded in
this closure request; do not infer them from older iPhone evidence.

## Release-closure checks

- Existing IPA downloaded and SHA-256 matched; ZIP integrity passed.
- Local repository suite: **191 tests, OK (24 skipped)**. Skips require additional
  pinned LiveContainer/standalone upstream checkouts not available in this run.
- Swift test cache used a writable temporary directory. Embedded SideStore and
  minimuxer tests used clean temporary exports of the pinned commits, with matching
  SideSign source and Git metadata; existing prepared checkouts were left intact.
- Whitespace/diff checks, changed YAML syntax and local Markdown link targets passed.
- No Xcode application build or GitHub Actions build was started.
- Release dispatch excludes `release/3.0.2.1` so publishing this closure cannot
  automatically dispatch the standalone build. Other release branches retain their behavior.
- Security and third-party license documents were reviewed and require no changes.

## Preservation and publication

Keep the existing installation, account, pairing and app data. No reset,
reinstallation or new build is required by this documentation closure. Preserve
this build's IPA and matching evidence; never substitute another run's artifact.
Release branch: `release/3.0.2.1`, fork: `fanonym/sidestore-auto-refresh`.
Use the existing `v` tag convention (`v3.0.2.1`) for a release titled `3.0.2.1`;
never move or overwrite an existing tag without explicit approval.
No 3.0.2.2 branch or release is part of this work.
