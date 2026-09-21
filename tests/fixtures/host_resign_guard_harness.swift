// Minimal value/API doubles for executing the real identity guard on macOS.
import Foundation
enum OperationError: Error { case invalidParameters(String) }
struct Team { var identifier: String }
struct X509 { var expiryDate = Date.distantFuture }
struct Certificate { var x509 = X509(); var serialNumber: String }
struct ActiveCertificate { var certificate: Certificate; var password: String? = nil
    var serialNumber: String { certificate.serialNumber }
}
final class AuthManager { static let shared = AuthManager(); var team: Team? = Team(identifier: "TEAM") }
final class CertificateManager {
    static let shared = CertificateManager()
    var activeCertificate: ActiveCertificate? = ActiveCertificate(certificate: Certificate(serialNumber: "NEW"))
    static func convert(_ cert: Certificate, password: String?) throws -> Data { Data([1]) }
}
enum StoreApp { static let altstoreAppID = "host.logical" }
extension Bundle { enum Info { static let activeBundleURL = URL(fileURLWithPath: "/host.app") } }
struct Profile { var teamIdentifier = "TEAM"; var bundleIdentifier = "host.TEAM"
    var certificates = [Certificate(serialNumber: "NEW")]
}
final class ALTApplication {
    static var source: ALTApplication!
    var fileURL = Bundle.Info.activeBundleURL
    var bundleIdentifier = "host.TEAM"
    var provisioningProfile: Profile? = Profile()
    var appExtensions: [ALTApplication] = []
    var entitlements: [String: Any] = ["application-identifier": "TEAM.host.TEAM",
        "com.apple.developer.team-identifier": "TEAM", "keychain-access-groups": ["TEAM.shared"],
        "com.apple.security.application-groups": ["group.host"]]
    init() {}
    convenience init?(fileURL: URL) {
        guard let source = Self.source else { return nil }
        self.init()
        self.fileURL = source.fileURL; bundleIdentifier = source.bundleIdentifier
        provisioningProfile = source.provisioningProfile; appExtensions = source.appExtensions
        entitlements = source.entitlements
    }
}
final class InstalledApp {
    var isActive = true; var bundleIdentifier = StoreApp.altstoreAppID
    var resignedBundleIdentifier = "host.TEAM"; var customBundleIdentifier: String?
    var team: Team? = Team(identifier: "TEAM")
}

// INSERT_REAL_GUARD

@MainActor func runChecks() throws {
    func rejected(_ label: String, _ work: () throws -> Void) {
        do { try work(); fatalError("Expected rejection: \(label)") } catch {}
    }
    ALTApplication.source = ALTApplication()
    let installed = InstalledApp()
    let identity = try V3HostResignIdentity(app: installed)
    let result = ALTApplication()
    try identity.validate(result)
    result.entitlements["keychain-access-groups"] = ["TEAM.other"]
    rejected("keychain change") { try identity.validate(result) }
    result.entitlements = ALTApplication.source.entitlements
    result.provisioningProfile?.teamIdentifier = "OTHER"
    rejected("team change") { try identity.validate(result) }
    result.provisioningProfile = Profile()
    result.provisioningProfile?.certificates = [Certificate(serialNumber: "OLD")]
    rejected("old signing identity") { try identity.validate(result) }
    result.provisioningProfile = Profile()
    let extensionApp = ALTApplication(); extensionApp.bundleIdentifier = "host.TEAM.extra"
    result.appExtensions = [extensionApp]
    rejected("extension added") { try identity.validate(result) }
    installed.bundleIdentifier = "guest"
    rejected("guest target") { _ = try V3HostResignIdentity(app: installed) }
    installed.bundleIdentifier = StoreApp.altstoreAppID
    CertificateManager.shared.activeCertificate = nil
    rejected("missing certificate") { _ = try V3HostResignIdentity(app: installed) }
    let gate = V3HostPipelineGate.shared
    try gate.enter(repair: false)
    rejected("repair overlaps ordinary pipeline") { try gate.enter(repair: true) }
    gate.leave(repair: false)
    try gate.enter(repair: true)
    rejected("ordinary overlaps repair") { try gate.enter(repair: false) }
    rejected("second repair") { try gate.enter(repair: true) }
    gate.leave(repair: true)
    try gate.enter(repair: false); gate.leave(repair: false)
    print("Host identity and exclusion checks passed")
}
@main enum GuardChecks {
    @MainActor static func main() throws { try runChecks() }
}
