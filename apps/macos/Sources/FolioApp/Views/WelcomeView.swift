import SwiftUI

struct WelcomeView: View {
    @Bindable var store: FolioStore
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Spacer()
            Text("A little clarity.\nA little less to do.").font(FolioTheme.headline(40)).lineSpacing(2)
            Text("Understand your money and let Folio help with the work.")
                .font(FolioTheme.body(15)).foregroundStyle(FolioTheme.secondary).lineSpacing(6)
            VStack(alignment: .leading, spacing: 12) {
                Button { Task { await store.startDemo() } } label: {
                    HStack(spacing: 8) { if store.isWorking { ProgressView().controlSize(.small) }; Text(store.isWorking ? "Opening demo…" : "Try a demo"); Image(systemName: "arrow.right") }
                }.buttonStyle(FolioButtonStyle(primary: true)).disabled(store.isWorking)
                Button("Import a statement") { store.showImport = true }.buttonStyle(FolioButtonStyle())
                Button("Connect a bank") { store.destination = .connections; store.error = "Bank connections are not enabled in this build. You can preview a statement locally or try the synthetic demo." }.buttonStyle(.plain).foregroundStyle(FolioTheme.accent)
            }
            StatusLine(text: "The demo uses fictional data in an isolated workspace. No bank login required.", symbol: "lock")
            Spacer()
            Text("Your financial data stays on your Mac during statement preview. Upload requires a signed-in private workspace, which is not enabled in the public demo.")
                .font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary).lineSpacing(4)
        }.frame(maxWidth: 540, alignment: .leading).padding(48).frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
