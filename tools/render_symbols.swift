// Renders SF Symbols as vector PDFs (one page per symbol) using the system symbol
// renderer (SwiftUI ImageRenderer keeps the outlines as vector paths).
// Usage: render_symbols <names.txt> <out-dir> <pointSize>
// Writes <out-dir>/{monochrome,hierarchical,multicolor}.pdf; page i = line i of names.txt.
// A symbol the system does not know becomes an empty 1x1 page.
import AppKit
import SwiftUI

@MainActor
func render(names: [String], mode: String, to url: URL, size: CGFloat) {
    var box = CGRect(x: 0, y: 0, width: 1, height: 1)
    guard let ctx = CGContext(url as CFURL, mediaBox: &box, nil) else { fatalError("no PDF context") }
    for name in names {
        guard NSImage(systemSymbolName: name, accessibilityDescription: nil) != nil else {
            var empty = CGRect(x: 0, y: 0, width: 1, height: 1)
            ctx.beginPage(mediaBox: &empty)
            ctx.endPage()
            continue
        }
        let base = Image(systemName: name).font(.system(size: size, weight: .regular))
        let view: AnyView
        switch mode {
        case "hierarchical":
            view = AnyView(base.symbolRenderingMode(.hierarchical).foregroundStyle(Color.black))
        case "multicolor":
            view = AnyView(base.symbolRenderingMode(.multicolor).foregroundStyle(Color.black))
        default:
            view = AnyView(base.symbolRenderingMode(.monochrome).foregroundStyle(Color.black))
        }
        let renderer = ImageRenderer(content: view.environment(\.colorScheme, .light))
        renderer.render { sz, draw in
            var page = CGRect(origin: .zero, size: sz)
            ctx.beginPage(mediaBox: &page)
            draw(ctx)
            ctx.endPage()
        }
    }
    ctx.closePDF()
}

let args = CommandLine.arguments
guard args.count == 4, let size = Double(args[3]) else {
    FileHandle.standardError.write("usage: render_symbols <names.txt> <out-dir> <pointSize>\n".data(using: .utf8)!)
    exit(2)
}
let names = try! String(contentsOfFile: args[1], encoding: .utf8).split(separator: "\n").map(String.init)
MainActor.assumeIsolated {
    for mode in ["monochrome", "hierarchical", "multicolor"] {
        render(names: names, mode: mode, to: URL(fileURLWithPath: args[2]).appendingPathComponent("\(mode).pdf"), size: CGFloat(size))
    }
}
