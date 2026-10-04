import SwiftUI
import UniformTypeIdentifiers
import FolioCore

struct ImportPreviewView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var showPicker = false
    @State private var rawCSV: String?
    @State private var fileName = ""
    @State private var dateOrder: CSVDateOrder?
    @State private var preview: CSVPreview?
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack { Text("Preview a statement").font(FolioTheme.headline(30)); Spacer(); Button("Done") { dismiss() }.buttonStyle(FolioButtonStyle()) }
            StatusLine(text: "Local preview only. This file is not uploaded to the demo server.", symbol: "lock")
            Button("Choose a CSV file…") { showPicker = true }.buttonStyle(FolioButtonStyle(primary: true))
            if rawCSV != nil {
                Text(fileName).font(FolioTheme.body(12, weight: .medium))
                Picker("Date interpretation", selection: $dateOrder) {
                    Text("Choose for non-ISO dates").tag(Optional<CSVDateOrder>.none)
                    ForEach(CSVDateOrder.allCases) { order in Text(order.title).tag(Optional(order)) }
                }.onChange(of: dateOrder) { reparse() }
            }
            if let error { StatusLine(text: error, symbol: "exclamationmark.triangle", tone: FolioTheme.danger) }
            if let preview {
                HStack { Text("\(preview.accepted.count) ready"); Text("\(preview.rows.filter { $0.status == .duplicate }.count) possible duplicates"); Text("\(preview.rows.filter { $0.status == .skipped }.count) skipped") }.font(FolioTheme.body(12))
                Hairline()
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                        ForEach(preview.rows) { row in
                            VStack(alignment: .leading, spacing: 5) {
                                HStack { Text("Row \(row.id) · \(row.date ?? "Date needs review")").foregroundStyle(FolioTheme.secondary); Spacer(); Text(row.amount?.formatted() ?? "Invalid amount").monospacedDigit() }
                                Text(row.merchant.isEmpty ? "Description missing" : row.merchant).fontWeight(.medium)
                                if let reason = row.reason { Text(reason).foregroundStyle(row.status == .skipped ? FolioTheme.danger : FolioTheme.warning) }
                                Hairline()
                            }.font(FolioTheme.body(11))
                        }
                    }
                }.frame(minHeight: 200, maxHeight: 360)
                Text("Possible duplicates are based on exact date, description and amount within this file. They remain visible for inspection. Sign-in and a private import backend are required before an import can be committed.").font(FolioTheme.body(11)).foregroundStyle(FolioTheme.secondary).lineSpacing(4)
            } else {
                EmptyState(title: "See the rows before they go anywhere.", detail: "Use a CSV with Date, Description (or Merchant), and Amount columns. Every invalid or duplicate row is shown with a reason.", symbol: "doc.text")
            }
        }.padding(28).frame(width: 700).background(FolioTheme.surface)
            .fileImporter(isPresented: $showPicker, allowedContentTypes: [.commaSeparatedText], allowsMultipleSelection: false) { result in
                do {
                    guard let url = try result.get().first else { return }
                    let access = url.startAccessingSecurityScopedResource()
                    defer { if access { url.stopAccessingSecurityScopedResource() } }
                    let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
                    guard size <= 5_000_000 else { throw CSVPreview.ParseError.oversized }
                    let text = try String(contentsOf: url, encoding: .utf8)
                    rawCSV = text; fileName = url.lastPathComponent; reparse()
                } catch { self.error = error.localizedDescription }
            }
    }
    private func reparse() {
        guard let rawCSV else { return }
        do { preview = try CSVPreview.parse(rawCSV, dateOrder: dateOrder); error = nil }
        catch { self.error = error.localizedDescription; preview = nil }
    }
}
