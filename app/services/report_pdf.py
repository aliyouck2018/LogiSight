"""Redesigned PDF report rendering — matches the LogiSight brand sample.

Layout: dark navy cover header (brand block, headline, period, status pill),
KPI card grid with coloured accent bars, finding rows with category chips,
hero highlight cards and a styled operational-alert table.
"""
from __future__ import annotations

import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, NextPageTemplate,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

PAGE_W, PAGE_H = A4
MARGIN = 1.4 * cm
COVER_H = 9.6 * cm

NAVY = colors.HexColor("#0d1b3e")
CYAN = colors.HexColor("#22d3ee")
INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7a90")
MUTED_LIGHT = colors.HexColor("#93a5be")
BORDER = colors.HexColor("#e3e8ef")
CARD_BG = colors.HexColor("#f8fafc")
ZEBRA = colors.HexColor("#fbfcfe")
RED = colors.HexColor("#e5484d")
RED_BG = colors.HexColor("#fdecec")
RED_DEEP = colors.HexColor("#fca5a5")
AMBER = colors.HexColor("#f59e0b")
AMBER_BG = colors.HexColor("#fef6e7")
BLUE = colors.HexColor("#2563eb")
BLUE_BG = colors.HexColor("#edf4fe")
GREEN = colors.HexColor("#059669")
GREEN_BG = colors.HexColor("#e7f6ef")
TEAL = colors.HexColor("#0e7490")

HEADLINES = {
    "executive": "Synthèse des opérations logistiques",
    "shipments": "Performance des expéditions",
    "customs": "Performance douanière",
    "transport": "Performance transport & tournées",
    "warehouse": "Capacité des entrepôts",
}

_TONES = {
    "red": (RED, RED_BG),
    "amber": (AMBER, AMBER_BG),
    "blue": (BLUE, BLUE_BG),
    "green": (GREEN, GREEN_BG),
    "navy": (NAVY, CARD_BG),
}

_BADGE_BY_KEYWORD = [
    ("corridor", "CORRIDOR"),
    ("marchandise", "CARGO"),
    ("véhicule", "FLOTTE"),
    ("entrepôt", "ENTREPÔT"),
    ("volume", "VOLUME"),
    ("sla", "DOUANE"),
    ("douane", "DOUANE"),
]


class _ProgressBar(Flowable):
    """Thin rounded progress bar with a red→amber gradient."""

    def __init__(self, width: float, frac: float, height: float = 6):
        super().__init__()
        self.width = width
        self.height = height
        self.frac = max(0.0, min(1.0, frac))

    def wrap(self, *args):
        return self.width, self.height + 2

    def draw(self):
        c = self.canv
        track = self.width
        h = self.height
        c.setFillColor(colors.HexColor("#e9edf3"))
        c.roundRect(0, 1, track, h, h / 2, stroke=0, fill=1)
        if self.frac <= 0:
            return
        steps = 24
        seg = track * self.frac / steps
        for i in range(steps):
            t = i / max(steps - 1, 1)
            col = colors.Color(
                0.96 - 0.96 * t + t * 0.90,  # r: f59e0b -> e5484d
                0.62 - 0.71 * t,
                0.04 + 0.26 * t,
            )
            c.setFillColor(col)
            c.rect(i * seg, 1, seg + 0.6, h, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.roundRect(0, 1, track, h, h / 2, stroke=1, fill=0)


def _fr(v) -> str:
    """French number formatting: 7877942.89 -> '7 877 942,89'."""
    if v is None:
        return "—"
    if isinstance(v, float) and v == int(v):
        v = int(v)
    if isinstance(v, int):
        return f"{v:,}".replace(",", " ")
    int_part, frac = f"{v:.2f}".split(".")
    whole = f"{int(int_part):,}".replace(",", " ")
    return f"{whole},{frac}".rstrip(",0").rstrip() if frac.rstrip("0") else whole


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _highlight(text: str, color: str) -> str:
    """Bold+colour numbers and percentages inside an escaped string."""
    text = _esc(text)
    text = re.sub(
        r"(\d[\d  ]*(?:[.,]\d+)? ?(?:%|pts?|h\b|j\b|XAF\b|km\b|km/L\b)?)",
        f'<font color="{color}"><b>\\1</b></font>',
        text,
    )
    return text


def _cover(canvas, doc, report: dict):
    """Draw the dark cover header on page 1."""
    canvas.saveState()
    ok = False
    try:
        p = canvas.beginPath()
        p.rect(0, PAGE_H - COVER_H, PAGE_W, COVER_H)
        canvas.clipPath(p, stroke=0, fill=0)
        canvas.linearGradient(0, PAGE_H, PAGE_W * 0.7, PAGE_H - COVER_H,
                              (colors.HexColor("#123a6b"), colors.HexColor("#081226")))
        ok = True
    except Exception:
        ok = False
    finally:
        canvas.restoreState()
    canvas.setFillColor(colors.HexColor("#0a1f43"))
    canvas.rect(0, PAGE_H - COVER_H, PAGE_W, COVER_H, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#0d2450"))
    canvas.rect(0, PAGE_H - COVER_H, PAGE_W, COVER_H, stroke=0, fill=1)
    # subtle diagonal shapes
    canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.03))
    canvas.saveState()
    canvas.translate(PAGE_W * 0.72, PAGE_H)
    canvas.rotate(-24)
    canvas.rect(0, -40, PAGE_W, COVER_H + 200, stroke=0, fill=1)
    canvas.restoreState()
    canvas.setFillColor(colors.Color(0, 0, 0, alpha=0.10))
    canvas.saveState()
    canvas.translate(PAGE_W * 0.60, PAGE_H - COVER_H * 0.15)
    canvas.rotate(-24)
    canvas.rect(0, -40, PAGE_W * 0.9, COVER_H, stroke=0, fill=1)
    canvas.restoreState()

    accent_w = stringWidth("Logi", "Helvetica-Bold", 15)
    # brand block
    canvas.setFillColor(CYAN)
    canvas.roundRect(MARGIN, PAGE_H - 2.15 * cm, 0.62 * cm, 0.6 * cm, 4, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(MARGIN + 0.9 * cm, PAGE_H - 1.98 * cm, "Logi")
    canvas.setFillColor(CYAN)
    canvas.drawString(MARGIN + 0.9 * cm + accent_w, PAGE_H - 1.98 * cm, "Sight")
    canvas.setFillColor(MUTED_LIGHT)
    canvas.setFont("Helvetica-Bold", 6.5)
    canvas.drawString(MARGIN + 0.9 * cm, PAGE_H - 2.4 * cm,
                      "I N T E L L I G E N C E   &   P I L O T A G E   L O G I S T I Q U E")

    # top-right meta
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9.5)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.62 * cm, report["title"])
    canvas.setFillColor(MUTED_LIGHT)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 2.0 * cm, f"Généré le {report['generated_at']}")

    # headline
    headline = HEADLINES.get(_rt := report.get("report_type", "executive"), HEADLINES["executive"])
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 21)
    canvas.drawString(MARGIN, PAGE_H - 4.5 * cm, headline)

    canvas.setFillColor(colors.HexColor("#aebcd4"))
    canvas.setFont("Helvetica", 10.5)
    period = report.get("period_label") or report["period"]
    canvas.drawString(MARGIN, PAGE_H - 5.3 * cm, f"Période analysée : {period}")

    # status pill
    status = report.get("status")
    if status:
        tone, text = status
        txt_color = {"red": RED_DEEP, "amber": colors.HexColor("#fcd34d"),
                     "green": colors.HexColor("#6ee7b7")}.get(tone, RED_DEEP)
        bg = {"red": colors.HexColor("#3b1423"), "amber": colors.HexColor("#3a2a10"),
              "green": colors.HexColor("#0f3a2c")}.get(tone, colors.HexColor("#3b1423"))
        label = f"●  {text}"
        w = stringWidth(label, "Helvetica-Bold", 9) + 26
        h = 22
        x0, y0 = MARGIN, PAGE_H - 5.3 * cm - 34
        canvas.setFillColor(bg)
        canvas.roundRect(x0, y0, w, h, 11, stroke=0, fill=1)
        canvas.setFillColor(txt_color)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(x0 + 13, y0 + (h - 9) / 2 + 1, label)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    try:
        canvas.line(MARGIN, 1.05 * cm, PAGE_W - MARGIN, 1.05 * cm)
    except Exception:
        pass
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(MARGIN, 0.68 * cm, "LogiSight — Plateforme d'intelligence logistique")
    canvas.drawRightString(PAGE_W - MARGIN, 0.68 * cm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _section(text: str) -> list:
    style = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=8.5,
                           textColor=MUTED, leading=12, spaceBefore=6)
    return [Spacer(1, 10), Paragraph(_esc(text).upper(), style), Spacer(1, 5)]


def palette_hex() -> dict:
    """JSON-safe accent palette (hex strings) shared with report payloads."""
    return {"NAVY": "#0d1b3e", "RED": "#e5484d", "GREEN": "#059669",
            "AMBER": "#f59e0b", "BLUE": "#2563eb", "TEAL": "#0e7490"}


def _accent(value) -> colors.HexColor:
    if isinstance(value, str):
        return colors.HexColor(value)
    return value if value is not None else colors.HexColor("#0d1b3e")


def _kpi_card(label: str, value: str, unit: str, accent,
              sub: str = "") -> Table:
    val = Paragraph(
        f'<font size="15" color="#0d1b3e"><b>{_esc(value)}</b></font>'
        + (f' <font size="8" color="#6b7a90">{_esc(unit)}</font>' if unit else ""),
        ParagraphStyle("v", leading=17),
    )
    rows = [
        [Paragraph(_esc(label).upper(), ParagraphStyle(
            "kl", fontName="Helvetica-Bold", fontSize=6.8, textColor=MUTED, leading=9))],
        [val],
    ]
    if sub:
        rows.append([Paragraph(_highlight(sub, "#e5484d"), ParagraphStyle(
            "ks", fontSize=7, textColor=MUTED, leading=9))])
    t = Table(rows, colWidths=[3.45 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, _accent(accent)),
    ]))
    return t


def _kpi_grid(cards: list) -> list:
    if not cards:
        return []
    per_row, gap = 5, 8
    out = []
    # split into rows of `per_row`
    data, chunks = [], []
    chunk = []
    for c in cards:
        chunk.append(c)
        if len(chunk) == per_row:
            chunks.append(chunk)
            chunk = []
    if chunk:
        chunks.append(chunk)
    for ch in chunks:
        widths = [3.45 * cm] * per_row if len(ch) == per_row else [3.45 * cm] * len(ch)
        cells = [_kpi_card(*c) for c in ch]
        while len(cells) < per_row:
            cells.append("")
        t = Table([cells], colWidths=[3.55 * cm] * per_row)
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), gap),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        out.append(t)
    return out


def _chip(text: str, color: colors.HexColor) -> Paragraph:
    return Paragraph(
        _esc(text).upper(),
        ParagraphStyle("chip", fontName="Helvetica-Bold", fontSize=6.6,
                       textColor=colors.white, leading=8.5, alignment=1,
                       backColor=color, borderPadding=(2.5, 5, 3.5, 5),
                       borderRadius=6),
    )


def _finding_row(badge: str, tone: str, text: str) -> Table:
    fg, bg = _TONES.get(tone, _TONES["navy"])
    num_color = "#e5484d" if tone == "red" else "#0d1b3e"
    body = Paragraph(
        _highlight(text, num_color),
        ParagraphStyle("f", fontSize=9, leading=13, textColor=INK),
    )
    t = Table([[ _chip(badge, fg), body ]], colWidths=[2.55 * cm, 15.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 8),
        ("LEFTPADDING", (1, 0), (1, 0), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _hero_card(label: str, big: str, caption: Flowable | str, tone: str,
               bar: float | None = None) -> Table:
    fg, bg = _TONES.get(tone, _TONES["red"])
    rows = [[Paragraph(_esc(label).upper(), ParagraphStyle(
        "hl", fontName="Helvetica-Bold", fontSize=7.2, textColor=MUTED, leading=10))]]
    if bar is not None:
        rows.append([_ProgressBar(4.6 * cm, bar)])
    rows.append([
        Paragraph(f'<font size="18" color="#{fg.hexval()[2:]}"><b>{_esc(big)}</b></font>',
                  ParagraphStyle("hv", leading=20)),
    ])
    if caption:
        rows.append([caption])
    t = Table(rows, colWidths=[5.3 * cm])
    st = [
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, fg),
    ]
    t.setStyle(TableStyle(st))
    return t


def _alert_table(alerts: list) -> Table | None:
    if not alerts:
        return None
    sev_map = {"CRITICAL": (RED, RED_BG), "HIGH": (RED, RED_BG),
               "WARNING": (AMBER, AMBER_BG), "MEDIUM": (AMBER, AMBER_BG),
               "INFO": (BLUE, BLUE_BG), "OPEN": (RED, RED_BG)}
    head = [
        Paragraph("SÉVÉRITÉ", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=6.8, textColor=MUTED)),
        Paragraph("ALERTE", ParagraphStyle("th2", fontName="Helvetica-Bold", fontSize=6.8, textColor=MUTED)),
        Paragraph("DÉTAIL", ParagraphStyle("th3", fontName="Helvetica-Bold", fontSize=6.8, textColor=MUTED)),
    ]
    data = [head]
    cmds = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, a in enumerate(alerts, start=1):
        sev = (a.get("severity") or "INFO").upper()
        fg, _bg = sev_map.get(sev, (BLUE, BLUE_BG))
        title = Paragraph(f'<b>{_esc(a.get("title") or "")}</b>',
                          ParagraphStyle("at", fontSize=8.8, leading=12, textColor=INK))
        desc = Paragraph(_highlight(a.get("description") or "", "#0d1b3e"),
                         ParagraphStyle("ad", fontSize=8.3, leading=11.5, textColor=colors.HexColor("#3b4757")))
        data.append([_chip(sev, fg), title, desc])
        cmds += [("LINEBEFORE", (0, i), (0, i), 2.5, sev_map.get(sev, (BLUE,))[0])]
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t = Table(data, colWidths=[2.5 * cm, 6.2 * cm, 9.2 * cm], repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def build_pdf(report: dict) -> bytes:
    """Render the full brand-styled PDF; returns raw bytes."""
    buf = io.BytesIO()

    class _Doc(BaseDocTemplate):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            cover_frame = Frame(MARGIN, 1.1 * cm, PAGE_W - 2 * MARGIN,
                                PAGE_H - COVER_H - 1.1 * cm, id="coverf",
                                leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            body_frame = Frame(MARGIN, 1.35 * cm, PAGE_W - 2 * MARGIN,
                               PAGE_H - 1.35 * cm - 1.35 * cm, id="bodyf",
                               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            self.addPageTemplates([
                PageTemplate(id="cover", frames=[cover_frame], onPage=lambda c, d: _cover(c, d, report)),
                PageTemplate(id="body", frames=[body_frame], onPage=_footer),
            ])

    doc = _Doc(buf, pagesize=A4, title=report["title"], author="LogiSight")
    story = [NextPageTemplate("body")]

    # KPI cards
    story += _section("Indicateurs clés")
    raw_cards = report.get("kpi_cards")
    if raw_cards:
        cards = [(c["label"], _fr(c.get("value")), c.get("unit", ""),
                  c.get("accent", NAVY), c.get("sub", "")) for c in raw_cards]
    else:
        cards = [(k["label"], k["value"], k.get("unit", "") or
                  ("" if str(k["value"]).endswith(k.get("unit", "§")) else ""), NAVY, "")
                 for k in report["kpis"]]
    story += _kpi_grid(cards)

    # findings
    story += _section("Constats clés")
    rich = report.get("findings_rich") or [{"badge": "CONSTAT", "tone": "blue", "text": f}
                                           for f in report["findings"]]
    for item in rich:
        story += [_finding_row(item.get("badge", "CONSTAT"), item.get("tone", "blue"),
                               item.get("text", "")), Spacer(1, 7)]

    # hero highlights
    heroes = report.get("highlights") or []
    if heroes:
        row_cells = []
        for h in heroes:
            fg, bg = _TONES.get(h["tone"], _TONES["red"])
            caption = Paragraph(_esc(h["caption"]), ParagraphStyle(
                "hc", fontSize=7.6, leading=10.5, textColor=MUTED))
            row_cells.append(_hero_card(h["label"], h["big"], caption,
                                        h.get("tone", "red"), h.get("bar")))
        if len(row_cells) == 1:
            story += [Spacer(1, 6), row_cells[0], Spacer(1, 6)]
        else:
            t = Table([row_cells], colWidths=[5.5 * cm] * len(row_cells), hAlign="LEFT")
            t.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story += [Spacer(1, 6), t, Spacer(1, 6)]

    # alerts
    alert_tbl = _alert_table(report["alerts"])
    if alert_tbl:
        story += _section("Alertes opérationnelles")
        story += [alert_tbl, Spacer(1, 8)]

    doc.build(story)
    return buf.getvalue()
