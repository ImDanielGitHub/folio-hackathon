import Foundation

// Exact synthetic-demo wire contract. Domain models are separate from server JSON names.
struct DemoWorkspaceDTO: Decodable {
    let id: String
    let kind: String
    let displayName: String
    let version: Int
    let transactions: [DemoTransactionDTO]
    let goals: [DemoGoalDTO]
    let memory: [DemoMemoryDTO]
    let activities: [DemoActivityDTO]
    let model: DemoModelDTO
}
struct DemoTransactionDTO: Decodable {
    let id: String, date: String, merchant: String, description: String, currency: String, category: String, purpose: String, status: String, accountId: String, sourceId: String
    let amountMinor: Int64
    let version: Int
    let businessPercent: Int
    let recurring: Bool
    var domain: Transaction {
        Transaction(id: id, date: date, merchant: merchant, description: description, category: category, purpose: purpose == "split" ? "mixed" : purpose, amount: Money(minorUnits: amountMinor, currency: currency), account: accountId == "demo-everyday" ? "Everyday · Demo" : accountId, needsReview: status == "needs_review", version: version, sourceID: sourceId, businessPercent: businessPercent)
    }
}
struct DemoGoalDTO: Decodable {
    let id: String, title: String, currency: String, scope: String, period: String, status: String
    let limitMinor: Int64
    let spentMinor: Int64?
    let progressNote: String?
    var domain: Goal {
        Goal(id: id, title: title, category: title, target: Money(minorUnits: limitMinor, currency: currency), current: progressNote?.contains("No October") == true ? nil : spentMinor.map { Money(minorUnits: $0, currency: currency) }, scope: FinancialScope(rawValue: scope) ?? .personal, period: period, status: status, calculationID: nil)
    }
}
struct DemoMemoryDTO: Decodable {
    let id: String, text: String, status: String, source: String, createdAt: String
    let scope: [String]
    var domain: MemoryItem { MemoryItem(id: id, text: text, scope: "\(scope.count) specific transaction(s)", source: source, confirmed: status == "confirmed", createdAt: createdAt) }
}
struct DemoActivityDTO: Decodable {
    let id: String, label: String, status: String, createdAt: String, source: String
    let undoable: Bool
    let affectedIds: [String]
    func domain(canUndo: Bool) -> ActivityReceipt {
        ActivityReceipt(id: id, title: label, detail: source, status: status, createdAt: createdAt, affectedIDs: affectedIds, canUndo: undoable && canUndo)
    }
}
struct DemoModelDTO: Decodable { let state: String, provider: String, model: String }
struct DemoComparisonDTO: Decodable {
    let calculationId: String, currency: String, scope: String, previousPeriod: String, currentPeriod: String
    let previousMinor: Int64?, currentMinor: Int64?, differenceMinor: Int64?
    let rows: [DemoCategoryDTO]
    let sourceIds: [String]
    var domain: Calculation? {
        guard let before = previousMinor, let after = currentMinor, let delta = differenceMinor, let scope = FinancialScope(rawValue: scope) else { return nil }
        return Calculation(id: calculationId, title: "September compared with August", period: currentPeriod, comparisonPeriod: previousPeriod, scope: scope, current: Money(minorUnits: after, currency: currency), previous: Money(minorUnits: before, currency: currency), delta: Money(minorUnits: delta, currency: currency), categories: rows.map { $0.domain(currency: currency) }, sourceIDs: sourceIds, assumptions: ["Synthetic fixture, July–September 2026.", "Currency: \(currency). Transfer treatment is owned by the calculation service.", "Personal and business amounts use confirmed allocations."])
    }
}
struct DemoCategoryDTO: Decodable {
    let category: String
    let previousMinor: Int64, currentMinor: Int64, differenceMinor: Int64
    let transactionIds: [String]
    func domain(currency: String) -> CategoryChange {
        CategoryChange(category: category, current: Money(minorUnits: currentMinor, currency: currency), previous: Money(minorUnits: previousMinor, currency: currency), delta: Money(minorUnits: differenceMinor, currency: currency), sourceIDs: transactionIds)
    }
}
struct DemoAskDTO: Decodable {
    let runId: String
    let status: String
    let answer: String?
    let surface: DemoComparisonDTO?
    let receipt: DemoRunReceiptDTO?
}
struct DemoRunReceiptDTO: Decodable {
    let provider: String?
    let model: String?
    let stages: [String]?
    let inferenceVerified: Bool?
}
struct DemoActionPayload: Encodable {
    var ids: [String]? = nil
    var purpose: String? = nil
    var remember: Bool? = nil
    var id: String? = nil
    var businessPercent: Int? = nil
    var limitMinor: Int64? = nil
}
struct DemoActionRequest: Encodable { let operationId: String; let expectedVersion: Int; let type: String; let payload: DemoActionPayload }
struct DemoAskRequest: Encodable { let operationId: String; let expectedVersion: Int; let question: String; let scope: String }
