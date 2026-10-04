import SwiftUI
import FolioCore

struct GoalsView: View {
    @Bindable var store: FolioStore
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 10) { Text("Make room for what matters.").font(FolioTheme.headline(32)); Text("A goal is a plan you choose. You can change your mind.").foregroundStyle(FolioTheme.secondary) }
                    Spacer()
                    Button("New goal") { store.showGoal = true }.buttonStyle(FolioButtonStyle(primary: true))
                }
                if store.workspace?.goals.isEmpty != false {
                    EmptyState(title: "Start with one small goal.", detail: "Preview a personal eating-out limit, choose an amount and save only when it feels right. No money is moved.", symbol: "flag")
                    Button("Preview an eating-out goal") { store.showGoal = true }.buttonStyle(FolioButtonStyle())
                }
                ForEach(store.workspace?.goals ?? []) { goal in
                    Hairline()
                    VStack(alignment: .leading, spacing: 14) {
                        HStack { Text(goal.title).font(FolioTheme.body(18, weight: .semibold)); Spacer(); StatusLine(text: goal.status.capitalized, symbol: goal.status == "paused" ? "pause.circle" : "flag") }
                        Text(goal.target.formatted()).font(FolioTheme.headline(34)).monospacedDigit()
                        Text("Personal · Monthly spending limit · NZD").font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary)
                        if let current = goal.current {
                            HStack { Text("Measured spending"); Spacer(); Text(current.formatted()).monospacedDigit() }.font(FolioTheme.body(12))
                        } else { StatusLine(text: "Progress unavailable. No transactions for the goal period have been imported.", symbol: "info.circle") }
                        Text("Reduced spending is not counted as money transferred into savings.").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
                    }
                }
            }.padding(32).frame(maxWidth: 800, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct GoalEditor: View {
    @Bindable var store: FolioStore
    @Environment(\.dismiss) private var dismiss
    @State private var amount = "300.00"
    @State private var localError: String?
    private var money: Money? { try? Money.parse(amount) }
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack { Text("Give eating out a little room.").font(FolioTheme.headline(30)); Spacer(); Button { dismiss() } label: { Image(systemName: "xmark") }.buttonStyle(.plain).accessibilityLabel("Close goal preview") }
            Text("Preview a monthly limit. Nothing is saved until you choose Save goal.").foregroundStyle(FolioTheme.secondary).lineSpacing(5)
            Hairline()
            LabeledContent("Category", value: "Eating out")
            LabeledContent("Scope", value: "Personal")
            LabeledContent("Currency", value: "NZD")
            LabeledContent("Starts", value: "1 October 2026 · Synthetic demo")
            LabeledContent("Monthly limit") {
                TextField("300.00", text: $amount).textFieldStyle(.roundedBorder).frame(width: 140).multilineTextAlignment(.trailing)
            }
            if let baseline = store.workspace?.calculations.first?.categories.first(where: { $0.category == "Eating out" }) {
                Text("September baseline: \(baseline.current.formatted()). Open Money to inspect the calculation and its source records.").font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary)
            }
            Hairline()
            Text("Progress uses posted personal spending in this category. October coverage is currently missing, so the goal begins without measured progress. No daily notifications or savings transfer are created.")
                .font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary).lineSpacing(5)
            if let error = localError ?? store.error { StatusLine(text: error, symbol: "exclamationmark.triangle", tone: FolioTheme.danger) }
            HStack {
                Button("Keep my current plan") { dismiss() }.buttonStyle(FolioButtonStyle())
                Spacer()
                Button(store.isWorking ? "Saving…" : "Save goal") { save() }.buttonStyle(FolioButtonStyle(primary: true)).disabled(store.isWorking || money == nil || (money?.minorUnits ?? 0) <= 0)
            }
        }.font(FolioTheme.body(13)).padding(28).frame(width: 570).background(FolioTheme.surface)
    }
    private func save() {
        guard let money, money.minorUnits > 0 else { localError = "Enter a positive amount with no more than two decimal places."; return }
        Task { if await store.saveGoal(GoalDraft(title: "Eating out", category: "Eating out", targetMinorUnits: money.minorUnits)) { store.destination = .goals; dismiss() } }
    }
}
