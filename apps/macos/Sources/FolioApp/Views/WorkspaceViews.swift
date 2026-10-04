import SwiftUI
import FolioCore

struct ActivityView: View {
    @Bindable var store: FolioStore
    var body: some View {
        WorkspacePage(title: "A record of the work.", subtitle: "Completed changes, their scope, and the latest available undo.") {
            if store.workspace?.activity.isEmpty != false { EmptyState(title: "No saved changes yet", detail: "Confirm a review, apply a split or save a goal. Its server receipt will appear here.", symbol: "clock.arrow.circlepath") }
            ForEach(store.workspace?.activity ?? []) { receipt in
                Hairline()
                HStack(alignment: .top, spacing: 16) {
                    Image(systemName: "checkmark.circle").foregroundStyle(FolioTheme.success)
                    VStack(alignment: .leading, spacing: 8) {
                        Text(receipt.title).font(FolioTheme.body(15, weight: .medium))
                        Text("\(receipt.detail) · \(receipt.createdAt)").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
                        if !receipt.affectedIDs.isEmpty { Text("\(receipt.affectedIDs.count) source transaction(s). Original amounts unchanged.").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary) }
                        Text("Receipt · \(receipt.id)").font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary).textSelection(.enabled)
                    }
                    Spacer()
                    if receipt.canUndo { Button("Undo") { Task { await store.undo(receipt) } }.buttonStyle(FolioButtonStyle()).disabled(store.isWorking) }
                }
            }
        }
    }
}

struct MemoryView: View {
    @Bindable var store: FolioStore
    var body: some View {
        WorkspacePage(title: "What Folio remembers.", subtitle: "Confirmed examples have a visible source and a specific scope.") {
            if store.workspace?.memory.isEmpty != false { EmptyState(title: "A clean slate", detail: "When you choose to remember selected examples during review, they appear here. A single correction never becomes a merchant-wide rule.", symbol: "square.stack") }
            ForEach(store.workspace?.memory ?? []) { item in
                Hairline()
                VStack(alignment: .leading, spacing: 10) {
                    Text(item.text).font(FolioTheme.body(15, weight: .medium))
                    StatusLine(text: item.confirmed ? "Confirmed by you" : "Suggestion · not confirmed", symbol: item.confirmed ? "checkmark.circle" : "questionmark.circle")
                    Text("Scope: \(item.scope)").font(FolioTheme.body(12))
                    Text("\(item.source) · \(item.createdAt)").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
                    Button("Forget this example") { Task { await store.forgetMemory(item.id) } }.buttonStyle(FolioButtonStyle()).disabled(store.isWorking)
                }
            }
        }
    }
}

struct ConnectionsView: View {
    @Bindable var store: FolioStore
    var body: some View {
        WorkspacePage(title: "Connected, with context.", subtitle: "Every source shows its actual environment. A demo is never a live bank connection.") {
            ForEach(store.workspace?.connections ?? []) { provider in
                Hairline()
                VStack(alignment: .leading, spacing: 12) {
                    HStack { Text(provider.name).font(FolioTheme.body(17, weight: .semibold)); Spacer(); Text(provider.environment.replacingOccurrences(of: "_", with: " ")).font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary) }
                    StatusLine(text: provider.status, symbol: provider.status == "Available" ? "checkmark.circle" : "info.circle")
                    Text(provider.detail).font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary).textSelection(.enabled)
                    if let synced = provider.lastSyncedAt { Text("Last synced: \(synced)").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary) }
                }
            }
            Text("Provider credentials stay on the backend. This app does not ask for banking passwords or inference keys.").font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary).lineSpacing(5)
        }
    }
}

struct BillsView: View {
    @Bindable var store: FolioStore
    private var candidates: [Transaction] { (store.workspace?.transactions ?? []).filter { $0.category == "Power" && $0.date.hasPrefix("2026-09") } }
    var body: some View {
        WorkspacePage(title: "The things that come around.", subtitle: "Inspect source charges before confirming a recurring commitment.") {
            StatusLine(text: "Recurring-series detection and next-bill estimates are not enabled in this demo.", symbol: "info.circle")
            SectionHeading(title: "Example power charges", detail: "Source evidence only. This is not a prediction of the next bill.")
            ForEach(candidates.prefix(6)) { transaction in
                Hairline()
                Button { store.selectedTransactionID = transaction.id; store.showInspector = true } label: {
                    HStack { VStack(alignment: .leading, spacing: 5) { Text(transaction.merchant); Text(transaction.date).font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary) }; Spacer(); Text(transaction.amount.formatted()).monospacedDigit(); Image(systemName: "chevron.right").font(.system(size: 10)) }
                }.buttonStyle(.plain)
            }
            Text("No cancellations or provider switches are performed here.").font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary)
        }
    }
}

struct OpportunitiesView: View {
    @Bindable var store: FolioStore
    var body: some View {
        WorkspacePage(title: "Worth a closer look.", subtitle: "Alternatives should fit your needs before they promise a saving.") {
            EmptyState(title: "No verified opportunities yet", detail: "This server has no verified plan, fee or eligibility sources. A savings estimate will appear only after the terms and missing facts have been checked.", symbol: "sparkle")
            Hairline()
            SectionHeading(title: "A useful comparison needs", detail: "You can keep your existing plan at every step.")
            ForEach(["Your confirmed country and coverage needs", "Current plan, billing cycle and any exit fee", "A dated source for the alternative’s full terms", "Promotion expiry and first-year net cost"], id: \.self) { requirement in
                Label(requirement, systemImage: "circle").font(FolioTheme.body(13)).foregroundStyle(FolioTheme.secondary)
            }
        }
    }
}

private struct WorkspacePage<Content: View>: View {
    let title: String
    let subtitle: String
    let content: Content
    init(title: String, subtitle: String, @ViewBuilder content: () -> Content) {
        self.title = title; self.subtitle = subtitle; self.content = content()
    }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text(title).font(FolioTheme.headline(32))
                Text(subtitle).foregroundStyle(FolioTheme.secondary).lineSpacing(5)
                content
            }.padding(32).frame(maxWidth: 800, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
