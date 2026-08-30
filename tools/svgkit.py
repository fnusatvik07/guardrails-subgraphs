"""Tiny SVG helper used to draw the class diagrams. No third-party deps."""

INK = "#1b2430"
MUTED = "#64748b"
LINE = "#cbd5e1"
PANEL = "#f7f9fc"
WHITE = "#ffffff"
BLUE = "#2563eb"
BLUE_SOFT = "#e8effd"
RED = "#c0392b"
RED_SOFT = "#fdecea"
GREEN = "#2f7d4f"
GREEN_SOFT = "#e8f5ee"
AMBER = "#b45309"
AMBER_SOFT = "#fdf3e3"
VIOLET = "#6d28d9"
VIOLET_SOFT = "#f0eafc"

FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
MONO = "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"


class Svg:
    def __init__(self, w, h, bg=WHITE):
        self.w, self.h = w, h
        self.parts = []
        self.bg = bg

    def add(self, s):
        self.parts.append(s)
        return self

    # ---------- primitives ----------
    def rect(self, x, y, w, h, fill=WHITE, stroke=LINE, r=10, sw=1.5, dash=None, op=1.0):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return self.add(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" ry="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"{d}/>'
        )

    def text(self, x, y, s, size=13, fill=INK, weight="400", anchor="middle",
             font=None, ls="0", op=1.0):
        font = font or FONT
        s = (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        return self.add(
            f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{ls}" opacity="{op}">{s}</text>'
        )

    def line(self, x1, y1, x2, y2, stroke=LINE, sw=1.5, dash=None, cap="round"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return self.add(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="{cap}"{d}/>'
        )

    def path(self, d, stroke=LINE, fill="none", sw=1.5, dash=None, marker=None):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        mk = f' marker-end="url(#{marker})"' if marker else ""
        return self.add(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round"{da}{mk}/>'
        )

    def arrow(self, x1, y1, x2, y2, stroke=MUTED, sw=1.6, dash=None, marker="arw"):
        return self.path(f"M {x1} {y1} L {x2} {y2}", stroke=stroke, sw=sw, dash=dash, marker=marker)

    def circle(self, cx, cy, r, fill=WHITE, stroke=LINE, sw=1.5):
        return self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    # ---------- composites ----------
    def box(self, x, y, w, h, title, sub=None, fill=WHITE, stroke=LINE, accent=None,
            tsize=14, ssize=11.5, r=12, mono=False, tweight="600"):
        self.rect(x, y, w, h, fill=fill, stroke=stroke, r=r)
        if accent:
            self.add(
                f'<path d="M {x+r} {y} L {x+w-r} {y} A {r} {r} 0 0 1 {x+w} {y+r} L {x+w} {y+4} '
                f'L {x} {y+4} L {x} {y+r} A {r} {r} 0 0 1 {x+r} {y}Z" fill="{accent}"/>'
            )
        cx = x + w / 2
        if sub:
            self.text(cx, y + h / 2 - 3, title, size=tsize, weight=tweight,
                      font=MONO if mono else FONT)
            self.text(cx, y + h / 2 + 15, sub, size=ssize, fill=MUTED)
        else:
            self.text(cx, y + h / 2 + tsize * 0.36, title, size=tsize, weight=tweight,
                      font=MONO if mono else FONT)
        return self

    def title(self, x, y, main, sub=None, anchor="start"):
        self.text(x, y, main, size=19, weight="700", anchor=anchor, ls="-0.2")
        if sub:
            self.text(x, y + 22, sub, size=13, fill=MUTED, anchor=anchor)
        return self

    def chip(self, x, y, label, fill=BLUE_SOFT, stroke=BLUE, txt=None, size=11, pad=11, h=22):
        w = len(label) * size * 0.60 + pad * 2
        self.rect(x, y, w, h, fill=fill, stroke=stroke, r=h / 2, sw=1.2)
        self.text(x + w / 2, y + h / 2 + size * 0.35, label, size=size,
                  fill=txt or stroke, weight="600")
        return w

    def tick(self, x, y, col=GREEN, sw=2.0):
        """Small drawn check mark, baseline-anchored near (x, y)."""
        return self.path(f"M {x} {y-4} L {x+4} {y} L {x+11} {y-9}", stroke=col, sw=sw)

    def cross(self, x, y, col=RED, sw=2.0):
        """Small drawn x mark, baseline-anchored near (x, y)."""
        self.path(f"M {x} {y-9} L {x+9} {y}", stroke=col, sw=sw)
        return self.path(f"M {x+9} {y-9} L {x} {y}", stroke=col, sw=sw)

    def render(self):
        defs = f'''<defs>
  <marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 1 L 9 5 L 0 9 z" fill="{MUTED}"/>
  </marker>
  <marker id="arwR" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 1 L 9 5 L 0 9 z" fill="{RED}"/>
  </marker>
  <marker id="arwG" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 1 L 9 5 L 0 9 z" fill="{GREEN}"/>
  </marker>
  <marker id="arwB" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 1 L 9 5 L 0 9 z" fill="{BLUE}"/>
  </marker>
  <marker id="arwV" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 1 L 9 5 L 0 9 z" fill="{VIOLET}"/>
  </marker>
</defs>'''
        body = "\n  ".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img">\n{defs}\n'
                f'  <rect width="{self.w}" height="{self.h}" fill="{self.bg}"/>\n  {body}\n</svg>\n')

    def save(self, path):
        with open(path, "w") as f:
            f.write(self.render())
        print("wrote", path)
