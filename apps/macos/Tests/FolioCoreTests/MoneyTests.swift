import XCTest
@testable import FolioCore

final class MoneyTests: XCTestCase {
    func testDecimalInputUsesExactMinorUnits() throws {
        XCTAssertEqual(try Money.parse("3,412.80").minorUnits, 341_280)
        XCTAssertEqual(try Money.parse("-0.01").minorUnits, -1)
        XCTAssertEqual(try Money.parse("0").minorUnits, 0)
    }
    func testMalformedAmountsNeverBecomeZero() {
        for input in ["", "12.345", "NaN", "1e3", "9,9", "9223372036854775807.01"] {
            XCTAssertThrowsError(try Money.parse(input), input)
        }
    }
    func testCurrencyCannotSilentlyMix() {
        XCTAssertThrowsError(try Money(minorUnits: 100, currency: "NZD").adding(Money(minorUnits: 100, currency: "USD")))
    }
    func testSixtyFortySplitReconcilesMinorUnitRounding() throws {
        let source = Money(minorUnits: 7_999)
        let parts = try source.split(businessPercent: 60)
        XCTAssertEqual(parts.business.minorUnits, 4_799)
        XCTAssertEqual(parts.personal.minorUnits, 3_200)
        XCTAssertEqual(try parts.business.adding(parts.personal), source)
    }
}
