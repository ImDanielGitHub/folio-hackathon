import Foundation
import Observation
import FolioCore

enum Destination: String, CaseIterable, Identifiable {
    case today = "Today", money = "Money", goals = "Goals", opportunities = "Opportunities"
    case review = "Review", transactions = "Transactions", bills = "Bills & subscriptions", activity = "Activity", memory = "Memory", connections = "Connections"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .today: return "sun.max"; case .money: return "chart.bar.xaxis"; case .goals: return "flag"
        case .opportunities: return "sparkle"; case .review: return "checklist"; case .transactions: return "list.bullet.rectangle"
        case .bills: return "calendar"; case .activity: return "clock.arrow.circlepath"; case .memory: return "square.stack"
        case .connections: return "link"
        }
    }
}

@MainActor @Observable
final class FolioStore {
    var destination: Destination = .today
    var scope: FinancialScope = .everything
    var workspace: WorkspaceSnapshot?
    var conversation: [ConversationMessage] = []
    var lastRun: RunResult?
    var selectedTransactionID: String?
    var selectedCalculationID: String?
    var search = ""
    var composer = ""
    var contextIDs: [String] = []
    var showPalette = false
    var showInspector = true
    var showImport = false
    var showGoal = false
    var isWorking = false
    var stale = false
    var error: String?
    var lastReceipt: ActivityReceipt?
    @ObservationIgnored private var service: any FolioService

    init(service: any FolioService) { self.service = service }
    var selectedTransaction: Transaction? { workspace?.transactions.first { $0.id == selectedTransactionID } }
    var selectedCalculation: Calculation? {
        workspace?.calculations.first { $0.id == selectedCalculationID && $0.scope == scope } ?? workspace?.calculations.first { $0.scope == scope }
    }
    var transactions: [Transaction] {
        (workspace?.transactions ?? []).filter { transaction in
            transaction.matches(scope: scope) && (search.isEmpty || "\(transaction.merchant) \(transaction.category) \(transaction.description)".localizedCaseInsensitiveContains(search))
        }
    }
    var reviewCount: Int { workspace?.transactions.filter(\.needsReview).count ?? 0 }
    func configure(baseURL: String) throws { service = try HTTPFolioService(baseURL: baseURL); workspace = nil; conversation = []; lastRun = nil; error = nil }
    func startDemo() async {
        guard !isWorking else { return }
        isWorking = true; error = nil
        defer { isWorking = false }
        do { workspace = try await service.createDemo(); stale = false; scope = .everything; destination = .today }
        catch { self.error = error.localizedDescription }
    }
    func refresh() async {
        guard let workspaceID = workspace?.id, !isWorking else { return }
        isWorking = true; error = nil
        defer { isWorking = false }
        do { workspace = try await service.refresh(workspaceID: workspaceID, scope: scope); stale = false }
        catch { self.error = error.localizedDescription; stale = true }
    }
    func ask(_ question: String? = nil) async {
        let text = (question ?? composer).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, let workspaceID = workspace?.id, !isWorking else { return }
        composer = ""; error = nil; isWorking = true
        conversation.append(ConversationMessage(role: .user, text: text))
        destination = .money
        defer { isWorking = false }
        do {
            let result = try await service.ask(text, workspaceID: workspaceID, scope: scope, transactionIDs: contextIDs)
            lastRun = result
            conversation.append(ConversationMessage(role: .assistant, text: result.text, calculationIDs: result.calculationIDs))
            selectedCalculationID = result.calculationIDs.first
            workspace = try await service.refresh(workspaceID: workspaceID, scope: scope)
            stale = false
        } catch { self.error = error.localizedDescription }
    }
    func annotate(_ change: AnnotationChange) async -> Bool {
        guard let id = workspace?.id, !isWorking else { return false }
        isWorking = true; error = nil
        defer { isWorking = false }
        do {
            lastReceipt = try await service.annotate(change, workspaceID: id)
            workspace = try await service.refresh(workspaceID: id, scope: scope)
            return true
        } catch { self.error = error.localizedDescription; return false }
    }
    func saveGoal(_ draft: GoalDraft) async -> Bool {
        guard let id = workspace?.id, !isWorking else { return false }
        isWorking = true; error = nil
        defer { isWorking = false }
        do { _ = try await service.saveGoal(draft, workspaceID: id); workspace = try await service.refresh(workspaceID: id, scope: scope); return true }
        catch { self.error = error.localizedDescription; return false }
    }
    func forgetMemory(_ memoryID: String) async {
        guard let id = workspace?.id, !isWorking else { return }
        isWorking = true; error = nil
        defer { isWorking = false }
        do { lastReceipt = try await service.forgetMemory(id: memoryID, workspaceID: id); workspace = try await service.refresh(workspaceID: id, scope: scope) }
        catch { self.error = error.localizedDescription }
    }
    func undo(_ receipt: ActivityReceipt) async {
        guard let id = workspace?.id, !isWorking else { return }
        isWorking = true; error = nil
        defer { isWorking = false }
        do { lastReceipt = try await service.undo(receiptID: receipt.id, workspaceID: id); workspace = try await service.refresh(workspaceID: id, scope: scope) }
        catch { self.error = error.localizedDescription }
    }
    func resetDemo() async {
        guard let id = workspace?.id, workspace?.isSynthetic == true, !isWorking else { return }
        isWorking = true; error = nil
        defer { isWorking = false }
        do { workspace = try await service.resetDemo(workspaceID: id); conversation = []; lastRun = nil; selectedTransactionID = nil; contextIDs = []; stale = false; scope = .everything }
        catch { self.error = error.localizedDescription }
    }
    func newConversation() { conversation = []; composer = ""; contextIDs = []; lastRun = nil; destination = .money }
}
