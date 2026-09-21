#!/usr/bin/env python3
"""Repair v3.0.2's no-op authentication Re-sign action on final generated sources.

Apply AFTER the other combined adapters, to fresh pinned embedded sources.
This candidate still requires a complete Xcode build and physical-device QA.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

PIN = "ff25922e5c13ccfafd83bda5092910d848ebd409"
TEMPLATE = Path(__file__).with_name("templates") / "host_resign_guard.swift"


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"host resign: expected one anchor, got {text.count(old)}: {old[:100]!r}")
    return text.replace(old, new, 1)


def patch(root):
    if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() != PIN:
        raise ValueError("host resign: source revision mismatch")
    manifest = root / ".v3-host-resign.json"
    inputs = hashlib.sha256(Path(__file__).read_bytes() + TEMPLATE.read_bytes()).hexdigest()
    if manifest.exists():
        previous = json.loads(manifest.read_text())
        if previous["inputs"] != inputs:
            raise ValueError("host resign: patch changed; use fresh sources")
        for name, digest in previous["files"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"host resign: patched source drifted: {name}")
        return
    changes = {}

    def edit(name, transform):
        changes[name] = transform(changes.get(name, (root / name).read_text()))

    def runtime(s):
        s = once(s, '        var attempts = 0\n',
                 '        var attempts = 0\n        var resignRequested = false\n        var group: RefreshGroup?\n')
        s = once(s, '    private var activeID: String?\n',
                 '    private var activeID: String?\n    var hasActiveSession: Bool { sessions.values.contains { $0.task != nil } }\n')
        s = once(s, '            let result = try await operation.execute()\n',
                 '''            let result = try await operation.execute()
            try Task.checkCancellation()
            if sessions[id]?.resignRequested == true {
                debugLog("[V3_HOST_RESIGN] BEGIN session=\\(id)")
                try await repairHost(id: id, context: context)
                debugLog("[V3_HOST_RESIGN] CALLBACK_SUCCESS session=\\(id)")
            }
            try Task.checkCancellation()
''')
        s = once(s, '        session.task?.cancel()\n        session.watchdog?.cancel()\n        if session.terminal',
                 '        session.task?.cancel()\n        session.group?.cancel()\n        session.watchdog?.cancel()\n        if session.terminal')
        s = once(s, '    func resolvePostAuth() async {\n',
                 '    func resolvePostAuth() async {\n        if V3HeadlessRuntime.shared.auth.sessions[sessionID]?.resignRequested == true { return }\n')
        start = s.index('    func resolveResign(mismatchReason:')
        end = s.index('\n    func complete()', start)
        segment = s[start:end]
        segment = once(segment, '        return answer["choice"] == "proceed"', '''        let requested = answer["choice"] == "proceed"
        V3HeadlessRuntime.shared.auth.sessions[sessionID]?.resignRequested = requested
        // A decision is not a completed re-sign. The auth center executes it
        // after SignInOperation returns and propagates its real result.
        return false''')
        s = s[:start] + segment + s[end:]
        start = s.index('final class V3HeadlessPipelineHandler:')
        prefix, h = s[:start], s[start:]
        h = once(h, '    init(sessionID: String) { self.sessionID = sessionID }',
                 '    let authRepair: Bool\n    init(sessionID: String, authRepair: Bool = false) { self.sessionID = sessionID; self.authRepair = authRepair }')
        h = once(h, '    var isResignActive: Bool { false }', '    var isResignActive: Bool { authRepair }')
        h = once(h, '        let center = try center()\n        let prompt = v3Prompt', '''        if authRepair {
            let auth = V3HeadlessRuntime.shared.auth
            guard auth.sessions[sessionID]?.terminal == nil else { throw CancellationError() }
            let prompt = v3Prompt(kind: kind, title: title, message: message,
                                  fields: fields, options: options, destructive: destructive)
            guard let promptID = prompt["id"] as? String else { throw CancellationError() }
            auth.sessions[sessionID]?.prompt = prompt
            defer { auth.sessions[sessionID]?.prompt = nil }
            return try await V3HeadlessRuntime.shared.prompts.park(promptID: promptID)
        }
        let center = try center()
        let prompt = v3Prompt''')
        h = once(h, '    func resolveBundleIDMismatch(targetID: String, activeEffectiveID: String) async -> Bool {',
                 '    func resolveBundleIDMismatch(targetID: String, activeEffectiveID: String) async -> Bool {\n        if authRepair { return false }')
        h = once(h, '        let sorted = excessExtensions.sorted',
                 '        if authRepair { throw OperationError.invalidParameters("Host repair cannot remove extensions.") }\n        let sorted = excessExtensions.sorted')
        s = prefix + h
        # A command reply releases the ordinary mutation gate before its session
        # finishes. Keep mutating service commands away from the entire auth flow.
        s = once(s, '        let mutation = !V3WireContract.readOperations.contains(operation)', '''        if V3HeadlessRuntime.shared.auth.hasActiveSession,
           !V3WireContract.readOperations.contains(operation),
           !["authRespond", "authCancel", "opCancel", "opAnswer"].contains(operation) {
            reply(encode(["version": 1, "id": id, "error": "busy"]))
            return
        }
        let mutation = !V3WireContract.readOperations.contains(operation)''')
        return s + '\n' + TEMPLATE.read_text()

    edit("AltStore/AppDelegate.swift", runtime)
    edit("SideStore/Core/Operations/OperationContexts.swift", lambda s: once(s,
         'class StandaloneOperationContext: OperationContext\n{',
         'class StandaloneOperationContext: OperationContext\n{\n    var v3HostResignIdentity: V3HostResignIdentity?'))

    def manager(s):
        start = s.index('    func resign(_ installedApp: InstalledApp,')
        end = s.index('\n    func backup(', start)
        segment = s[start:end]
        segment = once(segment, '                presentingViewController: UIViewController?,',
                       '                presentingViewController: UIViewController?,\n                handler: PipelineExecutionHandler? = nil,\n                context suppliedContext: StandaloneOperationContext? = nil,')
        segment = once(segment, 'let pipelineHandler = self.makePipelineHandler', 'let pipelineHandler = handler ?? self.makePipelineHandler')
        segment = once(segment, 'let context = self.makeAuthenticatedContext', 'let context = suppliedContext ?? self.makeAuthenticatedContext')
        return s[:start] + segment + s[end:]
    edit("AltStore/Managing Apps/AppManager.swift", manager)

    def runner(s):
        s = once(s, '        let operations = operations.filter', '''        let repair = group.context.v3HostResignIdentity != nil
        try V3HostPipelineGate.shared.enter(repair: repair)
        defer { V3HostPipelineGate.shared.leave(repair: repair) }
        let operations = operations.filter''')
        s = once(s, '        context.beginInstallationHandler =', '''        if let identity = group.context.v3HostResignIdentity {
            guard case .resign(let host, _) = operation,
                  host.bundleIdentifier == StoreApp.altstoreAppID else {
                throw OperationError.invalidParameters("Host repair only accepts the installed host.")
            }
            try identity.checkActiveIdentity()
            guard let source = ALTApplication(fileURL: identity.sourceURL) else {
                throw OperationError.invalidParameters("Current host bundle cannot be read.")
            }
            context.targetAppBundle = source
            context.customBundleIdentifier = identity.bundleID
            context.useMainProfile = false
        }

        context.beginInstallationHandler =''')
        return s
    edit("SideStore/Core/Operations/PipelineRunner.swift", runner)

    def executor(s):
        s = once(s, '            case .updateAppCertificate:\n', '''            case .updateAppCertificate:
                if let identity = context.standaloneContext.v3HostResignIdentity {
                    try identity.checkActiveIdentity()
                    guard let certificate = context.activeSigningCertificate,
                          certificate.serialNumber == identity.serial else {
                        throw OperationError.invalidParameters("Active host signing certificate changed.")
                    }
                    context.overrideSigningCertificate = certificate
                    return nil
                }
''')
        s = once(s, '                context.resignedAppBundle = resignedAppBundle',
                 '                try context.standaloneContext.v3HostResignIdentity?.validate(resignedAppBundle)\n                context.resignedAppBundle = resignedAppBundle')
        s = once(s, '            case .installApp:\n', '''            case .installApp:
                if let identity = context.standaloneContext.v3HostResignIdentity {
                    guard let bundle = context.resignedAppBundle else { throw OperationError.invalidApp }
                    try identity.validate(bundle)
                }
''')
        return s
    edit("SideStore/Core/Operations/PipelineExecutor.swift", executor)
    # Validate all anchors before writing; preserve hashes for replay checks.
    for name, content in changes.items():
        (root / name).write_text(content)
    manifest.write_text(json.dumps({"inputs": inputs, "files": {
        name: hashlib.sha256(content.encode()).hexdigest() for name, content in changes.items()
    }}, indent=2) + '\n')


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v3_host_resign.py EMBEDDED_SIDESTORE")
    patch(Path(sys.argv[1]).resolve())
