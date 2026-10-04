import XCTest
@testable import FolioCore

final class DemoContractTests: XCTestCase {
    func testComparisonKeepsIntegerAmountsAndCalculationSource() throws {
        let json = #"{"calculationId":"compare:demo:1:personal:NZD:2026-08:2026-09","currency":"NZD","scope":"personal","previousPeriod":"2026-08","currentPeriod":"2026-09","previousMinor":301610,"currentMinor":341280,"differenceMinor":39670,"rows":[],"sourceIds":["source-a"]}"#
        let wire = try JSONDecoder().decode(DemoComparisonDTO.self, from: Data(json.utf8))
        let value = try XCTUnwrap(wire.domain)
        XCTAssertEqual(value.current.minorUnits, 341_280)
        XCTAssertEqual(value.delta.minorUnits, 39_670)
        XCTAssertEqual(value.sourceIDs, ["source-a"])
        XCTAssertEqual(value.scope, .personal)
    }
    func testMissingPeriodIsNotMappedToZero() throws {
        let json = #"{"calculationId":"missing","currency":"NZD","scope":"personal","previousPeriod":"2026-08","currentPeriod":"2026-09","previousMinor":null,"currentMinor":null,"differenceMinor":null,"rows":[],"sourceIds":[]}"#
        let wire = try JSONDecoder().decode(DemoComparisonDTO.self, from: Data(json.utf8))
        XCTAssertNil(wire.domain)
    }
    func testMissingGoalCoverageIsNotMeasuredZero() throws {
        let json = #"{"id":"goal-1","title":"Eating out","currency":"NZD","scope":"personal","period":"month","status":"active","limitMinor":30000,"spentMinor":0,"progressNote":"No October transactions imported yet."}"#
        let goal = try JSONDecoder().decode(DemoGoalDTO.self, from: Data(json.utf8)).domain
        XCTAssertNil(goal.current)
        XCTAssertEqual(goal.target.minorUnits, 30_000)
    }
    func testPlaintextRemoteServerAndCredentialURLsAreRejected() {
        for address in ["http://example.com", "https://user:secret@example.com", "file:///tmp/data", "https://example.com?api_key=secret"] {
            XCTAssertThrowsError(try HTTPFolioService(baseURL: address))
        }
        XCTAssertNoThrow(try HTTPFolioService(baseURL: "http://127.0.0.1:8000"))
        XCTAssertNoThrow(try HTTPFolioService(baseURL: "https://folio.example.com"))
    }
    func testScopeFilteringKeepsMixedAllocationsInspectable() {
        let transaction = Transaction(id: "t", date: "2026-09-01", merchant: "Phone", description: "Synthetic", category: "Phone", purpose: "mixed", amount: Money(minorUnits: -7_999), account: "Demo", needsReview: false, version: 1, sourceID: "s", businessPercent: 60)
        XCTAssertTrue(transaction.matches(scope: .personal))
        XCTAssertTrue(transaction.matches(scope: .business))
    }
}
