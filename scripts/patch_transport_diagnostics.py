from pathlib import Path
import sys


MARKER = "SIDESTORE_TRANSPORT_DIAGNOSTICS_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label}: expected anchor not found")
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {text.count(old)}")
    return text.replace(old, new, 1)


def patch_common(root: Path) -> None:
    path = root / "Dependencies/minimuxer/Common/MinimuxerCommonLogging.swift"
    text = path.read_text(encoding="utf-8")

    if MARKER not in text:
        anchor = "public enum MinimuxerCommonLogging {"

        block = r'''// SIDESTORE_TRANSPORT_DIAGNOSTICS_V1
public enum TransportDiagnosticBuffer {
    private static let lock = NSLock()
    private nonisolated(unsafe) static var lines: [String] = []
    private nonisolated(unsafe) static var bufferedRunID: String?
    private static let maximumLines = 64
    private static let marker = "[SIDESTORE_COREDEVICE]"
    private static let suiteName = "group.com.SideStore.SideStore"
    private static let runIDKey = "liveContainerAutoRefreshExpectedRunID"
    public static let diagnosticsKey = "liveContainerTransportDiagnostics"

    public static func append(_ message: String) {
        guard message.contains(marker) else { return }

        let normalized = String(
            message
                .replacingOccurrences(of: "\r", with: " ")
                .replacingOccurrences(of: "\n", with: " ")
                .prefix(1024)
        )

        guard let defaults = UserDefaults(suiteName: suiteName),
              let runID = defaults.string(forKey: runIDKey),
              UUID(uuidString: runID) != nil
        else {
            return
        }

        let snapshot: [String] = lock.withLock {
            if bufferedRunID != runID {
                bufferedRunID = runID
                lines.removeAll(keepingCapacity: true)
            }

            lines.append(normalized)

            if lines.count > maximumLines {
                lines.removeFirst(lines.count - maximumLines)
            }

            return lines
        }

        defaults.set(
            [
                "version": 1,
                "run_id": runID,
                "lines": snapshot
            ],
            forKey: diagnosticsKey
        )
    }

    public static func snapshot() -> [String] {
        lock.withLock { lines }
    }

    public static func clear() {
        lock.withLock {
            lines.removeAll(keepingCapacity: true)
            bufferedRunID = nil
        }

        UserDefaults(suiteName: suiteName)?
            .removeObject(forKey: diagnosticsKey)
    }
}

'''

        text = replace_once(
            text,
            anchor,
            block + anchor,
            "MinimuxerCommon diagnostic buffer",
        )

    path.write_text(text, encoding="utf-8")


def patch_minimuxer_logger(root: Path) -> None:
    path = root / "Dependencies/minimuxer/Sources/MinimuxerLogging.swift"
    text = path.read_text(encoding="utf-8")

    if "TransportDiagnosticBuffer.append(message)" not in text:
        old = '''func debugLog(_ text: @autoclosure () -> String) {
    let message = text()
'''
        new = '''func debugLog(_ text: @autoclosure () -> String) {
    let message = text()
    TransportDiagnosticBuffer.append(message)
'''
        text = replace_once(text, old, new, "Minimuxer debugLog")

    if "transportDiagnosticsSnapshot" not in text:
        old = '''    public static func setLogging(_ enabled: Bool) {
        lock.withLock {
            _isLoggingEnabled = enabled
            MinimuxerCommonLogging.setLogging(enabled)
            DeviceGatewayLogging.setLogging(enabled)
        }
    }
'''
        new = '''    public static func setLogging(_ enabled: Bool) {
        lock.withLock {
            _isLoggingEnabled = enabled
            MinimuxerCommonLogging.setLogging(enabled)
            DeviceGatewayLogging.setLogging(enabled)
        }
    }

    public static func transportDiagnosticsSnapshot() -> [String] {
        TransportDiagnosticBuffer.snapshot()
    }

    public static func clearTransportDiagnostics() {
        TransportDiagnosticBuffer.clear()
    }
'''
        text = replace_once(text, old, new, "Minimuxer public diagnostic API")

    path.write_text(text, encoding="utf-8")


def patch_gateway_logger(root: Path) -> None:
    path = root / "Dependencies/minimuxer/DeviceGateway/DeviceGatewayLogging.swift"
    text = path.read_text(encoding="utf-8")

    if "import MinimuxerCommon" not in text:
        if "import Foundation" not in text:
            raise SystemExit("DeviceGatewayLogging.swift: import Foundation anchor not found")
        text = text.replace(
            "import Foundation",
            "import Foundation\nimport MinimuxerCommon",
            1,
        )

    if "TransportDiagnosticBuffer.append(message)" not in text:
        old = '''func debugLog(_ text: @autoclosure () -> String) {
    let message = text()
'''
        new = '''func debugLog(_ text: @autoclosure () -> String) {
    let message = text()
    TransportDiagnosticBuffer.append(message)
'''
        text = replace_once(text, old, new, "DeviceGateway debugLog")

    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: patch_transport_diagnostics.py <EmbeddedSideStore-root>"
        )

    root = Path(sys.argv[1]).resolve()

    patch_common(root)
    patch_minimuxer_logger(root)
    patch_gateway_logger(root)

    print("patched bounded CoreDevice transport diagnostics")


if __name__ == "__main__":
    main()
