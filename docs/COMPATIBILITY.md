# Device Compatibility

> **3.0.2.1 deployment:** See [the frozen baseline and test matrix](RELEASE_NOTES_v3.0.2.1.md)
> and [recommended Shortcuts refresh](../README.md#recommended-refresh-via-shortcuts).
> RPP-only pairing is recommended; internal LC Auto-refresh is unused. True Hairpin
> and CoreDevice/62078 are historical/experimental, not this deployment's recommendation.
> Older release evidence and pending issue-specific checks below retain their original scope;
> they neither override the 3.0.2.1 configuration nor gain new PASS results from its refresh tests.

## Current 3.0.2.1 coverage

| Scenario | Deployment-owner result |
| --- | --- |
| Home Wi-Fi | PASS |
| Wi-Fi 2 | PASS |
| Hotspot over Wi-Fi | PASS |
| Sleep/wake | PASS |
| Shortcuts refresh | PASS |

Use fixed Tunnel `10.7.0.1` / Device-Peer `10.7.0.2`, Use Local VPN ON,
Port Override `0`, RPP-only pairing and SideInstaller DNS Automatic.
Check LC Home signing lifetime; internal LC Auto-refresh is unused.
Other devices/OS versions and cellular-only operation are not established by these results.

## Historical CoreDevice coverage

The following records describe older releases only.

The implementation does not hardcode `10.x`, `192.168.x`, or another specific IPv4 range. It derives the LocalDevVPN peer from the active interface and routing table. The LocalDevVPN Tunnel IP and Device IP still need to be configured as unused `/32` addresses inside the iPhone's current Wi-Fi subnet.

## Standalone SideStore proof device

| Device | iOS | LocalDevVPN | Manual Refresh All | Scheduled PC-free refresh |
| --- | --- | --- | --- | --- |
| iPhone 12 | 26.6.1 | Official App Store LocalDevVPN, same-subnet `/32` route | ✅ Verified | ✅ Final proof verified |

## Combined LiveContainer v2.0.0

The combined variant uses the same intended Wi-Fi + official LocalDevVPN
CoreDevice route, but the standalone scheduled-refresh result above is not proof
of the combined host replacement or unattended execution path.

On iPhone 12 / iOS 26.6.1, embedded UI and earlier Return-control interaction were
observed, as were matching refresh results and a newly installed provisioning
profile. Final windowed/fullscreen control visibility, same-PID resume, complete
host replacement, and unattended combined refresh still need device validation.

Published build `f20e14e` passed Release compilation and package checks. No minimum
deployment targets were raised. Other OS/device combinations remain unverified.
Cellular-only refresh is not supported by this release.

## Community compatibility reports

Additional reports are requested for:

- other iPhone and iPad models
- other iOS versions
- `10.x` private Wi-Fi networks
- `192.168.x` private Wi-Fi networks
- `172.16-31.x` private Wi-Fi networks
- unusual router/subnet configurations

Use [Issue #1](https://github.com/NRG-Wardog/sidestore-auto-refresh/issues/1) or the **Device verification** issue template to report a result.

A useful report includes:

- device model
- standalone or combined variant, and installed build/version
- iOS version
- Wi-Fi network family (exact addresses are not required)
- whether official LocalDevVPN remained connected
- whether the same-subnet `/32` route was configured successfully
- manual refresh result
- scheduled PC-free result
- non-sensitive diagnostic markers when available

## Privacy

Do not publish pairing files, certificates, private keys, Apple credentials, signed personal IPAs, unnecessary device identifiers, exact private IP addresses if you do not want to disclose them, or complete private device logs.
