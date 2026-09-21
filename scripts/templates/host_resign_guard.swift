// Host-only identity checks for the Unified authentication repair path.
// This is compiled into embedded SideStore, never the host UI process.
struct V3HostResignIdentity {
    let bundleID: String
    let teamID: String
    let serial: String
    let sourceURL: URL
    let bundles: [String: [String: Any]]

    @MainActor
    init(app: InstalledApp) throws {
        guard app.isActive, app.bundleIdentifier == StoreApp.altstoreAppID,
              let team = AuthManager.shared.team,
              let active = CertificateManager.shared.activeCertificate,
              active.certificate.x509.expiryDate > Date(),
              let source = ALTApplication(fileURL: Bundle.Info.activeBundleURL),
              let profile = source.provisioningProfile,
              profile.teamIdentifier == team.identifier,
              app.resignedBundleIdentifier == source.bundleIdentifier,
              app.customBundleIdentifier == nil || app.customBundleIdentifier == source.bundleIdentifier,
              app.team?.identifier == team.identifier else {
            throw OperationError.invalidParameters("Host, team, bundle ID or active certificate is unavailable or mismatched.")
        }
        // Exporting a P12 must succeed before any installation work begins.
        _ = try CertificateManager.convert(active.certificate, password: active.password)
        bundleID = source.bundleIdentifier
        teamID = team.identifier
        serial = active.serialNumber
        sourceURL = source.fileURL
        bundles = try Self.identities(source)
    }

    func checkActiveIdentity() throws {
        guard AuthManager.shared.team?.identifier == teamID,
              CertificateManager.shared.activeCertificate?.serialNumber == serial else {
            throw OperationError.invalidParameters("Signing identity changed during host repair.")
        }
    }

    func validate(_ app: ALTApplication) throws {
        try checkActiveIdentity()
        guard app.bundleIdentifier == bundleID,
              let profile = app.provisioningProfile,
              profile.teamIdentifier == teamID,
              profile.certificates.contains(where: { $0.serialNumber == serial }) else {
            throw OperationError.invalidParameters("Re-signed host does not preserve the required identity.")
        }
        let actual = try Self.identities(app)
        for bundle in [app] + Array(app.appExtensions) {
            guard let profile = bundle.provisioningProfile,
                  profile.teamIdentifier == teamID,
                  profile.bundleIdentifier == bundle.bundleIdentifier,
                  profile.certificates.contains(where: { $0.serialNumber == serial }) else {
                throw OperationError.invalidParameters("Host or extension provisioning identity changed.")
            }
        }
        guard Set(actual.keys) == Set(bundles.keys) else {
            throw OperationError.invalidParameters("Host repair changed the embedded extension identities.")
        }
        for (id, expected) in bundles {
            guard let observed = actual[id], NSDictionary(dictionary: expected).isEqual(to: observed) else {
                throw OperationError.invalidParameters("Host repair changed data-access entitlements for \(id).")
            }
        }
    }

    private static func identities(_ app: ALTApplication) throws -> [String: [String: Any]] {
        // Compare actual executable entitlements, not just the allowed profile values.
        let protected = Set(["application-identifier", "com.apple.developer.team-identifier",
                             "keychain-access-groups", "com.apple.security.application-groups"])
        var result: [String: [String: Any]] = [:]
        for bundle in [app] + Array(app.appExtensions) {
            guard result[bundle.bundleIdentifier] == nil else {
                throw OperationError.invalidParameters("Duplicate host extension identity.")
            }
            var values: [String: Any] = [:]
            for (key, value) in bundle.entitlements where protected.contains(key) {
                // Group order is not semantically significant.
                if let strings = value as? [String] { values[key] = strings.sorted() }
                else { values[key] = value }
            }
            guard values["application-identifier"] != nil,
                  values["com.apple.developer.team-identifier"] != nil else {
                throw OperationError.invalidParameters("Cannot read host signing entitlements.")
            }
            result[bundle.bundleIdentifier] = values
        }
        return result
    }
}

// All embedded app pipelines share this gate. Ordinary operations may coexist;
// host replacement must be exclusive, including scheduled background refresh.
final class V3HostPipelineGate: @unchecked Sendable {
    static let shared = V3HostPipelineGate()
    private let lock = NSLock()
    private var count = 0
    private var repairing = false

    func enter(repair: Bool) throws {
        try lock.withLock {
            guard !repairing, !repair || count == 0 else {
                throw OperationError.invalidParameters("Another app operation is running.")
            }
            count += 1
            if repair { repairing = true }
        }
    }

    func leave(repair: Bool) {
        lock.withLock {
            count -= 1
            if repair { repairing = false }
        }
    }
}

extension V3AuthCenter {
    // Run after SignInOperation returns: errors here cannot be swallowed by
    // validateCodeSign's legacy resolveResign error handler.
    func repairHost(id: String, context: StandaloneOperationContext) async throws {
        try Task.checkCancellation()
        guard !AppManager.shared.isActivelyManagingAnyApp,
              let app = InstalledApp.fetchAltStore(in: DatabaseManager.shared.viewContext) else {
            throw OperationError.invalidParameters("Host is unavailable or another app operation is running.")
        }
        context.v3HostResignIdentity = try V3HostResignIdentity(app: app)
        guard let team = AuthManager.shared.team, let identity = context.v3HostResignIdentity else {
            throw OperationError.invalidParameters("Active host identity is missing.")
        }
        let certificates = try await DeveloperPortalProxy.shared.fetchCertificates(team: team)
        guard certificates.contains(where: { $0.serialNumber == identity.serial }) else {
            throw OperationError.invalidParameters("Active signing certificate is not present on the selected team's portal.")
        }
        try identity.checkActiveIdentity()
        let handler = V3HeadlessPipelineHandler(sessionID: id, authRepair: true)
        try await withTaskCancellationHandler(operation: {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                let gate = V3ServiceCallbackGate(continuation)
                let group = AppManager.shared.resign(app, alternateIconMode: .preserve,
                    presentingViewController: nil, handler: handler, context: context) { result in
                    gate.settle(result.map { _ in () })
                }
                sessions[id]?.group = group
                if Task.isCancelled { group.cancel() }
            }
        }, onCancel: {
            Task { @MainActor in self.sessions[id]?.group?.cancel() }
        })
        try Task.checkCancellation()
    }
}
