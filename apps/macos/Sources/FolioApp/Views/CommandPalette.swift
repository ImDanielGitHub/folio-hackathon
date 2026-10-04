import SwiftUI

struct CommandPalette: View {
    @Bindable var store: FolioStore
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @FocusState private var focused: Bool
    private var matches: [Destination] { Destination.allCases.filter { query.isEmpty || $0.rawValue.localizedCaseInsensitiveContains(query) } }
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass").foregroundStyle(FolioTheme.secondary)
                TextField("Where would you like to go?", text: $query).textFieldStyle(.plain).focused($focused)
                Text("esc").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
            }.padding(20)
            Hairline()
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(matches) { destination in
                        Button { store.destination = destination; dismiss() } label: {
                            HStack(spacing: 12) { Image(systemName: destination.icon).frame(width: 18); Text(destination.rawValue); Spacer(); Image(systemName: "arrow.turn.down.left").foregroundStyle(FolioTheme.secondary) }
                                .font(FolioTheme.body(13)).padding(12).contentShape(Rectangle())
                        }.buttonStyle(.plain)
                    }
                    if matches.isEmpty { Text("No matching destination").font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary).padding(16) }
                    Hairline()
                    Button("New conversation") { store.newConversation(); dismiss() }.buttonStyle(.plain).padding(12)
                    Button("Preview a statement locally…") { dismiss(); store.showImport = true }.buttonStyle(.plain).padding(12)
                }.padding(8)
            }.frame(maxHeight: 420)
        }.frame(width: 520).background(FolioTheme.surface).onAppear { focused = true }.onExitCommand { dismiss() }
    }
}
