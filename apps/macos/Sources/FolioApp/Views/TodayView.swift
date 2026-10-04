import SwiftUI
import FolioCore

struct TodayView: View {
    @Bindable var store: FolioStore
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                VStack(alignment: .leading, spacing: 10) {
                    HStack { Text("Today").font(FolioTheme.body(12, weight: .medium)); Spacer(); freshness }
                    Text("A clearer picture of your money.").font(FolioTheme.headline(34)).lineSpacing(2)
                    Text("Here’s one place to start. You decide what happens next.").foregroundStyle(FolioTheme.secondary).lineSpacing(5)
                }
                if let calculation = store.selectedCalculation {
                    Hairline()
                    VStack(alignment: .leading, spacing: 16) {
                        Text("September spending").font(FolioTheme.body(12, weight: .medium)).foregroundStyle(FolioTheme.secondary)
                        Text(calculation.current.formatted()).font(FolioTheme.headline(40)).monospacedDigit()
                        Text("\(Money(minorUnits: abs(calculation.delta.minorUnits), currency: calculation.delta.currency).formatted()) \(calculation.delta.minorUnits >= 0 ? "more" : "less") than August.").font(FolioTheme.body(14))
                        Text("Includes the selected scope. Open the breakdown to inspect categories and source records.").font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary)
                        HStack(spacing: 10) {
                            Button("See what changed") { store.destination = .money; store.selectedCalculationID = calculation.id; store.showInspector = true }.buttonStyle(FolioButtonStyle(primary: true))
                            Button("Browse transactions") { store.destination = .transactions }.buttonStyle(FolioButtonStyle())
                        }
                        Text("Calculation · \(calculation.id)").font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary).textSelection(.enabled)
                    }
                }
                Hairline()
                HStack(alignment: .top, spacing: 28) {
                    summary("A little help with the details", value: "\(store.reviewCount) to review", detail: "You can answer for one item or a selected group.", destination: .review)
                    summary("Your goals", value: store.workspace?.goals.isEmpty == false ? "\(store.workspace!.goals.count) saved" : "Choose your own pace", detail: "Set a spending limit when it’s useful to you.", destination: .goals)
                }
                Hairline()
                VStack(alignment: .leading, spacing: 12) {
                    SectionHeading(title: "What would you like to understand?")
                    ComposerView(store: store)
                    Text("Try “Why was September different?” or “Help me review the unclear purchases”.")
                        .font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
                }
            }.padding(32).frame(maxWidth: 800, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading)
        }
    }
    private var freshness: some View {
        StatusLine(text: store.stale ? "Offline · Last loaded view" : "Synthetic data · July–September 2026", symbol: store.stale ? "wifi.slash" : "circle.dotted", tone: store.stale ? FolioTheme.warning : FolioTheme.secondary)
    }
    private func summary(_ title: String, value: String, detail: String, destination: Destination) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
            Button(value) { store.destination = destination }.font(FolioTheme.body(16, weight: .medium)).buttonStyle(.plain)
            Text(detail).font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary).lineSpacing(4)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}
