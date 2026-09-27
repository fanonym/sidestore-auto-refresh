# Custom changelog

## 3.7.2.1 — Phase A (baseline preparation)

No custom runtime changes. CoreDevice/RSD, scheduler, signing preflight and UI ports are outside this phase. The existing patch workflows are not used by `phase-a-baseline.yml`.

| Component | Exact baseline |
| --- | --- |
| LiveContainer 3.7.2 | `d62aa328a44c07386a3dcd96a5d9f16231c67047` |
| Embedded SideStore | `d2c0b5f6decbccff9ef28a59851781e37f110a90` |
| Historical SideStore branch | `LiveContainerSupport2` (not today's LiveContainerSupport HEAD) |
| SideSign | Not present in this release; uses AltSign below |
| AltSign | `4819a7984f44c3c9936e74196a88c6576f14c853` |
| minimuxer | `9035aa25ae82c13cac73ecafb85f1aa27a00cf59` |
| idevice | crates.io `0.1.29`; locked checksum `c598466c8dfdd2c6cb03c99f9077236e3141161d88d76d9249529421aef65ac8` |
| idevice crate VCS | `5cf78b306b74763e44168f153cfabadd6ea49ccc`, published with `dirty=true`; crate checksum is authoritative |
| em_proxy | `c151b90652752fe27e294dddaff76b0c20000034` |
| Xcode | 26.2, matching upstream release workflow |

### Release identification

The published [LiveContainer 3.7.2 combined IPA](https://github.com/LiveContainer/LiveContainer/releases/tag/3.7.2) was downloaded and its SHA256 verified against GitHub asset metadata:
`794ec785c30a2f3a02f3757e5cd5978c9871bc0539e332deeb66f15f4aaf4de9`.
Its embedded SideStore Info.plist reports `0.6.3-nightly.2026.02.24.123+d2c0b5f6`. GitHub resolves this to the full SideStore SHA above. This is the reference artifact hash, not the new build hash.

### Build-only adaptations

- Upstream packaging downloaded moving SideStore nightly; use locally built SideStore at the exact historical SHA instead.
- Upstream Rust fetch script downloaded latest prebuilts; build the pinned minimuxer/em_proxy sources with Cargo.lock instead. Historical prebuilt binary provenance cannot be inferred solely from submodule pins.
- The old dylibify URL returns 404. Use its official relocated release 1.0, verified SHA256 `6d23f6a2fc4d8442f87caa1161aebe6ecaafd0e8c41ce205da007efb04fc82c7`.
- Correct packaging-only cleanup paths for strict error checking. No app source patches.
- Preserve app version 3.7.2; 3.7.2.1 identifies this migration baseline artifact.

### Validation

Build pending. GitHub Actions artifact `phase-a-3.7.2.1-baseline` will contain the IPA, SHA256, build logs, recursive submodule SHAs, resolved Swift packages and Cargo lockfiles. No device/runtime verification claimed. Local build unavailable because this Mac has Command Line Tools but no full Xcode.

### Custom changes

None.
