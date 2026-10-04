import Foundation

/// Monetary values are integer minor units. Decimal is used only at the display boundary.
public struct Money: Codable, Equatable, Hashable, Sendable {
    public let minorUnits: Int64
    public let currency: String
    public init(minorUnits: Int64, currency: String = "NZD") {
        self.minorUnits = minorUnits
        self.currency = currency
    }
    public enum ValidationError: Error { case invalidAmount, currencyMismatch, overflow, invalidPercentage }
    public static func parse(_ text: String, currency: String = "NZD") throws -> Money {
        let raw = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard raw.range(of: #"^[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,2})?$"#, options: .regularExpression) != nil else {
            throw ValidationError.invalidAmount
        }
        let negative = raw.hasPrefix("-")
        let cleaned = raw.replacingOccurrences(of: ",", with: "").replacingOccurrences(of: "-", with: "").replacingOccurrences(of: "+", with: "")
        let parts = cleaned.split(separator: ".", omittingEmptySubsequences: false)
        guard let whole = Int64(parts[0]) else { throw ValidationError.overflow }
        let cents = parts.count == 2 ? Int64(String(parts[1]).padding(toLength: 2, withPad: "0", startingAt: 0))! : 0
        let product = whole.multipliedReportingOverflow(by: 100)
        let sum = product.partialValue.addingReportingOverflow(cents)
        guard !product.overflow, !sum.overflow else { throw ValidationError.overflow }
        return Money(minorUnits: negative ? -sum.partialValue : sum.partialValue, currency: currency)
    }
    public func adding(_ other: Money) throws -> Money {
        guard currency == other.currency else { throw ValidationError.currencyMismatch }
        let sum = minorUnits.addingReportingOverflow(other.minorUnits)
        guard !sum.overflow else { throw ValidationError.overflow }
        return Money(minorUnits: sum.partialValue, currency: currency)
    }
    /// Display preview only. Persisted splits are validated by the server.
    public func split(businessPercent percent: Int64) throws -> (business: Money, personal: Money) {
        guard (0...100).contains(percent) else { throw ValidationError.invalidPercentage }
        let business = (minorUnits / 100) * percent + ((minorUnits % 100) * percent) / 100
        return (Money(minorUnits: business, currency: currency), Money(minorUnits: minorUnits - business, currency: currency))
    }
    public func formatted(explicitCurrency: Bool = false) -> String {
        let formatter = NumberFormatter()
        formatter.locale = Locale(identifier: "en_NZ")
        formatter.numberStyle = .currency
        formatter.currencyCode = currency
        formatter.minimumFractionDigits = 2
        formatter.maximumFractionDigits = 2
        if explicitCurrency { formatter.currencySymbol = "\(currency) " }
        return formatter.string(from: NSDecimalNumber(decimal: Decimal(minorUnits) / 100)) ?? "\(currency) —"
    }
}
