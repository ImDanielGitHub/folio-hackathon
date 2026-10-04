import Foundation

public enum FinancialScope: String, Codable, CaseIterable, Sendable, Identifiable {
    case everything, personal, business
    public var id: String { rawValue }
    public var title: String { switch self { case .everything: return "Everything"; case .personal: return "Personal"; case .business: return "Aneke Studio" } }
}

public struct Transaction: Codable, Identifiable, Equatable, Sendable {
    public let id: String
    public let date: String
    public let merchant: String
    public let description: String
    public var category: String
    public var purpose: String
    public let amount: Money
    public let account: String
    public var needsReview: Bool
    public var version: Int
    public let sourceID: String
    public var businessPercent: Int?
    public init(id: String, date: String, merchant: String, description: String, category: String, purpose: String, amount: Money, account: String, needsReview: Bool, version: Int, sourceID: String, businessPercent: Int? = nil) {
        self.id = id; self.date = date; self.merchant = merchant; self.description = description; self.category = category; self.purpose = purpose; self.amount = amount; self.account = account; self.needsReview = needsReview; self.version = version; self.sourceID = sourceID; self.businessPercent = businessPercent
    }
    public func matches(scope: FinancialScope) -> Bool {
        scope == .everything || purpose == scope.rawValue || purpose == "mixed"
    }
}

public struct CategoryChange: Codable, Identifiable, Sendable {
    public var id: String { category }
    public let category: String
    public let current: Money
    public let previous: Money
    public let delta: Money
    public let sourceIDs: [String]
}

public struct Calculation: Codable, Identifiable, Sendable {
    public let id: String
    public let title: String
    public let period: String
    public let comparisonPeriod: String
    public let scope: FinancialScope
    public let current: Money
    public let previous: Money
    public let delta: Money
    public let categories: [CategoryChange]
    public let sourceIDs: [String]
    public let assumptions: [String]
}

public struct Goal: Codable, Identifiable, Sendable {
    public let id: String
    public let title: String
    public let category: String
    public let target: Money
    public let current: Money?
    public let scope: FinancialScope
    public let period: String
    public let status: String
    public let calculationID: String?
}

public struct ReviewGroup: Codable, Identifiable, Sendable {
    public let id: String
    public let title: String
    public let reason: String
    public let transactionIDs: [String]
    public let suggestedCategory: String?
    public let version: Int
}

public struct MemoryItem: Codable, Identifiable, Sendable {
    public let id: String
    public let text: String
    public let scope: String
    public let source: String
    public let confirmed: Bool
    public let createdAt: String
}

public struct ActivityReceipt: Codable, Identifiable, Sendable {
    public let id: String
    public let title: String
    public let detail: String
    public let status: String
    public let createdAt: String
    public let affectedIDs: [String]
    public let canUndo: Bool
}

public struct ProviderStatus: Codable, Identifiable, Sendable {
    public var id: String { name }
    public let name: String
    public let environment: String
    public let status: String
    public let detail: String
    public let lastSyncedAt: String?
}

public struct WorkspaceSnapshot: Codable, Sendable {
    public let id: String
    public let name: String
    public let isSynthetic: Bool
    public let asOf: String
    public let transactions: [Transaction]
    public let calculations: [Calculation]
    public let goals: [Goal]
    public let reviewGroups: [ReviewGroup]
    public let memory: [MemoryItem]
    public let activity: [ActivityReceipt]
    public let connections: [ProviderStatus]
}
