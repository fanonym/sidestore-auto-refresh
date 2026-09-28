from pathlib import Path
import sys

UI_MARKER = "SIDESTORE_TRANSPORT_DIAGNOSTICS_UI_V1"
CLEAR_MARKER = "SIDESTORE_TRANSPORT_DIAGNOSTICS_CLEAR_V1"

DIAGNOSTICS_KEY = "liveContainerTransportDiagnostics"


def patch_refresh_view(root: Path) -> bool:
    path = (
        root
        / "LiveContainerSwiftUI/Views/Settings/"
          "LCEmbeddedSideStoreRefreshView.swift"
    )

    text = path.read_text(encoding="utf-8")
    changed = False

    # Upgrade an already patched older diagnostics UI.
    old_guard = (
        '                                   '
        'lastError.contains("correlation=\\(diagnosticRunID)"),\n'
    )

    if old_guard in text:
        text = text.replace(old_guard, "", 1)
        changed = True

    old_output = (
        '                                    '
        'copied += "\\n\\nTransport diagnostics:\\n"\n'
        '                                    '
        'copied += lines.joined(separator: "\\n")'
    )

    new_output = (
        '                                    '
        'copied += "\\n\\nTransport diagnostics:"\n'
        '                                    '
        'copied += "\\nrun_id=\\(diagnosticRunID)"\n'
        '                                    '
        'copied += "\\n"\n'
        '                                    '
        'copied += lines.joined(separator: "\\n")'
    )

    if old_output in text:
        text = text.replace(old_output, new_output, 1)
        changed = True

    # Fresh, not-yet-patched generated view.
    if UI_MARKER not in text:
        anchor = "UIPasteboard.general.string = lastError"

        if anchor not in text:
            raise SystemExit(
                f"{path}: Copy Refresh Diagnostics anchor not found"
            )

        replacement = (
            f"// {UI_MARKER}\n"
            "                                var copied = lastError\n"
            '                                if let defaults = '
            'UserDefaults(suiteName: "group.com.SideStore.SideStore"),\n'
            '                                   let diagnostics = '
            f'defaults.dictionary(forKey: "{DIAGNOSTICS_KEY}"),\n'
            '                                   let diagnosticRunID = '
            'diagnostics["run_id"] as? String,\n'
            '                                   let lines = '
            'diagnostics["lines"] as? [String],\n'
            "                                   !lines.isEmpty {\n"
            '                                    copied += '
            '"\\n\\nTransport diagnostics:"\n'
            '                                    copied += '
            '"\\nrun_id=\\(diagnosticRunID)"\n'
            '                                    copied += "\\n"\n'
            '                                    copied += '
            'lines.joined(separator: "\\n")\n'
            "                                }\n"
            "                                UIPasteboard.general.string = copied"
        )

        text = text.replace(anchor, replacement, 1)
        changed = True

    # Verify that an old UI variant cannot silently survive.
    if 'lastError.contains("correlation=\\(diagnosticRunID)")' in text:
        raise SystemExit(
            f"{path}: obsolete correlation/run_id coupling remains"
        )

    if UI_MARKER in text and 'copied += "\\nrun_id=\\(diagnosticRunID)"' not in text:
        raise SystemExit(
            f"{path}: diagnostics UI marker exists but run_id output is missing"
        )

    if changed:
        path.write_text(text, encoding="utf-8")

    return changed


def patch_app_delegate(root: Path) -> bool:
    path = root / "LiveContainerSwiftUI/App/AppDelegate.swift"
    text = path.read_text(encoding="utf-8")

    if CLEAR_MARKER in text:
        return False

    # Exact anchor from LiveContainerAutoRefreshScheduler.beginRun().
    anchor = (
        "        defaults.set(id.uuidString, forKey: expectedRunKey)\n"
    )

    if text.count(anchor) != 1:
        raise SystemExit(
            f"{path}: expected exactly one expectedRunKey beginRun anchor; "
            f"found {text.count(anchor)}"
        )

    replacement = (
        anchor
        + f"        // {CLEAR_MARKER}\n"
        + "        defaults.removeObject("
          'forKey: "liveContainerTransportDiagnostics")\n'
    )

    text = text.replace(anchor, replacement, 1)
    path.write_text(text, encoding="utf-8")
    return True


def verify(root: Path) -> None:
    view = (
        root
        / "LiveContainerSwiftUI/Views/Settings/"
          "LCEmbeddedSideStoreRefreshView.swift"
    ).read_text(encoding="utf-8")

    delegate = (
        root / "LiveContainerSwiftUI/App/AppDelegate.swift"
    ).read_text(encoding="utf-8")

    required_view = [
        UI_MARKER,
        'diagnostics["run_id"] as? String',
        'copied += "\\nrun_id=\\(diagnosticRunID)"',
        DIAGNOSTICS_KEY,
    ]

    for value in required_view:
        if value not in view:
            raise SystemExit(
                f"refresh view verification failed: missing {value}"
            )

    if 'lastError.contains("correlation=\\(diagnosticRunID)")' in view:
        raise SystemExit(
            "refresh view verification failed: obsolete correlation guard"
        )

    if delegate.count(CLEAR_MARKER) != 1:
        raise SystemExit(
            "AppDelegate verification failed: cleanup marker count != 1"
        )

    expected_cleanup = (
        "defaults.set(id.uuidString, forKey: expectedRunKey)\n"
        f"        // {CLEAR_MARKER}\n"
        "        defaults.removeObject("
        'forKey: "liveContainerTransportDiagnostics")'
    )

    if expected_cleanup not in delegate:
        raise SystemExit(
            "AppDelegate verification failed: diagnostics cleanup "
            "is not immediately after expectedRunKey assignment"
        )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: patch_transport_diagnostics_ui.py <LiveContainer-root>"
        )

    root = Path(sys.argv[1]).resolve()

    changed = []

    if patch_refresh_view(root):
        changed.append("refresh diagnostics UI")

    if patch_app_delegate(root):
        changed.append("refresh diagnostics lifecycle")

    verify(root)

    if changed:
        print("patched transport diagnostics:")
        for item in changed:
            print(f"  {item}")
    else:
        print("transport diagnostics UI/lifecycle already patched")

    print("transport diagnostics verification: OK")


if __name__ == "__main__":
    main()
