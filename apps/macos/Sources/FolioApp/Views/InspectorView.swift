import SwiftUI
import FolioCore

struct InspectorView: View {
    @Bindable var store: FolioStore
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack { Text(store.selectedTransaction != nil ? "Transaction" : "Evidence").font(FolioTheme.body(12, weight: .semibold)); Spacer(); Image(systemName: "sidebar.right").foregroundStyle(FolioTheme.secondary) }
                if let transaction = store.selectedTransaction {
                    TransactionInspector(store: store, transaction: transaction).id(transaction.id)
                } else if let calculation = store.selectedCalculation {
                    EvidenceInspector(store: store, calculation: calculation)
                } else {
                    EmptyState(title: "The detail belongs here.", detail: "Select a transaction or open a calculation to see its source records and assumptions.", symbol: "doc.text.magnifyingglass")
                }
            }.padding(24).padding(.top, 24)
        }.background(FolioTheme.canvas)
    }
}

private struct EvidenceInspector: View {
    @Bindable var store: FolioStore
    let calculation: Calculation
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 7) {
                Text("September vs August").font(FolioTheme.headline(26))
                Text("\(calculation.scope.title) · \(calculation.current.currency)").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
            }
            VStack(spacing: 12) {
                amountRow("September", calculation.current)
                amountRow("August", calculation.previous)
                Hairline()
                amountRow("Difference", calculation.delta, strong: true)
            }
            Rectangle().fill(FolioTheme.ink).frame(height: 2)
            SectionHeading(title: "Where it changed", detail: "Same figures as the calculation table.")
            ForEach(calculation.categories) { category in
                Button {
                    store.search = category.category; store.destination = .transactions; store.selectedTransactionID = nil
                } label: {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(category.category).lineLimit(2)
                            Spacer()
                            Text(signed(category.delta)).monospacedDigit()
                        }.font(FolioTheme.body(11))
                        GeometryReader { geometry in
                            Rectangle().fill(FolioTheme.border).frame(height: 3)
                            Rectangle().fill(FolioTheme.secondary).frame(width: geometry.size.width * fraction(category.delta.minorUnits), height: 3)
                        }.frame(height: 3).accessibilityHidden(true)
                    }
                }.buttonStyle(.plain).accessibilityLabel("\(category.category), change \(signed(category.delta)), show transactions")
            }
            Hairline()
            DisclosureGroup("Calculation and sources") {
                VStack(alignment: .leading, spacing: 10) {
                    Text(calculation.id).textSelection(.enabled)
                    ForEach(calculation.assumptions, id: \.self) { Text($0) }
                    Text("\(calculation.sourceIDs.count) source records")
                }.font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary).padding(.top, 8)
            }.font(FolioTheme.body(11))
            Button("Show matching transactions") { store.destination = .transactions; store.search = "" }.buttonStyle(FolioButtonStyle())
        }
    }
    private func amountRow(_ title: String, _ amount: Money, strong: Bool = false) -> some View {
        HStack { Text(title); Spacer(); Text(amount.formatted()).monospacedDigit() }.font(FolioTheme.body(12, weight: strong ? .semibold : .regular))
    }
    private func signed(_ money: Money) -> String { (money.minorUnits > 0 ? "+" : "") + money.formatted() }
    private func fraction(_ value: Int64) -> Double {
        let maximum = calculation.categories.map { abs(Double($0.delta.minorUnits)) }.max() ?? 1
        return maximum == 0 ? 0 : abs(Double(value)) / maximum
    }
}

private struct TransactionInspector: View {
    @Bindable var store: FolioStore
    let transaction: Transaction
    @State private var percentage = 60
    @State private var showSplit = false
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 8) {
                Text(transaction.merchant).font(FolioTheme.headline(28))
                Text(transaction.amount.formatted(explicitCurrency: true)).font(FolioTheme.headline(32)).monospacedDigit()
                Text("\(transaction.date) · \(transaction.account)").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
                StatusLine(text: transaction.needsReview ? "Needs your review" : "Purpose: \(transaction.purpose)", symbol: transaction.needsReview ? "questionmark.circle" : "checkmark.circle")
            }
            Hairline()
            VStack(alignment: .leading, spacing: 10) {
                Text("Category").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
                Text(transaction.category).font(FolioTheme.body(14, weight: .medium))
                Text("Original source amount is never changed by a correction.").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
            }
            HStack {
                Button("Personal") { classify("personal") }
                Button("Business") { classify("business") }
            }.buttonStyle(FolioButtonStyle()).disabled(store.isWorking)
            Button(showSplit ? "Close split preview" : "Split personal and business") { showSplit.toggle() }.buttonStyle(.plain).foregroundStyle(FolioTheme.accent).font(FolioTheme.body(12))
            if showSplit { splitPreview }
            Hairline()
            DisclosureGroup("Original bank data") {
                VStack(alignment: .leading, spacing: 8) {
                    Text(transaction.description)
                    Text("Source · \(transaction.sourceID)")
                    Text("Version · \(transaction.version)")
                }.font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary).textSelection(.enabled).padding(.top, 8)
            }.font(FolioTheme.body(12))
            Text("No receipt attached. Merchant descriptions alone do not establish business purpose.").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary).lineSpacing(4)
            Button("Close transaction") { store.selectedTransactionID = nil }.buttonStyle(.plain).font(FolioTheme.body(12)).foregroundStyle(FolioTheme.accent)
        }
    }
    private var splitPreview: some View {
        VStack(alignment: .leading, spacing: 12) {
            Stepper("Business: \(percentage)%", value: $percentage, in: 0...100, step: 5).font(FolioTheme.body(12))
            if let parts = try? transaction.amount.split(businessPercent: Int64(percentage)) {
                HStack { Text("Business"); Spacer(); Text(parts.business.formatted()).monospacedDigit() }
                HStack { Text("Personal"); Spacer(); Text(parts.personal.formatted()).monospacedDigit() }
                Text("Preview · this transaction only. Both amounts add up to the unchanged source amount.").font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary)
                Button("Apply to this transaction") {
                    Task { _ = await store.annotate(AnnotationChange(transactionIDs: [transaction.id], expectedVersions: [transaction.id: transaction.version], businessPercent: percentage)) }
                }.buttonStyle(FolioButtonStyle(primary: true)).disabled(store.isWorking)
            }
        }.font(FolioTheme.body(12)).padding(12).background(FolioTheme.sunken).clipShape(RoundedRectangle(cornerRadius: 6))
    }
    private func classify(_ purpose: String) {
        Task { _ = await store.annotate(AnnotationChange(transactionIDs: [transaction.id], expectedVersions: [transaction.id: transaction.version], purpose: purpose)) }
    }
}
