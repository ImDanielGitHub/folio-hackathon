import XCTest
@testable import FolioCore

final class CSVPreviewTests: XCTestCase {
    func testAmbiguousDateNeedsChosenInterpretation() throws {
        let csv = "Date,Description,Amount\n03/04/2026,Phone,-79.99"
        let unresolved = try CSVPreview.parse(csv, dateOrder: nil)
        XCTAssertEqual(unresolved.accepted.count, 0)
        XCTAssertTrue(unresolved.rows[0].reason?.contains("date") == true)
        let confirmed = try CSVPreview.parse(csv, dateOrder: .dayFirst)
        XCTAssertEqual(confirmed.accepted[0].date, "2026-04-03")
    }
    func testQuotedMerchantAndDuplicateRowsArePreserved() throws {
        let csv = "Date,Description,Amount\r\n2026-09-01,\"Corner, Cafe\",-12.40\r\n2026-09-01,\"Corner, Cafe\",-12.40"
        let preview = try CSVPreview.parse(csv, dateOrder: .iso)
        XCTAssertEqual(preview.rows.count, 2)
        XCTAssertEqual(preview.accepted.count, 1)
        XCTAssertEqual(preview.rows[0].merchant, "Corner, Cafe")
        XCTAssertEqual(preview.rows[1].status, .duplicate)
    }
    func testInvalidDateAndAmountAreNeverSilentlyCoerced() throws {
        let csv = "Date,Description,Amount\n2026-02-31,Cafe,-4.20\n2026-09-02,Cafe,nope"
        let preview = try CSVPreview.parse(csv, dateOrder: .iso)
        XCTAssertTrue(preview.accepted.isEmpty)
        XCTAssertEqual(preview.rows.count, 2)
        XCTAssertTrue(preview.rows.allSatisfy { $0.reason != nil })
    }
    func testUnclosedQuotesAreRejected() {
        XCTAssertThrowsError(try CSVPreview.parse("Date,Description,Amount\n2026-09-01,\"Cafe,-3", dateOrder: .iso))
    }
}
