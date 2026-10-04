import Foundation

public enum CSVDateOrder: String, CaseIterable, Identifiable, Sendable {
    case iso, dayFirst, monthFirst
    public var id: String { rawValue }
    public var title: String { switch self { case .iso: return "Year–month–day"; case .dayFirst: return "Day/month/year"; case .monthFirst: return "Month/day/year" } }
}
public struct CSVPreviewRow: Identifiable, Sendable {
    public enum Status: String, Sendable { case accepted, duplicate, skipped }
    public let id: Int
    public let original: [String]
    public let date: String?
    public let merchant: String
    public let amount: Money?
    public let status: Status
    public let reason: String?
}
public struct CSVPreview: Sendable {
    public let headers: [String]
    public let rows: [CSVPreviewRow]
    public var accepted: [CSVPreviewRow] { rows.filter { $0.status == .accepted } }
    public enum ParseError: LocalizedError {
        case missingHeaders, malformedQuotes, oversized
        public var errorDescription: String? {
            switch self {
            case .missingHeaders: return "The file needs Date, Description (or Merchant), and Amount columns. No rows were imported."
            case .malformedQuotes: return "The CSV contains an unclosed quoted field. No rows were imported."
            case .oversized: return "Preview supports CSV files up to 5 MB. Split the export into smaller files."
            }
        }
    }
    /// Local-only preview. This function performs no upload, persistence or financial annotation.
    public static func parse(_ text: String, dateOrder: CSVDateOrder?, currency: String = "NZD") throws -> CSVPreview {
        guard text.utf8.count <= 5_000_000 else { throw ParseError.oversized }
        let records = try tokenize(text)
        guard let header = records.first else { throw ParseError.missingHeaders }
        let names = header.map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased().replacingOccurrences(of: "\u{FEFF}", with: "") }
        guard let dateColumn = names.firstIndex(of: "date"),
              let merchantColumn = names.firstIndex(where: { ["description", "merchant"].contains($0) }),
              let amountColumn = names.firstIndex(of: "amount") else { throw ParseError.missingHeaders }
        var seen = Set<String>()
        let rows = records.dropFirst().enumerated().compactMap { index, fields -> CSVPreviewRow? in
            guard !fields.allSatisfy({ $0.trimmingCharacters(in: .whitespaces).isEmpty }) else { return nil }
            let field: (Int) -> String = { $0 < fields.count ? fields[$0].trimmingCharacters(in: .whitespacesAndNewlines) : "" }
            let merchant = field(merchantColumn)
            let date = parseDate(field(dateColumn), order: dateOrder)
            let money = try? Money.parse(field(amountColumn), currency: currency)
            var reason: String?
            if fields.count != header.count { reason = "Column count differs from the header." }
            else if date == nil { reason = "Choose a date interpretation or correct this invalid date." }
            else if merchant.isEmpty { reason = "Description is missing." }
            else if money == nil { reason = "Amount is invalid; it has not been treated as zero." }
            var status: CSVPreviewRow.Status = reason == nil ? .accepted : .skipped
            if let date, let money, reason == nil {
                let identity = "\(date)|\(merchant.lowercased())|\(money.minorUnits)|\(currency)"
                if seen.contains(identity) { status = .duplicate; reason = "Same date, description and amount in this file. Review before import." }
                seen.insert(identity)
            }
            return CSVPreviewRow(id: index + 2, original: fields, date: date, merchant: merchant, amount: money, status: status, reason: reason)
        }
        return CSVPreview(headers: header, rows: rows)
    }
    private static func parseDate(_ value: String, order: CSVDateOrder?) -> String? {
        let format: String
        if value.range(of: #"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"#, options: .regularExpression) != nil { format = "yyyy-MM-dd" }
        else { switch order { case .dayFirst: format = "dd/MM/yyyy"; case .monthFirst: format = "MM/dd/yyyy"; default: return nil } }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.isLenient = false
        formatter.dateFormat = format
        guard let date = formatter.date(from: value), formatter.string(from: date) == value else { return nil }
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
    private static func tokenize(_ text: String) throws -> [[String]] {
        var rows: [[String]] = [], row: [String] = [], field = ""
        var quoted = false, previousCR = false
        let characters = Array(text)
        var index = 0
        while index < characters.count {
            let character = characters[index]
            if character == "\"" {
                if quoted, index + 1 < characters.count, characters[index + 1] == "\"" { field.append("\""); index += 1 }
                else { quoted.toggle() }
            } else if !quoted, character == "," { row.append(field); field = "" }
            else if !quoted, character == "\r\n" || character == "\n" || character == "\r" {
                if !(previousCR && character == "\n") { row.append(field); rows.append(row); row = []; field = "" }
            } else { field.append(character) }
            previousCR = !quoted && character == "\r"
            index += 1
        }
        guard !quoted else { throw ParseError.malformedQuotes }
        if !field.isEmpty || !row.isEmpty { row.append(field); rows.append(row) }
        return rows
    }
}
