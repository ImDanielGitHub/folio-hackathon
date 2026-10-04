import SwiftUI
import FolioCore

struct TransactionsView: View {
    @Bindable var store: FolioStore
    @State private var selected = Set<String>()
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Transactions").font(FolioTheme.headline(30))
                    Text("July–September 2026 · \(store.scope.title) · NZD").font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary)
                }
                Spacer()
                Button("Import statement") { store.showImport = true }.buttonStyle(FolioButtonStyle())
            }
            HStack {
                Image(systemName: "magnifyingglass").foregroundStyle(FolioTheme.secondary)
                TextField("Search merchant, category or description", text: $store.search).textFieldStyle(.plain)
                if !store.search.isEmpty { Button("Reset") { store.search = "" }.buttonStyle(.plain).foregroundStyle(FolioTheme.accent) }
            }.font(FolioTheme.body(12)).padding(10).background(FolioTheme.canvas).overlay(RoundedRectangle(cornerRadius: 6).stroke(FolioTheme.border, lineWidth: 1))
            if store.transactions.isEmpty {
                EmptyState(title: "No matching transactions", detail: "Try a different search or reset the scope. An empty result does not mean no spending.")
                Spacer()
            } else {
                Table(store.transactions, selection: $selected) {
                    TableColumn("Date") { Text($0.date).font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary) }.width(min: 74, ideal: 84, max: 92)
                    TableColumn("Merchant") { transaction in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(transaction.merchant).font(FolioTheme.body(12, weight: .medium)).lineLimit(1)
                            Text(transaction.category).font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary).lineLimit(1)
                        }.padding(.vertical, 5)
                    }.width(min: 130, ideal: 200)
                    TableColumn("Purpose") { transaction in Text(transaction.needsReview ? "Needs review" : transaction.purpose.capitalized).font(FolioTheme.body(11)).foregroundStyle(transaction.needsReview ? FolioTheme.warning : FolioTheme.secondary) }.width(min: 70, ideal: 85, max: 110)
                    TableColumn("Amount") { Text($0.amount.formatted()).font(FolioTheme.body(12)).monospacedDigit().frame(maxWidth: .infinity, alignment: .trailing) }.width(min: 85, ideal: 96, max: 120)
                }.tableStyle(.inset(alternatesRowBackgrounds: false))
                    .onChange(of: selected) { store.selectedTransactionID = selected.count == 1 ? selected.first : nil }
            }
            HStack {
                Text(selected.isEmpty ? "\(store.transactions.count) matching records" : "\(selected.count) selected").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
                Spacer()
                if !selected.isEmpty {
                    Button("Review selected") { store.destination = .review; store.contextIDs = Array(selected).sorted() }.buttonStyle(FolioButtonStyle())
                }
            }
        }.padding(28)
    }
}
