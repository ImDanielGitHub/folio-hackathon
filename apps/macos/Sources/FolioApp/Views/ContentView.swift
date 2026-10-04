import SwiftUI

struct ContentView: View {
    @Bindable var store: FolioStore
    @State private var compactInspector = false
    @State private var confirmReset = false
    var body: some View {
        GeometryReader { geometry in
            HStack(spacing: 0) {
                SidebarView(store: store).frame(width: FolioTheme.sidebarWidth)
                Rectangle().fill(FolioTheme.border).frame(width: 1)
                VStack(spacing: 0) {
                    header(compact: geometry.size.width < 1180)
                    Hairline()
                    if store.workspace?.isSynthetic == true { demoBanner }
                    if let error = store.error { errorBanner(error) }
                    if store.workspace == nil { WelcomeView(store: store) }
                    else { destination }
                }.frame(maxWidth: .infinity, maxHeight: .infinity).background(FolioTheme.surface)
                if geometry.size.width >= 1180, store.workspace != nil, store.showInspector {
                    Rectangle().fill(FolioTheme.border).frame(width: 1)
                    InspectorView(store: store).frame(width: FolioTheme.inspectorWidth)
                }
            }
            .background(FolioTheme.canvas)
            .sheet(isPresented: $compactInspector) { InspectorView(store: store).frame(width: 400, height: 640).padding(.top, 20) }
        }
        .frame(minWidth: 1024, minHeight: 720)
        .font(FolioTheme.body())
        .onChange(of: store.scope) { Task { await store.refresh() } }
        .foregroundStyle(FolioTheme.ink)
        .sheet(isPresented: $store.showPalette) { CommandPalette(store: store) }
        .sheet(isPresented: $store.showImport) { ImportPreviewView() }
        .sheet(isPresented: $store.showGoal) { GoalEditor(store: store) }
        .confirmationDialog("Reset this synthetic demo?", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("Reset demo", role: .destructive) { Task { await store.resetDemo() } }
            Button("Keep this demo", role: .cancel) {}
        } message: { Text("The demo’s saved goals, corrections and conversation will be cleared. Real accounts are not connected.") }
    }
    private func header(compact: Bool) -> some View {
        HStack(spacing: 16) {
            Picker("Workspace scope", selection: $store.scope) {
                ForEach(FinancialScope.allCases) { scope in Text(scope.title).tag(scope) }
            }.pickerStyle(.menu).frame(width: 160)
            Spacer()
            Button { store.showPalette = true } label: {
                HStack(spacing: 8) { Image(systemName: "magnifyingglass"); Text("Search"); Text("⌘K").foregroundStyle(FolioTheme.secondary) }
            }.buttonStyle(.plain).foregroundStyle(FolioTheme.secondary)
            Button { if compact { compactInspector = true } else { store.showInspector.toggle() } } label: {
                Image(systemName: "sidebar.right").frame(width: 28, height: 28)
            }.buttonStyle(.plain).help("Show evidence and details").accessibilityLabel("Show inspector")
        }.padding(.horizontal, 24).padding(.top, 28).padding(.bottom, 16)
    }
    private var demoBanner: some View {
        HStack(spacing: 8) {
            Image(systemName: "circle.dotted")
            Text("Demo · Fictional transactions. No bank connection.")
            Spacer()
            Button("Reset demo") { confirmReset = true }.buttonStyle(.plain).underline()
        }.font(FolioTheme.body(11)).padding(.horizontal, 24).padding(.vertical, 9).background(FolioTheme.sunken)
    }
    private func errorBanner(_ message: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "exclamationmark.triangle")
            Text(message).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
            Button { store.error = nil } label: { Image(systemName: "xmark") }.buttonStyle(.plain).accessibilityLabel("Dismiss error")
        }.font(FolioTheme.body(12)).foregroundStyle(FolioTheme.danger).padding(16).background(FolioTheme.canvas)
    }
    @ViewBuilder private var destination: some View {
        switch store.destination {
        case .today: TodayView(store: store)
        case .money: MoneyView(store: store)
        case .transactions: TransactionsView(store: store)
        case .review: ReviewView(store: store)
        case .goals: GoalsView(store: store)
        case .activity: ActivityView(store: store)
        case .memory: MemoryView(store: store)
        case .connections: ConnectionsView(store: store)
        case .bills: BillsView(store: store)
        case .opportunities: OpportunitiesView(store: store)
        }
    }
}

import FolioCore
