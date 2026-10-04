import AppKit
import SwiftUI
import FolioCore

final class FolioAppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

@main
struct FolioApp: App {
    @NSApplicationDelegateAdaptor(FolioAppDelegate.self) private var delegate
    @State private var store: FolioStore
    @AppStorage("appearance") private var appearance = "system"
    init() {
        FolioTheme.registerFonts()
        let configured = ProcessInfo.processInfo.environment["FOLIO_API_URL"] ?? UserDefaults.standard.string(forKey: "apiURL") ?? "http://127.0.0.1:8000"
        let service = (try? HTTPFolioService(baseURL: configured)) ?? HTTPFolioService.localDevelopment()
        _store = State(initialValue: FolioStore(service: service))
    }
    var body: some Scene {
        WindowGroup("Folio", id: "main") {
            ContentView(store: store)
                .preferredColorScheme(appearance == "dark" ? .dark : appearance == "light" ? .light : nil)
        }
        .defaultSize(width: 1280, height: 860)
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New conversation") { store.newConversation() }.keyboardShortcut("n")
                Button("Import statement…") { store.showImport = true }.keyboardShortcut("o")
            }
            CommandMenu("Folio") {
                Button("Search commands…") { store.showPalette = true }.keyboardShortcut("k")
                Button("Show transactions") { store.destination = .transactions }.keyboardShortcut("f")
                Button("Toggle inspector") { store.showInspector.toggle() }.keyboardShortcut("i", modifiers: [.command, .option])
                Divider()
                Button("Refresh workspace") { Task { await store.refresh() } }.keyboardShortcut("r").disabled(store.workspace == nil || store.isWorking)
            }
        }
        Settings { SettingsView(store: store) }
        MenuBarExtra("Folio", systemImage: "leaf") { FolioMenu(store: store) }
    }
}

private struct FolioMenu: View {
    @Bindable var store: FolioStore
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        Text(store.workspace?.isSynthetic == true ? "Synthetic demo" : "No workspace connected")
        Button("Open Folio") { openWindow(id: "main"); NSApp.activate(ignoringOtherApps: true) }
        Button("Ask about your money") { store.destination = .money; openWindow(id: "main") }
        Button("Review transactions") { store.destination = .review; openWindow(id: "main") }
        Divider()
        SettingsLink { Text("Settings…") }
        Button("Quit Folio") { NSApplication.shared.terminate(nil) }.keyboardShortcut("q")
    }
}
