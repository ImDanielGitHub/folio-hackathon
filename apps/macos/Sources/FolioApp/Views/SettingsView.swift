import SwiftUI
import FolioCore

struct SettingsView: View {
    @Bindable var store: FolioStore
    @AppStorage("appearance") private var appearance = "system"
    @AppStorage("apiURL") private var savedURL = "http://127.0.0.1:8000"
    @State private var address = ""
    @State private var message: String?
    var body: some View {
        TabView {
            Form {
                Picker("Appearance", selection: $appearance) { Text("System").tag("system"); Text("Light").tag("light"); Text("Dark").tag("dark") }
                LabeledContent("Language", value: "New Zealand English")
                LabeledContent("Minimum system", value: "macOS 26")
                Text("Animation follows the system’s Reduce Motion setting. Tables and evidence remain readable in both appearances.").font(.caption).foregroundStyle(.secondary)
            }.formStyle(.grouped).tabItem { Label("General", systemImage: "gearshape") }
            Form {
                Section("Demo server") {
                    TextField("Server address", text: $address).textFieldStyle(.roundedBorder)
                    Text("HTTPS is required except on localhost. This address is not a provider credential.").font(.caption).foregroundStyle(.secondary)
                    Button("Use this server") {
                        do { try store.configure(baseURL: address); savedURL = address; message = "Server selected. Open the demo from the main window." }
                        catch { message = error.localizedDescription }
                    }
                    if let message { Text(message).font(.caption) }
                }
                Section("Data and permissions") {
                    Text("The public demo accepts synthetic data only. Statement previews stay local and are not uploaded.")
                    Text("Bank linking, private workspace sign-in, scheduled coaching and Telegram are not enabled in this client build.")
                }
            }.formStyle(.grouped).tabItem { Label("Connections", systemImage: "link") }
            Form {
                Section("You stay in control") {
                    Text("Original source amounts are immutable. Changes are versioned annotations with receipts. Item corrections do not create merchant-wide rules.")
                    Text("No payments, money transfers, plan switches or grant submissions are available.")
                    Text("Optional on-device preprocessing is not enabled. No claim is made that this app scans or removes all personal information.")
                }
            }.formStyle(.grouped).tabItem { Label("Privacy", systemImage: "hand.raised") }
        }.frame(width: 600, height: 430).padding(12).onAppear { address = savedURL }
    }
}
