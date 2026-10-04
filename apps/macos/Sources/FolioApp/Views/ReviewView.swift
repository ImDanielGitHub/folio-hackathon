import SwiftUI
import FolioCore

struct ReviewView: View {
    @Bindable var store: FolioStore
    @State private var selectedGroupID: String?
    @State private var applyToGroup = false
    @State private var purpose = "personal"
    @State private var remember = false
    private var groups: [ReviewGroup] { store.workspace?.reviewGroups ?? [] }
    private var group: ReviewGroup? { groups.first { $0.id == selectedGroupID } ?? groups.first }
    private var items: [Transaction] {
        let ids = store.contextIDs.isEmpty ? group?.transactionIDs ?? [] : store.contextIDs
        return (store.workspace?.transactions ?? []).filter { ids.contains($0.id) }
    }
    private var chosen: [Transaction] { applyToGroup ? Array(items.prefix(50)) : Array(items.prefix(1)) }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("A little context goes a long way.").font(FolioTheme.headline(32))
                Text("Some purchases need your judgement. A correction applies only to the items you choose.").foregroundStyle(FolioTheme.secondary).lineSpacing(5)
                if items.isEmpty {
                    EmptyState(title: "Nothing waiting for your review", detail: "When a transaction’s purpose is unclear, it will appear here with its source evidence.", symbol: "checkmark.circle")
                } else {
                    if store.contextIDs.isEmpty {
                        HStack(spacing: 8) {
                            ForEach(groups) { group in
                                Button(group.title) { selectedGroupID = group.id; applyToGroup = false; remember = false }
                                    .buttonStyle(FolioButtonStyle())
                            }
                        }
                    }
                    Hairline()
                    SectionHeading(title: store.contextIDs.isEmpty ? group?.title ?? "Selected purchases" : "Selected purchases", detail: "\(items.count) transactions · purpose is not established by the merchant name")
                    ForEach(Array(items.prefix(3))) { item in
                        Button { store.selectedTransactionID = item.id; store.showInspector = true } label: {
                            HStack(spacing: 16) {
                                VStack(alignment: .leading, spacing: 5) { Text(item.merchant).font(FolioTheme.body(14, weight: .medium)); Text("\(item.date) · \(item.category)").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary) }
                                Spacer()
                                Text(item.amount.formatted()).font(FolioTheme.body(13)).monospacedDigit()
                                Image(systemName: "chevron.right").font(.system(size: 10)).foregroundStyle(FolioTheme.secondary)
                            }.padding(.vertical, 8)
                        }.buttonStyle(.plain)
                    }
                    if items.count > 3 {
                        DisclosureGroup("Show all \(items.count) items") {
                            ForEach(Array(items.dropFirst(3))) { item in
                                HStack { Text("\(item.date) · \(item.merchant)"); Spacer(); Text(item.amount.formatted()).monospacedDigit() }.font(FolioTheme.body(11)).padding(.vertical, 5)
                            }
                        }.font(FolioTheme.body(12))
                    }
                    Hairline()
                    Text("How should these be treated?").font(FolioTheme.body(16, weight: .medium))
                    Picker("Purpose", selection: $purpose) { Text("Personal").tag("personal"); Text("Business").tag("business") }.pickerStyle(.segmented).frame(maxWidth: 260)
                    Picker("Correction scope", selection: $applyToGroup) {
                        Text("Apply to this item (1)").tag(false)
                        Text("Apply to this group (\(min(items.count, 50)))").tag(true)
                    }.pickerStyle(.radioGroup).font(FolioTheme.body(12))
                    Toggle("Remember these selected examples", isOn: $remember).toggleStyle(.checkbox).font(FolioTheme.body(12))
                    Text(remember ? "Saves a confirmed example for these exact transaction IDs. It will not create a rule for every purchase at this merchant." : "No future merchant rule will be created.")
                        .font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary).lineSpacing(4)
                    HStack(spacing: 10) {
                        Button("Confirm \(chosen.count) as \(purpose)") { confirm() }.buttonStyle(FolioButtonStyle(primary: true)).disabled(store.isWorking || chosen.isEmpty)
                        Button("Leave for later") { store.contextIDs = []; store.destination = .today }.buttonStyle(FolioButtonStyle())
                    }
                }
                if let receipt = store.lastReceipt { StatusLine(text: receipt.title, symbol: "checkmark.circle", tone: FolioTheme.success) }
            }.padding(32).frame(maxWidth: 760, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading)
        }
    }
    private func confirm() {
        let selected = chosen
        let change = AnnotationChange(transactionIDs: selected.map(\.id), expectedVersions: Dictionary(uniqueKeysWithValues: selected.map { ($0.id, $0.version) }), purpose: purpose, rememberRule: remember)
        Task { if await store.annotate(change) { store.contextIDs = []; remember = false; applyToGroup = false } }
    }
}
