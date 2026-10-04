import SwiftUI

struct SidebarView: View {
    @Bindable var store: FolioStore
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Folio").font(FolioTheme.headline(30)).padding(.horizontal, 24).padding(.top, 50).padding(.bottom, 34)
            ForEach(Array(Destination.allCases.prefix(4))) { item in row(item) }
            Text("Workspace").font(FolioTheme.body(11, weight: .medium)).foregroundStyle(FolioTheme.secondary).padding(.horizontal, 20).padding(.top, 28).padding(.bottom, 10)
            ForEach(Array(Destination.allCases.dropFirst(4))) { item in row(item) }
            Spacer(minLength: 20)
            Hairline().padding(.horizontal, 16)
            SettingsLink {
                HStack(spacing: 10) { Image(systemName: "gearshape").frame(width: 18); Text("Settings") }
                    .font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary).padding(.horizontal, 20).padding(.vertical, 14)
            }.buttonStyle(.plain)
            HStack(spacing: 9) {
                Text(store.workspace == nil ? "F" : "SR").font(FolioTheme.body(10, weight: .medium)).frame(width: 28, height: 28).background(FolioTheme.sunken).clipShape(Circle())
                VStack(alignment: .leading, spacing: 3) {
                    Text(store.workspace?.name ?? "Your workspace").font(FolioTheme.body(12, weight: .medium))
                    Text(store.workspace?.isSynthetic == true ? "Synthetic demo" : "Not connected").font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary)
                }
            }.padding(.horizontal, 18).padding(.bottom, 20)
        }.background(FolioTheme.canvas)
    }
    private func row(_ destination: Destination) -> some View {
        Button {
            store.destination = destination
            if destination != .transactions { store.search = "" }
        } label: {
            HStack(spacing: 10) {
                Image(systemName: destination.icon).frame(width: 18).foregroundStyle(FolioTheme.secondary)
                Text(destination.rawValue).lineLimit(1)
                Spacer(minLength: 2)
                if destination == .review, store.reviewCount > 0 { Text("\(store.reviewCount)").font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary) }
            }
            .font(FolioTheme.body(12, weight: store.destination == destination ? .medium : .regular))
            .padding(.horizontal, 10).frame(height: 34)
            .background(store.destination == destination ? FolioTheme.selection : .clear)
            .clipShape(RoundedRectangle(cornerRadius: 5))
            .contentShape(Rectangle())
        }.buttonStyle(.plain).padding(.horizontal, 10).padding(.vertical, 1)
            .accessibilityAddTraits(store.destination == destination ? [.isSelected] : [])
    }
}
