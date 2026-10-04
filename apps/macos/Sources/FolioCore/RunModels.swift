import Foundation

public struct ConversationMessage: Identifiable, Sendable {
    public enum Role: String, Codable, Sendable { case user, assistant }
    public let id: String
    public let role: Role
    public let text: String
    public let calculationIDs: [String]
    public init(id: String = UUID().uuidString, role: Role, text: String, calculationIDs: [String] = []) {
        self.id = id; self.role = role; self.text = text; self.calculationIDs = calculationIDs
    }
}

public struct RunResult: Codable, Sendable {
    public let id: String
    public let text: String
    public let status: String
    public let stages: [String]
    public let calculationIDs: [String]
    public let provider: String
    public let model: String?
    public let inferenceVerified: Bool
}

public struct GoalDraft: Codable, Sendable {
    public var title: String
    public var category: String
    public var targetMinorUnits: Int64
    public var currency: String
    public var scope: FinancialScope
    public var period: String
    public init(title: String, category: String, targetMinorUnits: Int64, currency: String = "NZD", scope: FinancialScope = .personal, period: String = "monthly") {
        self.title = title; self.category = category; self.targetMinorUnits = targetMinorUnits; self.currency = currency; self.scope = scope; self.period = period
    }
}

public struct AnnotationChange: Codable, Sendable {
    public var transactionIDs: [String]
    public var expectedVersions: [String: Int]
    public var category: String?
    public var purpose: String?
    public var businessPercent: Int?
    public var rememberRule: Bool
    public init(transactionIDs: [String], expectedVersions: [String: Int], category: String? = nil, purpose: String? = nil, businessPercent: Int? = nil, rememberRule: Bool = false) {
        self.transactionIDs = transactionIDs; self.expectedVersions = expectedVersions; self.category = category; self.purpose = purpose; self.businessPercent = businessPercent; self.rememberRule = rememberRule
    }
}

public enum FolioServiceError: LocalizedError {
    case notConfigured, invalidURL, unauthorised, staleWrite, unavailable(String), malformedResponse, unsupported(String)
    public var errorDescription: String? {
        switch self {
        case .notConfigured: return "Connect to your Folio server to open a workspace."
        case .invalidURL: return "Use an HTTPS server address, or localhost for local development."
        case .unauthorised: return "Your session has expired. Open a new demo workspace."
        case .staleWrite: return "These items changed elsewhere. Refresh and review them again before applying."
        case .unavailable(let detail): return detail
        case .malformedResponse: return "The server returned an unexpected response. Your existing view has been kept."
        case .unsupported(let detail): return detail
        }
    }
}

public protocol FolioService: Sendable {
    func createDemo() async throws -> WorkspaceSnapshot
    func refresh(workspaceID: String, scope: FinancialScope) async throws -> WorkspaceSnapshot
    func ask(_ text: String, workspaceID: String, scope: FinancialScope, transactionIDs: [String]) async throws -> RunResult
    func annotate(_ change: AnnotationChange, workspaceID: String) async throws -> ActivityReceipt
    func saveGoal(_ draft: GoalDraft, workspaceID: String) async throws -> Goal
    func forgetMemory(id: String, workspaceID: String) async throws -> ActivityReceipt
    func undo(receiptID: String, workspaceID: String) async throws -> ActivityReceipt
    func resetDemo(workspaceID: String) async throws -> WorkspaceSnapshot
}
