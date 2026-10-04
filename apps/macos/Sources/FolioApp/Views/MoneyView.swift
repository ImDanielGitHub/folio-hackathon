import SwiftUI
import FolioCore

struct MoneyView: View {
    @Bindable var store: FolioStore
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 26) {
                        if store.conversation.isEmpty {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("Let’s make sense of it.").font(FolioTheme.headline(38))
                                Text("Ask a question about your money. The evidence stays beside the conversation.").font(FolioTheme.body(15)).foregroundStyle(FolioTheme.secondary).lineSpacing(6)
                                suggestions
                            }.padding(.top, 20)
                        }
                        ForEach(store.conversation) { message in messageView(message).id(message.id) }
                        if store.isWorking {
                            HStack(spacing: 10) { ProgressView().controlSize(.small); Text("Waiting for the server…").font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary) }
                        }
                        if let run = store.lastRun {
                            RunReceiptView(run: run)
                        }
                    }.frame(maxWidth: 640, alignment: .leading).padding(32).frame(maxWidth: .infinity, alignment: .center)
                }.onChange(of: store.conversation.count) { if let id = store.conversation.last?.id { proxy.scrollTo(id, anchor: .bottom) } }
            }
            Hairline()
            ComposerView(store: store).padding(24)
        }
    }
    private var suggestions: some View {
        VStack(alignment: .leading, spacing: 10) {
            Button("Why was September different?") { Task { await store.ask("Why was September different from August?") } }
            Button("Help me review unclear purchases") { store.destination = .review }
            Button("Set an eating-out goal") { store.showGoal = true }
        }.buttonStyle(FolioButtonStyle()).padding(.top, 8)
    }
    private func messageView(_ message: ConversationMessage) -> some View {
        HStack {
            if message.role == .user { Spacer(minLength: 56) }
            VStack(alignment: .leading, spacing: 12) {
                if message.role == .assistant { Text("Folio").font(FolioTheme.body(12, weight: .semibold)) }
                Text(message.text).font(FolioTheme.body(14)).lineSpacing(7).textSelection(.enabled)
                ForEach(message.calculationIDs, id: \.self) { id in
                    Button { store.selectedCalculationID = id; store.showInspector = true } label: { Label("View evidence", systemImage: "arrow.up.right") }
                        .buttonStyle(.plain).font(FolioTheme.body(12)).foregroundStyle(FolioTheme.accent)
                }
            }
            .padding(message.role == .user ? 16 : 0)
            .background(message.role == .user ? FolioTheme.sunken : .clear)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            if message.role == .assistant { Spacer(minLength: 10) }
        }
    }
}

struct ComposerView: View {
    @Bindable var store: FolioStore
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !store.contextIDs.isEmpty {
                HStack(spacing: 8) {
                    Label("\(store.contextIDs.count) selected transaction(s)", systemImage: "doc.text")
                    Button { store.contextIDs = [] } label: { Image(systemName: "xmark") }.buttonStyle(.plain).accessibilityLabel("Clear question context")
                }.font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary)
            }
            HStack(alignment: .bottom, spacing: 12) {
                TextField("Ask Folio about your money…", text: $store.composer, axis: .vertical)
                    .textFieldStyle(.plain).lineLimit(1...5).font(FolioTheme.body(14))
                    .onSubmit { Task { await store.ask() } }
                Button { Task { await store.ask() } } label: {
                    Image(systemName: "arrow.up").font(.system(size: 12, weight: .semibold)).foregroundStyle(FolioTheme.surface).frame(width: 28, height: 28).background(FolioTheme.accent).clipShape(RoundedRectangle(cornerRadius: 8))
                }.buttonStyle(.plain).disabled(store.composer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.isWorking || store.workspace == nil).accessibilityLabel("Send question")
            }.padding(.vertical, 14).padding(.leading, 16).padding(.trailing, 12)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(FolioTheme.border, lineWidth: 1))
            Text("Scope: \(store.scope.title). Folio asks before changing anything.").font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary)
        }
    }
}

private struct RunReceiptView: View {
    let run: RunResult
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Hairline()
            StatusLine(text: run.status == "completed" ? "Work receipt" : "Partial result", symbol: run.status == "completed" ? "checkmark.circle" : "info.circle")
            ForEach(Array(run.stages.enumerated()), id: \.offset) { _, stage in Text(stage).font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary) }
            Text(run.inferenceVerified ? "Inference verified · \(run.provider) · \(run.model ?? "model recorded by server")" : "Live model inference has not been verified for this result.")
                .font(FolioTheme.body(10)).foregroundStyle(FolioTheme.secondary).textSelection(.enabled)
        }
    }
}
