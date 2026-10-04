import AppKit
import SwiftUI
import CoreText

/// Paper component-library tokens. Explicit light/dark variants; never inferred from model output.
enum FolioTheme {
    static let canvas = adaptive("F6F6F4", "121413")
    static let surface = adaptive("FFFFFF", "1A1D1C")
    static let sunken = adaptive("F0F0EE", "202422")
    static let border = adaptive("E6E6E2", "2A2E2C")
    static let ink = adaptive("1C1F1E", "ECEDEA")
    static let secondary = adaptive("5C625F", "A8AEAA")
    static let accent = adaptive("1F4D3F", "8CC3AC")
    static let selection = adaptive("F2F3F1", "252A27")
    static let success = adaptive("2E6B4F", "8CC3AC")
    static let warning = adaptive("9A5B12", "E4B571")
    static let danger = adaptive("C2413A", "F3978D")
    static let sidebarWidth: CGFloat = 212
    static let inspectorWidth: CGFloat = 340
    static func body(_ size: CGFloat = 14, weight: Font.Weight = .regular) -> Font {
        .custom("Inter", size: size).weight(weight)
    }
    static func headline(_ size: CGFloat = 28) -> Font { .custom("Newsreader", size: size) }
    private static func adaptive(_ light: String, _ dark: String) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let hex = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
            let value = UInt64(hex, radix: 16)!
            return NSColor(srgbRed: CGFloat((value >> 16) & 255) / 255, green: CGFloat((value >> 8) & 255) / 255, blue: CGFloat(value & 255) / 255, alpha: 1)
        })
    }
    static func registerFonts() {
        for ext in ["ttf", "otf"] {
            for url in Bundle.module.urls(forResourcesWithExtension: ext, subdirectory: nil) ?? [] {
                CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
            }
        }
    }
}

struct FolioButtonStyle: ButtonStyle {
    var primary = false
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(FolioTheme.body(12, weight: .medium))
            .foregroundStyle(primary ? FolioTheme.surface : FolioTheme.ink)
            .padding(.horizontal, 12)
            .frame(minHeight: 32)
            .background(primary ? FolioTheme.accent : FolioTheme.surface)
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(primary ? .clear : FolioTheme.border, lineWidth: 1))
            .opacity(configuration.isPressed ? 0.72 : 1)
    }
}
struct Hairline: View {
    var body: some View { Rectangle().fill(FolioTheme.border).frame(height: 1).accessibilityHidden(true) }
}
struct SectionHeading: View {
    let title: String
    var detail: String? = nil
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(FolioTheme.body(18, weight: .semibold)).foregroundStyle(FolioTheme.ink)
            if let detail { Text(detail).font(FolioTheme.body(12)).foregroundStyle(FolioTheme.secondary) }
        }
    }
}
struct StatusLine: View {
    let text: String
    var symbol = "info.circle"
    var tone: Color = FolioTheme.secondary
    var body: some View {
        Label(text, systemImage: symbol).font(FolioTheme.body(12)).foregroundStyle(tone).fixedSize(horizontal: false, vertical: true)
    }
}
struct EmptyState: View {
    let title: String
    let detail: String
    var symbol = "tray"
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Image(systemName: symbol).font(.system(size: 22, weight: .light)).foregroundStyle(FolioTheme.secondary)
            Text(title).font(FolioTheme.headline(28)).foregroundStyle(FolioTheme.ink)
            Text(detail).font(FolioTheme.body()).foregroundStyle(FolioTheme.secondary).lineSpacing(5)
        }.frame(maxWidth: 520, alignment: .leading).padding(.vertical, 32)
    }
}
