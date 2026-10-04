import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Backend owns authentication, arithmetic and mutations. The client never holds provider keys.
public actor HTTPFolioService: FolioService {
    private let baseURL: URL
    private let session: URLSession
    private var state: DemoWorkspaceDTO?
    public init(baseURL: String, session: URLSession = .shared) throws {
        guard let url = URL(string: baseURL), let scheme = url.scheme?.lowercased(), let host = url.host,
              scheme == "https" || (scheme == "http" && ["localhost", "127.0.0.1", "::1"].contains(host)),
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil else { throw FolioServiceError.invalidURL }
        self.baseURL = url; self.session = session
    }
    public static func localDevelopment() -> HTTPFolioService { try! HTTPFolioService(baseURL: "http://127.0.0.1:8000") }
    public func createDemo() async throws -> WorkspaceSnapshot {
        let state: DemoWorkspaceDTO = try await request("v1/demo/session", method: "POST", body: Data("{}".utf8))
        self.state = state
        return try await snapshot(state, scope: .everything)
    }
    public func refresh(workspaceID: String, scope: FinancialScope) async throws -> WorkspaceSnapshot {
        let state: DemoWorkspaceDTO = try await request("v1/demo/workspace")
        guard state.id == workspaceID else { throw FolioServiceError.unauthorised }
        self.state = state
        return try await snapshot(state, scope: scope)
    }
    public func ask(_ text: String, workspaceID: String, scope: FinancialScope, transactionIDs: [String]) async throws -> RunResult {
        let state = try current(workspaceID)
        // Current API supports workspace scope only. Do not silently broaden an item-scoped question.
        guard transactionIDs.isEmpty else { throw FolioServiceError.unsupported("Item-scoped questions are not enabled on this server yet. Clear the selected-transaction context to ask about the current workspace scope.") }
        let payload = DemoAskRequest(operationId: UUID().uuidString, expectedVersion: state.version, question: text, scope: scope.rawValue)
        let result: DemoAskDTO = try await request("v1/demo/ask", method: "POST", body: JSONEncoder().encode(payload))
        guard let answer = result.answer, !answer.isEmpty else { throw FolioServiceError.malformedResponse }
        return RunResult(id: result.runId, text: answer, status: result.status, stages: result.receipt?.stages ?? [], calculationIDs: result.surface.map { [$0.calculationId] } ?? [], provider: result.receipt?.provider ?? "Unverified", model: result.receipt?.model, inferenceVerified: result.receipt?.inferenceVerified == true)
    }
    public func annotate(_ change: AnnotationChange, workspaceID: String) async throws -> ActivityReceipt {
        let state = try current(workspaceID)
        guard change.category == nil else { throw FolioServiceError.unsupported("Category editing is not enabled on this server.") }
        guard !change.transactionIDs.isEmpty, change.transactionIDs.allSatisfy({ id in state.transactions.contains { $0.id == id && change.expectedVersions[id] == $0.version } }) else { throw FolioServiceError.staleWrite }
        let payload: DemoActionPayload
        let type: String
        if let percentage = change.businessPercent {
            guard change.transactionIDs.count == 1 else { throw FolioServiceError.unsupported("Preview one transaction before applying a split.") }
            type = "split"; payload = DemoActionPayload(id: change.transactionIDs[0], businessPercent: percentage)
        } else {
            type = "classify"; payload = DemoActionPayload(ids: change.transactionIDs, purpose: change.purpose, remember: change.rememberRule)
        }
        let result = try await action(type, payload: payload, workspaceID: workspaceID)
        guard let receipt = result.activities.first else { throw FolioServiceError.malformedResponse }
        return receipt.domain(canUndo: true)
    }
    public func saveGoal(_ draft: GoalDraft, workspaceID: String) async throws -> Goal {
        guard draft.category == "Eating out", draft.currency == "NZD", draft.scope == .personal else { throw FolioServiceError.unsupported("This demo currently supports a personal eating-out goal in NZD.") }
        let result = try await action("save_goal", payload: DemoActionPayload(limitMinor: draft.targetMinorUnits), workspaceID: workspaceID)
        guard let goal = result.goals.last else { throw FolioServiceError.malformedResponse }
        return goal.domain
    }
    public func forgetMemory(id: String, workspaceID: String) async throws -> ActivityReceipt {
        let result = try await action("forget_memory", payload: DemoActionPayload(id: id), workspaceID: workspaceID)
        guard let receipt = result.activities.first else { throw FolioServiceError.malformedResponse }
        return receipt.domain(canUndo: true)
    }
    public func undo(receiptID: String, workspaceID: String) async throws -> ActivityReceipt {
        let state = try current(workspaceID)
        guard state.activities.first?.id == receiptID, state.activities.first?.undoable == true else { throw FolioServiceError.unsupported("Only the latest reversible action can be undone in this demo.") }
        let result = try await action("undo", payload: DemoActionPayload(), workspaceID: workspaceID)
        guard let receipt = result.activities.first else { throw FolioServiceError.malformedResponse }
        return receipt.domain(canUndo: false)
    }
    public func resetDemo(workspaceID: String) async throws -> WorkspaceSnapshot {
        let result = try await action("reset", payload: DemoActionPayload(), workspaceID: workspaceID)
        return try await snapshot(result, scope: .everything)
    }
    private func current(_ id: String) throws -> DemoWorkspaceDTO {
        guard let state, state.id == id else { throw FolioServiceError.unauthorised }; return state
    }
    private func action(_ type: String, payload: DemoActionPayload, workspaceID: String) async throws -> DemoWorkspaceDTO {
        let current = try current(workspaceID)
        let requestBody = DemoActionRequest(operationId: UUID().uuidString, expectedVersion: current.version, type: type, payload: payload)
        let result: DemoWorkspaceDTO = try await request("v1/demo/actions", method: "POST", body: JSONEncoder().encode(requestBody))
        state = result
        return result
    }
    private func snapshot(_ state: DemoWorkspaceDTO, scope: FinancialScope) async throws -> WorkspaceSnapshot {
        let comparison: DemoComparisonDTO = try await request("v1/demo/comparison", query: [URLQueryItem(name: "scope", value: scope.rawValue)])
        let transactions = state.transactions.map(\.domain)
        let groups = Dictionary(grouping: transactions.filter(\.needsReview), by: \.merchant).map { merchant, items in
            ReviewGroup(id: "review-\(merchant)", title: merchant, reason: "The source record does not establish whether these purchases were personal or business.", transactionIDs: items.map(\.id), suggestedCategory: nil, version: state.version)
        }.sorted { $0.title < $1.title }
        return WorkspaceSnapshot(id: state.id, name: state.displayName, isSynthetic: state.kind == "demo", asOf: ISO8601DateFormatter().string(from: Date()), transactions: transactions, calculations: comparison.domain.map { [$0] } ?? [], goals: state.goals.map(\.domain), reviewGroups: groups, memory: state.memory.map(\.domain), activity: state.activities.enumerated().map { $0.element.domain(canUndo: $0.offset == 0) }, connections: [
            ProviderStatus(name: "Synthetic account", environment: "Demo", status: "Available", detail: "Fictional source records. No real bank connected.", lastSyncedAt: nil),
            ProviderStatus(name: "Akahu", environment: "Not configured", status: "Unavailable", detail: "Live or personal-testing access has not been connected.", lastSyncedAt: nil),
            ProviderStatus(name: "Plaid", environment: "Not configured", status: "Unavailable", detail: "Sandbox and production access have not been connected.", lastSyncedAt: nil),
            ProviderStatus(name: "Nebius · Nemotron", environment: state.model.state, status: state.model.state == "inference_verified" ? "Inference verified" : "Not verified", detail: state.model.model, lastSyncedAt: nil)
        ])
    }
    private func request<T: Decodable>(_ path: String, method: String = "GET", body: Data? = nil, query: [URLQueryItem] = []) async throws -> T {
        var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { components.queryItems = query }
        var request = URLRequest(url: components.url!, timeoutInterval: 90)
        request.httpMethod = method; request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("folio://macos", forHTTPHeaderField: "Origin")
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw FolioServiceError.malformedResponse }
        switch response.statusCode {
        case 200...299: break
        case 401: throw FolioServiceError.unauthorised
        case 409: throw FolioServiceError.staleWrite
        default:
            let detail = (try? JSONDecoder().decode(APIErrorBody.self, from: data).detail) ?? "The server could not complete this request (\(response.statusCode))."
            throw FolioServiceError.unavailable(detail)
        }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw FolioServiceError.malformedResponse }
    }
}

private struct APIErrorBody: Decodable { let detail: String }
