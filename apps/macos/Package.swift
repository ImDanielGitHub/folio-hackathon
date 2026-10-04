// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Folio",
    platforms: [.macOS("26.0")],
    products: [.executable(name: "Folio", targets: ["FolioApp"]), .library(name: "FolioCore", targets: ["FolioCore"])],
    targets: [
        .target(name: "FolioCore"),
        .executableTarget(name: "FolioApp", dependencies: ["FolioCore"], resources: [.process("Resources")]),
        .testTarget(name: "FolioCoreTests", dependencies: ["FolioCore"])
    ],
    swiftLanguageModes: [.v5]
)
