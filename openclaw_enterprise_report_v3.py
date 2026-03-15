#!/usr/bin/env python3
"""
qqlaw Enterprise Architecture Report — v4
Merges OpenClaw's channel-first architecture + Claude Code's minimalist agentic philosophy
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.graphics.charts.barcharts import VerticalBarChart
import os
from datetime import datetime

OUTPUT_PATH = os.path.expanduser("~/.openclaw/workspace/OpenClaw_Enterprise_Architecture_Report.pdf")

# ── Colors ──
ACCENT_BLUE = HexColor("#0f3460")
ACCENT_TEAL = HexColor("#16a085")
ACCENT_RED = HexColor("#c0392b")
ACCENT_ORANGE = HexColor("#e67e22")
ACCENT_GREEN = HexColor("#27ae60")
ACCENT_PURPLE = HexColor("#8e44ad")
LIGHT_GRAY = HexColor("#f5f5f5")
MED_GRAY = HexColor("#bdc3c7")
DARK_GRAY = HexColor("#2c3e50")
QUANTIPHI_BLUE = HexColor("#003366")
BAIONIQ_PURPLE = HexColor("#6c3483")
QQ_BLUE = HexColor("#1565c0")
QQ_DARK = HexColor("#0d47a1")
CC_AMBER = HexColor("#f57f17")  # Claude Code gold
CC_BROWN = HexColor("#795548")

styles = getSampleStyleSheet()

title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=28, leading=34, textColor=ACCENT_BLUE, spaceAfter=6, alignment=TA_CENTER)
subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=14, leading=18, textColor=DARK_GRAY, alignment=TA_CENTER, spaceAfter=20)
h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=20, leading=24, textColor=ACCENT_BLUE, spaceBefore=24, spaceAfter=12)
h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=16, leading=20, textColor=DARK_GRAY, spaceBefore=16, spaceAfter=8)
h3_style = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=13, leading=17, textColor=ACCENT_PURPLE, spaceBefore=12, spaceAfter=6)
body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10.5, leading=15, textColor=black, alignment=TA_JUSTIFY, spaceAfter=8)
bullet_style = ParagraphStyle('Bullet', parent=body_style, leftIndent=20, bulletIndent=10, spaceAfter=4)
callout_style = ParagraphStyle('Callout', parent=body_style, fontSize=10, leading=14, textColor=DARK_GRAY, leftIndent=15, rightIndent=15, spaceBefore=8, spaceAfter=8, backColor=HexColor("#eaf2f8"), borderWidth=1, borderColor=ACCENT_BLUE, borderPadding=8)
callout_amber = ParagraphStyle('CalloutAmber', parent=body_style, fontSize=10, leading=14, textColor=DARK_GRAY, leftIndent=15, rightIndent=15, spaceBefore=8, spaceAfter=8, backColor=HexColor("#fff8e1"), borderWidth=1, borderColor=CC_AMBER, borderPadding=8)
callout_green = ParagraphStyle('CalloutGreen', parent=body_style, fontSize=10, leading=14, textColor=DARK_GRAY, leftIndent=15, rightIndent=15, spaceBefore=8, spaceAfter=8, backColor=HexColor("#e8f5e9"), borderWidth=1, borderColor=ACCENT_GREEN, borderPadding=8)
code_style = ParagraphStyle('Code', parent=styles['Code'], fontSize=8.5, leading=11, textColor=HexColor("#2c3e50"), backColor=HexColor("#f8f9fa"), borderWidth=0.5, borderColor=MED_GRAY, borderPadding=6, leftIndent=10, rightIndent=10, spaceAfter=8)
caption_style = ParagraphStyle('Caption', parent=styles['Normal'], fontSize=9, leading=12, textColor=DARK_GRAY, alignment=TA_CENTER, spaceBefore=4, spaceAfter=12, italic=True)

def hr():
    return HRFlowable(width="100%", thickness=1, color=MED_GRAY, spaceBefore=6, spaceAfter=6)

def draw_box(d, x, y, w, h, color, label, font_size=8, text_color=white):
    d.add(Rect(x, y, w, h, fillColor=color, strokeColor=HexColor("#444444"), strokeWidth=0.75, rx=5, ry=5))
    lines = label.split('\n')
    total_h = len(lines) * (font_size + 2)
    start_y = y + h/2 + total_h/2 - font_size
    for i, line in enumerate(lines):
        d.add(String(x + w/2, start_y - i*(font_size+2), line, fontSize=font_size, fillColor=text_color, textAnchor='middle', fontName='Helvetica-Bold'))

def arrow_down(d, x1, y1, x2, y2, c=DARK_GRAY):
    d.add(Line(x1, y1, x2, y2, strokeColor=c, strokeWidth=1.2))
    d.add(Polygon(points=[x2-3.5, y2+5, x2+3.5, y2+5, x2, y2], fillColor=c, strokeColor=c))

def arrow_right(d, x1, y1, x2, y2, c=DARK_GRAY):
    d.add(Line(x1, y1, x2, y2, strokeColor=c, strokeWidth=1.2))
    d.add(Polygon(points=[x2-5, y2-3.5, x2-5, y2+3.5, x2, y2], fillColor=c, strokeColor=c))

def label_text(d, x, y, text, size=7, color=DARK_GRAY, font='Helvetica', anchor='middle'):
    d.add(String(x, y, text, fontSize=size, fillColor=color, textAnchor=anchor, fontName=font))

# ═══════════════════════════════════════════════
# DIAGRAMS
# ═══════════════════════════════════════════════

def diag_cover():
    d = Drawing(460, 90)
    draw_box(d, 5, 25, 90, 45, ACCENT_BLUE, "OpenClaw\nChannel-First\nGateway", 8)
    draw_box(d, 125, 25, 90, 45, CC_AMBER, "Claude Code\nMinimalist\nAgentic Loop", 8, black)
    draw_box(d, 245, 25, 90, 45, QQ_BLUE, "qqlaw\nEnterprise\nArchitecture", 8)
    draw_box(d, 365, 25, 90, 45, BAIONIQ_PURPLE, "Baioniq\nPlatform\nIntegration", 8)
    arrow_right(d, 95, 47, 125, 47, ACCENT_TEAL)
    arrow_right(d, 215, 47, 245, 47, ACCENT_TEAL)
    arrow_right(d, 335, 47, 365, 47, ACCENT_TEAL)
    label_text(d, 110, 12, "inspires", 6.5, ACCENT_TEAL, 'Helvetica-Oblique')
    label_text(d, 230, 12, "becomes", 6.5, ACCENT_TEAL, 'Helvetica-Oblique')
    label_text(d, 350, 12, "integrates", 6.5, ACCENT_TEAL, 'Helvetica-Oblique')
    return d

def diag_gateway():
    d = Drawing(480, 225)
    label_text(d, 240, 213, "OpenClaw Gateway Architecture", 11, ACCENT_BLUE, 'Helvetica-Bold')
    # Channels layer
    d.add(Rect(15, 168, 450, 32, fillColor=HexColor("#e8f5e9"), strokeColor=ACCENT_GREEN, strokeWidth=0.75, rx=4))
    label_text(d, 240, 184, "Messaging Channels", 8, ACCENT_GREEN, 'Helvetica-Bold')
    for i, ch in enumerate(["WhatsApp", "Telegram", "Discord", "Slack", "Signal", "iMessage", "Teams", "IRC"]):
        label_text(d, 30 + i*55, 172, ch, 6.5, DARK_GRAY, 'Helvetica')
    arrow_down(d, 240, 168, 240, 155)
    # Gateway
    d.add(Rect(55, 103, 370, 48, fillColor=ACCENT_BLUE, strokeColor=HexColor("#0a2540"), strokeWidth=1, rx=5))
    label_text(d, 240, 134, "Gateway Control Plane", 10, white, 'Helvetica-Bold')
    label_text(d, 240, 121, "WebSocket Server  ·  Session Router  ·  Event Bus  ·  Cron", 7, HexColor("#bbdefb"))
    label_text(d, 240, 109, "ws://127.0.0.1:18789  ·  JSON Schema  ·  Idempotent Ops", 6.5, HexColor("#90caf9"), 'Helvetica-Oblique')
    # Components
    for ax in [100, 240, 380]:
        arrow_down(d, ax, 103, ax, 90)
    draw_box(d, 30, 53, 140, 34, ACCENT_TEAL, "Agent Runtime (Pi RPC)\nTool Exec · Streaming", 7)
    draw_box(d, 180, 53, 120, 34, ACCENT_PURPLE, "Session Store\nDM Scoping · JSONL", 7)
    draw_box(d, 310, 53, 140, 34, ACCENT_ORANGE, "Skills Platform\nClawHub · Plugins", 7)
    # Clients
    d.add(Rect(15, 8, 450, 28, fillColor=HexColor("#fce4ec"), strokeColor=ACCENT_RED, strokeWidth=0.75, rx=4))
    label_text(d, 240, 18, "Clients:  CLI · Web UI · macOS App · iOS/Android Nodes · WebChat", 7.5, DARK_GRAY)
    arrow_down(d, 240, 53, 240, 39)
    return d

def diag_agentic_loop():
    """Claude Code's agentic loop — the minimalist philosophy."""
    d = Drawing(480, 145)
    label_text(d, 240, 133, "Claude Code — The Agentic Loop (Minimalist Philosophy)", 11, CC_AMBER, 'Helvetica-Bold')
    # Three phases
    draw_box(d, 20, 60, 120, 50, HexColor("#fff3e0"), "① Gather Context\nRead files · Search\nExplore codebase", 8, black)
    draw_box(d, 175, 60, 120, 50, HexColor("#fff3e0"), "② Take Action\nEdit files · Run cmds\nCreate · Refactor", 8, black)
    draw_box(d, 330, 60, 120, 50, HexColor("#fff3e0"), "③ Verify Results\nRun tests · Compare\nCheck output", 8, black)
    arrow_right(d, 140, 85, 175, 85, CC_AMBER)
    arrow_right(d, 295, 85, 330, 85, CC_AMBER)
    # Feedback loop arrow (back from verify to gather)
    d.add(Line(390, 60, 390, 42, strokeColor=CC_AMBER, strokeWidth=1, strokeDashArray=[3,2]))
    d.add(Line(390, 42, 80, 42, strokeColor=CC_AMBER, strokeWidth=1, strokeDashArray=[3,2]))
    d.add(Line(80, 42, 80, 60, strokeColor=CC_AMBER, strokeWidth=1, strokeDashArray=[3,2]))
    d.add(Polygon(points=[76.5, 55, 83.5, 55, 80, 60], fillColor=CC_AMBER, strokeColor=CC_AMBER))
    label_text(d, 240, 32, "loop until task complete — human can interrupt at any point", 7, CC_AMBER, 'Helvetica-Oblique')
    # Core principle
    d.add(Rect(70, 5, 340, 18, fillColor=HexColor("#fff8e1"), strokeColor=CC_AMBER, strokeWidth=0.5, rx=3))
    label_text(d, 240, 10, "Principle: Model reasons + Tools act  ·  Harness provides context, tools & execution env", 7, DARK_GRAY)
    return d

def diag_multi_agent():
    d = Drawing(480, 185)
    label_text(d, 240, 173, "OpenClaw — Multi-Agent Routing", 11, ACCENT_BLUE, 'Helvetica-Bold')
    draw_box(d, 10, 125, 90, 32, ACCENT_ORANGE, "Inbound\nMessage", 9)
    draw_box(d, 130, 120, 130, 40, ACCENT_BLUE, "Binding Router\n(most-specific wins)", 8)
    label_text(d, 195, 118, "peer > guild > account > default", 5.5, HexColor("#90caf9"), 'Helvetica-Oblique')
    arrow_right(d, 100, 141, 130, 141, ACCENT_TEAL)
    for i, (lbl, clr) in enumerate([("Agent: main\nWorkspace A\nSessions A", ACCENT_TEAL), ("Agent: coding\nWorkspace B\nSessions B", ACCENT_PURPLE), ("Agent: support\nWorkspace C\nSessions C", ACCENT_GREEN)]):
        draw_box(d, 50+i*150, 15, 130, 55, clr, lbl, 7.5)
    arrow_down(d, 155, 120, 115, 70)
    arrow_down(d, 195, 120, 265, 70)
    arrow_down(d, 235, 120, 415, 70)
    # Callout
    d.add(Rect(300, 125, 165, 32, fillColor=HexColor("#fff3e0"), strokeColor=ACCENT_ORANGE, strokeWidth=0.5, rx=3))
    label_text(d, 382, 145, "Each agent fully isolated:", 7, DARK_GRAY, 'Helvetica-Bold')
    label_text(d, 382, 135, "Own workspace · auth · sessions", 6.5, DARK_GRAY)
    label_text(d, 382, 126, "No cross-agent credential sharing", 6.5, ACCENT_RED, 'Helvetica-Oblique')
    return d

def diag_qqlaw_core():
    """The qqlaw architecture — merging both philosophies."""
    d = Drawing(480, 320)
    label_text(d, 240, 308, "qqlaw — Enterprise Agentic Architecture", 12, QQ_DARK, 'Helvetica-Bold')
    label_text(d, 240, 295, "Merging OpenClaw's Channel-First Design + Claude Code's Minimalist Agentic Loop", 7.5, DARK_GRAY, 'Helvetica-Oblique')

    # ── User Layer ──
    d.add(Rect(60, 260, 360, 25, fillColor=HexColor("#e3f2fd"), strokeColor=QQ_BLUE, strokeWidth=0.75, rx=4))
    label_text(d, 240, 269, "Enterprise Users:  Slack · Teams · WhatsApp · Web · Mobile · Email", 7.5, DARK_GRAY)
    arrow_down(d, 240, 260, 240, 248)

    # ── Auth + API Gateway ──
    draw_box(d, 70, 218, 340, 27, DARK_GRAY, "API Gateway  +  IAM (OIDC · RBAC · MFA · Tenant Scoping)", 8)
    arrow_down(d, 240, 218, 240, 205)

    # ── qqlaw Core ──
    d.add(Rect(30, 125, 420, 78, fillColor=HexColor("#e3f2fd"), strokeColor=QQ_BLUE, strokeWidth=1, rx=5))
    label_text(d, 240, 192, "qqlaw Core Engine", 10, QQ_DARK, 'Helvetica-Bold')

    # Agentic loop inside core (from Claude Code)
    draw_box(d, 40, 162, 95, 24, HexColor("#fff3e0"), "Agentic Loop\nGather→Act→Verify", 6.5, black)
    draw_box(d, 145, 162, 95, 24, QQ_BLUE, "Tenant Router\nPod-per-tenant", 7)
    draw_box(d, 250, 162, 95, 24, ACCENT_PURPLE, "Session Mgr\nPer-tenant-user", 7)
    draw_box(d, 355, 162, 85, 24, ACCENT_TEAL, "Skill Dispatch\nApproved only", 7)

    # Harness row
    draw_box(d, 40, 130, 190, 22, HexColor("#455a64"), "Workspace Isolation (K8s Pods)\nSOUL.md · AGENTS.md · Memory", 6.5)
    draw_box(d, 240, 130, 200, 22, HexColor("#455a64"), "Tool Runtime (Sandboxed gVisor)\nExec · Browser · File · Search", 6.5)

    # Arrows from core to tenant pods
    for ax in [80, 200, 320, 420]:
        arrow_down(d, ax, 125, ax, 112)

    # ── Tenant Pods ──
    for i, (lbl, clr) in enumerate([("Tenant A", ACCENT_BLUE), ("Tenant B", ACCENT_TEAL), ("Tenant C", ACCENT_PURPLE), ("Tenant N", ACCENT_GREEN)]):
        tx = 15 + i*118
        draw_box(d, tx, 73, 100, 36, clr, f"{lbl}\nGateway Pod", 7.5)
        d.add(Rect(tx+25, 68, 50, 9, fillColor=HexColor("#ffcdd2"), strokeColor=ACCENT_RED, strokeWidth=0.3, rx=2))
        label_text(d, tx+50, 69.5, "Isolated", 5, ACCENT_RED, 'Helvetica-Bold')

    # ── Shared Services ──
    d.add(Line(15, 62, 465, 62, strokeColor=MED_GRAY, strokeWidth=0.5, strokeDashArray=[3,2]))
    label_text(d, 240, 54, "Shared Services Layer", 8, DARK_GRAY, 'Helvetica-Bold')
    for i, lbl in enumerate(["Model Router\n(LLM Gateway)", "Skill Registry\n(Vetted + Versioned)", "Observability\n(Audit · OTel)", "Data Layer\n(Postgres · S3)"]):
        draw_box(d, 15+i*118, 14, 100, 34, HexColor("#455a64"), lbl, 7)

    # ── Baioniq Bridge ──
    draw_box(d, 80, -15, 320, 22, BAIONIQ_PURPLE, "Baioniq Platform Bridge  —  RAG · Guardrails · Model Mgmt · Governance", 7)
    for sx in [65, 183, 301, 415]:
        arrow_down(d, sx, 14, 240, 7)

    return d

def diag_philosophy_merge():
    """Side-by-side: what qqlaw takes from each."""
    d = Drawing(480, 180)
    label_text(d, 240, 168, "Design Philosophy Merge", 11, QQ_DARK, 'Helvetica-Bold')
    
    # OpenClaw column
    d.add(Rect(10, 20, 145, 135, fillColor=HexColor("#e3f2fd"), strokeColor=ACCENT_BLUE, strokeWidth=0.75, rx=4))
    label_text(d, 82, 140, "From OpenClaw", 9, ACCENT_BLUE, 'Helvetica-Bold')
    items_oc = ["Channel-first (25+ surfaces)", "Multi-agent routing", "Workspace isolation", "Skills + ClawHub ecosystem", "Cron/heartbeat automation", "SOUL.md persona system"]
    for i, item in enumerate(items_oc):
        label_text(d, 20, 125 - i*17, f"• {item}", 7, DARK_GRAY, 'Helvetica', 'start')

    # Claude Code column
    d.add(Rect(168, 20, 145, 135, fillColor=HexColor("#fff8e1"), strokeColor=CC_AMBER, strokeWidth=0.75, rx=4))
    label_text(d, 240, 140, "From Claude Code", 9, CC_AMBER, 'Helvetica-Bold')
    items_cc = ["Agentic loop (3 phases)", "Permission-based security", "Subagent delegation", "CLAUDE.md context injection", "Sandboxed execution", "Verify-before-commit ethos"]
    for i, item in enumerate(items_cc):
        label_text(d, 178, 125 - i*17, f"• {item}", 7, DARK_GRAY, 'Helvetica', 'start')

    # qqlaw column
    d.add(Rect(326, 20, 145, 135, fillColor=HexColor("#e8f5e9"), strokeColor=ACCENT_GREEN, strokeWidth=0.75, rx=4))
    label_text(d, 398, 140, "qqlaw Synthesis", 9, ACCENT_GREEN, 'Helvetica-Bold')
    items_qq = ["Omnichannel delivery", "Pod-per-tenant isolation", "Agentic loop + RBAC tools", "Enterprise skill registry", "Governed tool execution", "Baioniq RAG + Guardrails"]
    for i, item in enumerate(items_qq):
        label_text(d, 336, 125 - i*17, f"→ {item}", 7, DARK_GRAY, 'Helvetica', 'start')

    # Arrows
    arrow_right(d, 155, 87, 168, 87, ACCENT_TEAL)
    arrow_right(d, 313, 87, 326, 87, ACCENT_GREEN)

    return d

def diag_session_flow():
    d = Drawing(480, 130)
    label_text(d, 240, 118, "Session Isolation Progression", 10, ACCENT_BLUE, 'Helvetica-Bold')
    modes = [
        ("Shared\n(main)", "All DMs → 1\nsession", HexColor("#e57373")),
        ("Per-Peer", "1 session per\nsender", HexColor("#ffb74d")),
        ("Per-Channel\nPeer", "Channel +\nsender", HexColor("#81c784")),
        ("Per-Tenant\nUser", "Tenant + user\n+ role (qqlaw)", QQ_BLUE),
    ]
    for i, (t, desc, c) in enumerate(modes):
        draw_box(d, 10+i*120, 40, 108, 50, c, f"{t}\n{desc}", 7)
    d.add(Line(30, 30, 440, 30, strokeColor=DARK_GRAY, strokeWidth=1, strokeDashArray=[2,2]))
    arrow_right(d, 30, 30, 440, 30)
    label_text(d, 120, 18, "Personal", 7, DARK_GRAY, 'Helvetica-Oblique')
    label_text(d, 370, 18, "Enterprise", 7, QQ_DARK, 'Helvetica-Bold')
    return d

def diag_baioniq_integration():
    d = Drawing(480, 240)
    label_text(d, 240, 228, "Baioniq + qqlaw Integration", 11, BAIONIQ_PURPLE, 'Helvetica-Bold')
    # Baioniq
    d.add(Rect(30, 188, 420, 30, fillColor=BAIONIQ_PURPLE, strokeColor=HexColor("#4a148c"), strokeWidth=1, rx=5))
    label_text(d, 240, 205, "Baioniq Platform", 10, white, 'Helvetica-Bold')
    label_text(d, 240, 193, "Model Mgmt · RAG Pipeline · Guardrails · Governance", 7, HexColor("#e1bee7"))
    # Integration
    for x in [150, 240, 330]:
        arrow_down(d, x, 188, x, 175)
    d.add(Rect(60, 148, 360, 24, fillColor=ACCENT_ORANGE, strokeColor=HexColor("#bf360c"), strokeWidth=0.75, rx=4))
    label_text(d, 240, 161, "qqlaw Agent Bridge API", 8.5, white, 'Helvetica-Bold')
    label_text(d, 240, 151, "Model Router · RAG Skill · Guardrails Middleware · Telemetry", 6.5, HexColor("#fff3e0"))
    # Orchestrator
    arrow_down(d, 240, 148, 240, 133)
    draw_box(d, 90, 98, 300, 32, QQ_DARK, "qqlaw Multi-Tenant Orchestrator\nAgentic Loop · Tenant Routing · Tool RBAC · Skill Dispatch", 7.5)
    # Components
    for ax in [55, 175, 295, 415]:
        arrow_down(d, ax, 98, ax, 83)
    for i, (lbl, clr) in enumerate([("Tenant\nWorkspaces\n(K8s Pods)", ACCENT_TEAL), ("Skill\nRegistry\n(Approved)", ACCENT_GREEN), ("Channel\nHub\n(25+ Surfaces)", ACCENT_PURPLE), ("Audit &\nCompliance\nEngine", ACCENT_RED)]):
        draw_box(d, 10+i*120, 25, 100, 55, clr, lbl, 7.5)
    # Use cases
    d.add(Rect(30, 3, 420, 16, fillColor=HexColor("#f3e5f5"), strokeColor=BAIONIQ_PURPLE, strokeWidth=0.5, rx=3))
    label_text(d, 240, 7, "IT Helpdesk · Sales Copilot · HR Policy Bot · Code Review Agent · Customer Support", 6.5, DARK_GRAY)
    return d

# ═══════════════════════════════════════════════
# BUILD
# ═══════════════════════════════════════════════

def build_report():
    doc = SimpleDocTemplate(OUTPUT_PATH, pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    story = []

    # ═══ COVER ═══
    story.append(Spacer(1, 1.2*inch))
    story.append(Paragraph("qqlaw", ParagraphStyle('BigTitle', parent=title_style, fontSize=40, textColor=QQ_DARK)))
    story.append(Paragraph("Enterprise Agentic AI Architecture", subtitle_style))
    story.append(Paragraph("Inspired by OpenClaw's Channel-First Design<br/>& Claude Code's Minimalist Agentic Philosophy",
        ParagraphStyle('Sub2', parent=subtitle_style, fontSize=11, textColor=DARK_GRAY)))
    story.append(hr())
    story.append(Spacer(1, 0.15*inch))
    story.append(diag_cover())
    story.append(Spacer(1, 0.25*inch))
    story.append(Paragraph(
        f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}<br/>"
        "<b>Author:</b> Dan's Bot",
        ParagraphStyle('CoverMeta', parent=body_style, alignment=TA_CENTER, fontSize=11, leading=16, textColor=DARK_GRAY)
    ))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        '<i>qqlaw is an original enterprise platform design inspired by architectural patterns in OpenClaw (MIT, open-source) '
        'and Claude Code (proprietary, Anthropic). Not a fork, copy, or derivative of either.</i>',
        ParagraphStyle('Disc', parent=body_style, alignment=TA_CENTER, fontSize=9, textColor=MED_GRAY)
    ))
    story.append(PageBreak())

    # ═══ TOC ═══
    story.append(Paragraph("Table of Contents", h1_style))
    story.append(hr())
    toc = [
        ("1.", "Executive Summary"),
        ("2.", "Source Architectures — Deep Dive"),
        ("  2.1", "OpenClaw: Gateway Control Plane & Channel-First Design"),
        ("  2.2", "Claude Code: The Minimalist Agentic Loop"),
        ("  2.3", "Design Principles Worth Stealing"),
        ("3.", "Why These Architectures Won"),
        ("4.", "qqlaw — The Merged Enterprise Architecture"),
        ("  4.1", "Design Philosophy"),
        ("  4.2", "Architecture Overview"),
        ("  4.3", "The Agentic Core (from Claude Code)"),
        ("  4.4", "Channel-First Delivery (from OpenClaw)"),
        ("  4.5", "Tenant Isolation Model"),
        ("  4.6", "Identity & Access Management"),
        ("  4.7", "Shared Services Layer"),
        ("  4.8", "Observability & Compliance"),
        ("5.", "Baioniq Integration Strategy"),
        ("  5.1", "Synergy Map"),
        ("  5.2", "Integration Architecture"),
        ("  5.3", "Competitive Positioning"),
        ("6.", "Implementation Roadmap"),
        ("7.", "Risk Analysis"),
        ("8.", "Conclusion & Recommendations"),
    ]
    for num, title in toc:
        indent = 20 if num.startswith("  ") else 0
        story.append(Paragraph(f'<b>{num.strip()}</b>  {title}',
            ParagraphStyle('TOC', parent=body_style, leftIndent=indent, fontSize=10, spaceAfter=3)))
    story.append(PageBreak())

    # ═══ 1. EXECUTIVE SUMMARY ═══
    story.append(Paragraph("1. Executive Summary", h1_style))
    story.append(hr())
    story.append(Paragraph(
        "Two projects have independently discovered powerful architectural patterns for AI agents: "
        "<b>OpenClaw</b> (open-source, MIT-licensed) solved the delivery problem — how do agents reach users through "
        "25+ messaging channels? <b>Claude Code</b> (proprietary, Anthropic) solved the execution problem — how do "
        "agents reason, act, and verify autonomously with minimal architecture? "
        "Neither was designed for enterprise multi-tenancy.",
        body_style))
    story.append(Paragraph(
        "<b>qqlaw</b> is a proposed enterprise agentic platform that merges these two philosophies into a single "
        "architecture purpose-built for corporate deployment. Combined with Quantiphi's <b>Baioniq</b> platform "
        "(model management, RAG, guardrails, governance), qqlaw creates a complete enterprise agentic AI stack "
        "that no competitor currently offers.",
        body_style))
    story.append(Paragraph('<b>The core insight:</b>', body_style))
    story.append(Paragraph(
        "OpenClaw's Gateway + Claude Code's Agentic Loop + Baioniq's Enterprise GenAI = "
        "governed agents that reason autonomously, execute safely, and deliver through any channel.",
        callout_green))
    story.append(Paragraph('<b>Key architectural decisions in qqlaw:</b>', body_style))
    decisions = [
        "<b>Agentic loop at the core</b> (from Claude Code): Gather → Act → Verify cycle with human-in-the-loop interrupts",
        "<b>Channel-first delivery</b> (from OpenClaw): 25+ messaging surfaces as first-class output, not afterthought",
        "<b>Pod-per-tenant isolation:</b> Kubernetes namespace + container boundaries (not just filesystem convention)",
        "<b>Permission-based tool RBAC</b> (from Claude Code): Every tool invocation requires authorization, not just routing",
        "<b>Workspace-as-identity:</b> SOUL.md/AGENTS.md (OpenClaw persona) + CLAUDE.md (Claude Code project context) patterns for agent configuration",
        "<b>Baioniq bridge:</b> RAG, guardrails, and model management as shared services, not per-agent responsibility",
    ]
    for d_ in decisions:
        story.append(Paragraph(f'• {d_}', bullet_style))
    story.append(PageBreak())

    # ═══ 2. SOURCE ARCHITECTURES ═══
    story.append(Paragraph("2. Source Architectures — Deep Dive", h1_style))
    story.append(hr())

    # 2.1 OpenClaw
    story.append(Paragraph("2.1 OpenClaw: Gateway Control Plane & Channel-First Design", h2_style))
    story.append(Paragraph(
        "OpenClaw is a self-hosted AI agent framework built around a single long-lived Node.js Gateway process. "
        "It owns all messaging connections (WhatsApp via Baileys, Telegram via grammY, Discord, Slack, Signal, "
        "iMessage, and 15+ more), session state, tool execution, and agent orchestration.", body_style))
    story.append(diag_gateway())
    story.append(Paragraph("Figure 1: OpenClaw Gateway — Layered Control Plane", caption_style))

    story.append(Paragraph('<b>Key architectural properties:</b>', body_style))
    for p in [
        "<b>Single-process:</b> No distributed coordination. The Gateway IS the system.",
        "<b>WebSocket-native:</b> Typed WS frames, JSON Schema validation, handshake-first (connect or die).",
        "<b>Multi-agent routing:</b> Multiple isolated agents per Gateway with deterministic binding resolution.",
        "<b>Skills platform:</b> AgentSkills-compatible extensibility with ClawHub registry.",
        "<b>Personal trust model:</b> One trusted operator per Gateway. sessionKey = routing, not auth.",
    ]:
        story.append(Paragraph(f'• {p}', bullet_style))

    story.append(diag_multi_agent())
    story.append(Paragraph("Figure 2: Multi-Agent Routing — Deterministic Binding Resolution", caption_style))

    # 2.2 Claude Code
    story.append(Paragraph("2.2 Claude Code: The Minimalist Agentic Loop", h2_style))
    story.append(Paragraph(
        "Claude Code (proprietary, requires Anthropic subscription or API key) takes a radically different approach. "
        "Instead of building a platform, it builds a <b>harness</b> — the minimal infrastructure needed to turn a "
        "language model into a capable agent. It runs locally in your terminal/IDE but depends on Anthropic's cloud "
        "for model inference. The architecture is three things: a model that reasons, tools that act, and a loop "
        "that connects them.", body_style))
    story.append(diag_agentic_loop())
    story.append(Paragraph("Figure 3: Claude Code Agentic Loop — Minimalist Three-Phase Architecture", caption_style))

    story.append(Paragraph('<b>Core design principles:</b>', body_style))
    for p in [
        "<b>Model + Tools + Loop:</b> That's the entire architecture. The model reasons, tools act, the loop repeats.",
        "<b>Permission-based security:</b> Read-only by default. Every write/exec requires explicit approval.",
        "<b>Context window is the bottleneck:</b> Performance degrades as context fills. Everything is designed to preserve it.",
        "<b>Subagent delegation:</b> Specialized agents (Explore, Plan, General) with scoped tools and independent contexts.",
        "<b>CLAUDE.md as persistent memory:</b> Project-level instructions injected at session start. Auto-memory for learned patterns.",
        "<b>Verify-before-commit:</b> The single highest-leverage pattern — always give the agent a way to check its own work.",
    ]:
        story.append(Paragraph(f'• {p}', bullet_style))

    story.append(Paragraph(
        "💡 <b>Claude Code's key insight:</b> Don't build a platform — build a harness. The model does the thinking; "
        "you just need to give it the right tools, deny-by-default permissions, and a way to verify results. "
        "Everything else is overhead. (Note: the execution pattern is the inspiration, not the licensing or deployment model.)",
        callout_amber))

    # 2.3 Design Principles
    story.append(Paragraph("2.3 Design Principles Worth Stealing", h2_style))
    story.append(diag_philosophy_merge())
    story.append(Paragraph("Figure 4: Design Philosophy Merge — What qqlaw Takes from Each", caption_style))

    principles_data = [
        ['Principle', 'Source', 'How qqlaw Applies It'],
        ['Channels are the UI', 'OpenClaw', 'Agents deliver through Slack/Teams/WhatsApp —\nno new app for users to learn'],
        ['Agentic loop > pipeline', 'Claude Code', 'Gather→Act→Verify cycle replaces rigid\nLangChain-style DAGs'],
        ['Markdown config\nas agent identity', 'OpenClaw:\nSOUL.md\nClaude Code:\nCLAUDE.md', 'Workspace files define agent persona,\nskills, and behavior per tenant'],
        ['Permission by default', 'Claude Code', 'Every tool invocation requires RBAC clearance,\nnot just session routing'],
        ['Skills as composable\nunits', 'OpenClaw', 'Enterprise skill registry with approval\nworkflows and version pinning'],
        ['Context is precious', 'Claude Code', 'Session pruning, smart compaction, subagent\ndelegation to preserve context'],
        ['Trust boundary =\ncontainer boundary', 'qqlaw (new)', 'Pod-per-tenant with gVisor, not filesystem\nconvention'],
    ]
    pt = Table(principles_data, colWidths=[100, 65, 255])
    pt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), QQ_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#e3f2fd")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(pt)
    story.append(Paragraph("Table 1: Design Principles — Sources and Application in qqlaw", caption_style))
    story.append(PageBreak())

    # ═══ 3. WHY THESE ARCHITECTURES WON ═══
    story.append(Paragraph("3. Why These Architectures Won", h1_style))
    story.append(hr())
    story.append(Paragraph(
        "Both projects achieved rapid adoption by solving different parts of the same problem: making AI agents "
        "genuinely useful in daily workflows, not just impressive in demos.", body_style))

    # Chart
    chart_d = Drawing(450, 165)
    label_text(chart_d, 225, 155, "Adoption Driver Impact — Both Projects", 10, ACCENT_BLUE, 'Helvetica-Bold')
    bc = VerticalBarChart()
    bc.x = 65; bc.y = 25; bc.height = 112; bc.width = 350
    bc.data = [[95, 88, 90, 85, 70], [30, 92, 40, 80, 90]]
    bc.categoryAxis.categoryNames = ['Channel\nCoverage', 'Setup\nSimplicity', 'Data\nSovereignty', 'Extensibility', 'Safety\nGuardrails']
    bc.categoryAxis.labels.fontSize = 6.5
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 100
    bc.valueAxis.labels.fontSize = 7
    bc.bars[0].fillColor = ACCENT_TEAL
    bc.bars[1].fillColor = CC_AMBER
    chart_d.add(bc)
    label_text(chart_d, 180, 10, "■ OpenClaw", 7, ACCENT_TEAL, 'Helvetica-Bold')
    label_text(chart_d, 280, 10, "■ Claude Code", 7, CC_AMBER, 'Helvetica-Bold')
    story.append(chart_d)
    story.append(Paragraph("Figure 5: Adoption Impact Comparison", caption_style))

    story.append(Paragraph(
        "<b>OpenClaw's moat:</b> Channel-first design + self-hosted sovereignty. Day-one support for 25+ messaging "
        "surfaces means users interact from the app they already live in. MIT-licensed, runs on your hardware, "
        "your data never leaves your machine. The agent meets users where they are.", body_style))
    story.append(Paragraph(
        "<b>Claude Code's moat:</b> Minimalist agentic execution with built-in safety. Three phases (gather/act/verify) "
        "with a deny-by-default permission model that makes the agent genuinely autonomous without being dangerous. "
        "Note: Claude Code is proprietary (requires Anthropic subscription/API key) and depends on Anthropic's cloud "
        "for model inference — it is NOT self-hosted or open-source. Its value is in the execution pattern, not the "
        "deployment model.", body_style))
    story.append(Paragraph(
        "<b>Key difference in trust model:</b> OpenClaw trusts by default (full access, ask forgiveness) while "
        "Claude Code denies by default (permission prompts for every write/exec). Both approaches make agents "
        "genuinely useful — OpenClaw through autonomy, Claude Code through verified safety. qqlaw merges both: "
        "RBAC-scoped autonomy within approved tool boundaries.", body_style))
    story.append(PageBreak())

    # ═══ 4. QQLAW ARCHITECTURE ═══
    story.append(Paragraph("4. qqlaw — The Merged Enterprise Architecture", h1_style))
    story.append(hr())

    # 4.1
    story.append(Paragraph("4.1 Design Philosophy", h2_style))
    story.append(Paragraph(
        "qqlaw's design philosophy is captured in three axioms:", body_style))
    story.append(Paragraph(
        "<b>Axiom 1: The agent is a loop, not a pipeline.</b> Inspired by Claude Code, qqlaw agents follow a "
        "Gather→Act→Verify cycle that adapts dynamically. No rigid DAGs. The agent decides what each step requires "
        "based on what it learned from the previous step.", callout_amber))
    story.append(Paragraph(
        "<b>Axiom 2: Channels are the UI.</b> Inspired by OpenClaw, qqlaw delivers through existing messaging "
        "surfaces. The agent appears in Slack, Teams, WhatsApp, email — wherever the enterprise user already works. "
        "No new application to deploy, train on, or maintain.", callout_style))
    story.append(Paragraph(
        "<b>Axiom 3: Trust boundaries are container boundaries.</b> Original to qqlaw. Where OpenClaw uses "
        "filesystem convention and Claude Code uses user approval, qqlaw uses Kubernetes pods with gVisor "
        "sandboxing. Every tenant gets a hard isolation boundary — not because we expect adversarial users, "
        "but because enterprise compliance requires it.", callout_green))

    # 4.2
    story.append(Paragraph("4.2 Architecture Overview", h2_style))
    story.append(diag_qqlaw_core())
    story.append(Paragraph("Figure 6: qqlaw Enterprise Architecture — The Full Stack", caption_style))

    # 4.3
    story.append(Paragraph("4.3 The Agentic Core (from Claude Code)", h2_style))
    story.append(Paragraph(
        "At the heart of every qqlaw agent is Claude Code's agentic loop, adapted for enterprise:", body_style))
    loop_data = [
        ['Phase', 'Claude Code (Personal)', 'qqlaw (Enterprise)'],
        ['Gather\nContext', 'Read files, search code,\nexplore codebase', 'Read tenant workspace +\nquery Baioniq RAG pipeline +\nscan enterprise knowledge bases'],
        ['Take\nAction', 'Edit files, run commands,\nuse any tool', 'Execute RBAC-gated tools only.\nBrowser/exec/file ops sandboxed\nin gVisor. Audit logged.'],
        ['Verify\nResults', 'Run tests, compare output,\ncheck screenshots', 'Run verification suite +\nBaioniq guardrails check output +\ncompliance scan before delivery'],
        ['Subagent\nDelegation', 'Explore (Haiku), Plan,\nGeneral-purpose —\neach in own context window', 'Tenant-scoped subagents with\ninherited RBAC. No cross-tenant\nsubagent spawning.'],
    ]
    lt = Table(loop_data, colWidths=[60, 155, 195])
    lt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), CC_AMBER),
        ('TEXTCOLOR', (0,0), (-1,0), black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#fff8e1")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(lt)
    story.append(Paragraph("Table 2: Agentic Loop — Personal vs Enterprise Adaptation", caption_style))

    # 4.4
    story.append(Paragraph("4.4 Channel-First Delivery (from OpenClaw)", h2_style))
    story.append(Paragraph(
        "qqlaw's Channel Hub adapts OpenClaw's multi-channel architecture for enterprise. Instead of one Gateway "
        "owning all channel connections, qqlaw uses a shared Channel Hub service that routes messages to the "
        "correct tenant pod:", body_style))
    for p in [
        "<b>Shared channel apps:</b> One Slack bot, one Teams app, one WhatsApp Business account — routing by tenant",
        "<b>Per-tenant channel accounts:</b> Optional dedicated bots per tenant for branding/isolation",
        "<b>Format adaptation:</b> Per-channel rendering (no markdown tables in Telegram, link wrapping in Discord, etc.)",
        "<b>Block streaming:</b> Long responses chunked and coalesced to avoid single-line spam",
        "<b>Media pipeline:</b> Unified image/audio/doc handling across all surfaces",
    ]:
        story.append(Paragraph(f'• {p}', bullet_style))

    # 4.5
    story.append(Paragraph("4.5 Tenant Isolation Model", h2_style))
    story.append(diag_session_flow())
    story.append(Paragraph("Figure 7: Session Isolation Progression — Personal to Enterprise", caption_style))
    for p in [
        "<b>Pod-per-tenant:</b> K8s namespace + network policies + gVisor container per tenant",
        "<b>Workspace PV:</b> Dedicated persistent volume (not shared filesystem)",
        "<b>Vault secrets:</b> Per-tenant API keys, channel tokens, model credentials",
        "<b>PostgreSQL sessions:</b> Per-tenant schema (replacing JSONL files) for query/audit capability",
        "<b>Resource quotas:</b> CPU/memory limits, token budgets, rate limiting per tenant",
    ]:
        story.append(Paragraph(f'• {p}', bullet_style))

    # 4.6
    story.append(Paragraph("4.6 Identity & Access Management", h2_style))
    iam_data = [
        ['Layer', 'OpenClaw', 'Claude Code', 'qqlaw'],
        ['Auth', 'Device pairing +\nchallenge-response', 'Anthropic account\n(subscription/API key)', 'OIDC / SAML SSO\n+ MFA'],
        ['Authz', 'sessionKey routing\n(not authorization)', 'Per-action permission\nprompts (deny-by-default)', 'RBAC + ABAC per\ntool + resource'],
        ['Identity', 'Device token\n(local trust)', 'Anthropic cloud\naccount', 'Corporate identity\n(Okta/Entra)'],
        ['Tool\nControl', 'Tool policy in\nconfig file', 'Allowlist + sandbox\n+ per-cmd approval', 'RBAC per tool per\ntenant + audit log'],
    ]
    it = Table(iam_data, colWidths=[50, 110, 110, 120])
    it.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), QQ_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('GRID', (0,0), (-1,-1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#e3f2fd")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(it)
    story.append(Paragraph("Table 3: IAM Comparison — Three-Way", caption_style))

    # 4.7
    story.append(Paragraph("4.7 Shared Services Layer", h2_style))
    for p in [
        "<b>Model Router:</b> Central LLM gateway with per-tenant quotas, failover, cost attribution (via Baioniq)",
        "<b>Skill Registry:</b> Curated skill catalog with approval workflows, version pinning, security scanning",
        "<b>Channel Hub:</b> Shared channel infrastructure with per-tenant message routing",
        "<b>Object Store:</b> S3-compatible with per-tenant bucket prefixes and lifecycle policies",
    ]:
        story.append(Paragraph(f'• {p}', bullet_style))

    # 4.8
    story.append(Paragraph("4.8 Observability & Compliance", h2_style))
    for p in [
        "<b>Audit logs:</b> Every tool invocation, model call, message — immutably logged with tenant/user attribution",
        "<b>OTel traces:</b> OpenTelemetry from message receipt through agentic loop to response delivery",
        "<b>Metrics:</b> Token usage, latency, error rates per tenant/agent/model (Prometheus + Grafana)",
        "<b>PII detection:</b> Redaction in logs/transcripts with configurable retention",
        "<b>Compliance:</b> SOC 2 Type II evidence, GDPR DSAR support, data classification",
    ]:
        story.append(Paragraph(f'• {p}', bullet_style))
    story.append(PageBreak())

    # ═══ 5. BAIONIQ ═══
    story.append(Paragraph("5. Baioniq Integration Strategy", h1_style))
    story.append(hr())

    # 5.1
    story.append(Paragraph("5.1 Synergy Map", h2_style))
    syn_data = [
        ['Capability', 'qqlaw Provides', 'Baioniq Provides', 'Combined'],
        ['Reasoning', 'Agentic loop\n(gather/act/verify)', 'Model management\n+ evaluation', 'Governed\nautonomous agents'],
        ['Knowledge', 'Workspace memory\n+ CLAUDE.md patterns', 'RAG pipeline\n+ vector stores', 'Deep enterprise\ncontext'],
        ['Delivery', '25+ messaging\nsurfaces', 'Enterprise\nconnectors', 'Omnichannel\nagent UX'],
        ['Safety', 'Pod isolation\n+ tool RBAC', 'Guardrails\n+ governance', 'Defense-in-\ndepth'],
        ['Ops', 'Cron · heartbeats\n· webhooks', 'K8s deploy\n+ monitoring', 'Enterprise\nautomation'],
    ]
    st = Table(syn_data, colWidths=[65, 105, 105, 95])
    st.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BAIONIQ_PURPLE),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#f3e5f5")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(st)
    story.append(Paragraph("Table 4: qqlaw ↔ Baioniq Synergy Matrix", caption_style))

    # 5.2
    story.append(Paragraph("5.2 Integration Architecture", h2_style))
    story.append(diag_baioniq_integration())
    story.append(Paragraph("Figure 8: Baioniq + qqlaw Integration Architecture", caption_style))

    for p in [
        "<b>Model Router Bridge:</b> Tenant pods route LLM calls through Baioniq's model management layer",
        "<b>RAG Skill:</b> Custom skill bridging qqlaw's tool interface to Baioniq's retrieval API",
        "<b>Guardrails Middleware:</b> Baioniq's content safety wraps agent I/O (both directions)",
        "<b>Workspace Templates:</b> Baioniq manages tenant provisioning — pre-configured personas and skill sets",
        "<b>Telemetry Pipeline:</b> Agent execution telemetry flows into Baioniq's operational dashboard",
    ]:
        story.append(Paragraph(f'• {p}', bullet_style))

    # 5.3
    story.append(Paragraph("5.3 Competitive Positioning", h2_style))
    story.append(Paragraph(
        '<b>"Baioniq Agents" — Enterprise Agentic AI, Delivered Where Your Teams Already Work</b>',
        ParagraphStyle('Tag', parent=body_style, fontSize=12, textColor=BAIONIQ_PURPLE, alignment=TA_CENTER, spaceBefore=8, spaceAfter=12)))
    diff_data = [
        ['Competitor', 'Limitation', 'Baioniq Agents (qqlaw)'],
        ['Microsoft Copilot', 'Locked to M365', 'Any channel + any model'],
        ['Google Agentspace', 'GCP only', 'Multi-cloud + self-hosted option'],
        ['Salesforce Agentforce', 'CRM-centric', 'Full tool execution + RAG'],
        ['Custom LangChain', 'DIY ops, no channels', 'Managed + 25+ channels built-in'],
        ['OpenClaw\n(OSS, MIT)', 'Personal only,\nno enterprise', 'Multi-tenant, governed,\ncompliant'],
        ['Claude Code\n(Proprietary)', 'Developer tool,\nno channel delivery', 'Enterprise channels +\ngovernance layer'],
    ]
    dt = Table(diff_data, colWidths=[105, 130, 175])
    dt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), QUANTIPHI_BLUE),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, LIGHT_GRAY]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(dt)
    story.append(Paragraph("Table 5: Competitive Differentiation", caption_style))
    story.append(PageBreak())

    # ═══ 6. ROADMAP ═══
    story.append(Paragraph("6. Implementation Roadmap", h1_style))
    story.append(hr())
    rm_data = [
        ['Phase', 'Timeline', 'Deliverables', 'Dependencies'],
        ['Phase 1:\nAgentic Core', 'Weeks 1–6', '• qqlaw agentic loop engine\n• Pod-per-tenant K8s manifests\n• IAM integration (OIDC)\n• PostgreSQL session store', 'K8s cluster,\nIdentity provider,\nPostgres'],
        ['Phase 2:\nBaioniq Bridge', 'Weeks 7–12', '• Model Router Bridge API\n• RAG Skill implementation\n• Guardrails middleware\n• Workspace template system', 'Baioniq API,\nRAG pipeline,\nGuardrails svc'],
        ['Phase 3:\nChannels +\nSkills', 'Weeks 13–18', '• Enterprise Channel Hub\n• Skill Registry + approval\n• Admin portal MVP\n• Per-tenant dashboards', 'Slack/Teams apps,\nUI framework,\nProm/Grafana'],
        ['Phase 4:\nHarden +\nShip', 'Weeks 19–24', '• Security audit + pen test\n• SOC 2 evidence pack\n• Performance benchmarks\n• Customer pilot (2 tenants)', 'Security team,\nCompliance,\nPilot customers'],
    ]
    rt = Table(rm_data, colWidths=[65, 65, 195, 110])
    rt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), QQ_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#e3f2fd")]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(rt)
    story.append(Paragraph("Table 6: 24-Week Implementation Roadmap", caption_style))
    story.append(Paragraph("<b>Estimated team:</b> 2 platform engineers, 1 Baioniq specialist, 1 security engineer, 0.5 PM (~4.5 FTE × 6 months)", body_style))
    story.append(PageBreak())

    # ═══ 7. RISK ═══
    story.append(Paragraph("7. Risk Analysis", h1_style))
    story.append(hr())
    rk_data = [
        ['Risk', 'Severity', 'Likelihood', 'Mitigation'],
        ['Agentic loop produces\nunexpected actions\nin production', 'Critical', 'Medium', 'Baioniq guardrails on all I/O;\ngVisor sandbox; tool RBAC;\nhuman-in-the-loop for sensitive ops'],
        ['Pod-per-tenant cost\nat scale (100+\ntenants)', 'Medium', 'Medium', 'Resource right-sizing; shared-pool\nmode for small tenants; spot\ninstances for non-prod'],
        ['Channel API breaking\nchanges (WhatsApp/\nSlack/Teams)', 'Medium', 'Medium', 'Abstract channel adapter layer;\nuse official APIs (WABA, Bolt);\nversion pinning'],
        ['Enterprise adoption\nfriction (teams don\'t\nwant agents)', 'High', 'Medium', 'Start with Q&A bots; graduate\nto tool-enabled agents; measure\ntime-saved metrics'],
        ['Context window\ndegradation in long\nsessions', 'Medium', 'High', 'Subagent delegation (from Claude\nCode); smart compaction; session\nrotation; auto-memory persistence'],
    ]
    rkt = Table(rk_data, colWidths=[100, 55, 60, 195])
    rkt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ACCENT_RED),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#fce4ec")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(rkt)
    story.append(Paragraph("Table 7: Risk Assessment Matrix", caption_style))
    story.append(PageBreak())

    # ═══ 8. CONCLUSION ═══
    story.append(Paragraph("8. Conclusion & Recommendations", h1_style))
    story.append(hr())
    story.append(Paragraph(
        "OpenClaw proved that AI agents should live in your messaging apps, not behind a new URL. "
        "Claude Code proved that the best agentic architecture is the simplest one: a loop that reasons, acts, and verifies. "
        "qqlaw takes both lessons and rebuilds them for enterprise — with hard tenant isolation, RBAC-governed tools, "
        "and Baioniq's GenAI infrastructure as the foundation.", body_style))
    story.append(Paragraph(
        "• <b>Baioniq alone</b> = powerful GenAI stack, but outputs trapped in dashboards and APIs<br/>"
        "• <b>Agents alone</b> = powerful execution, but no governance, RAG, or compliance<br/>"
        "• <b>Baioniq + qqlaw</b> = governed enterprise agentic AI, delivered through 25+ channels, "
        "with full tool execution, RAG-powered knowledge, and the minimalist agentic loop that Claude Code validated",
        callout_green))

    story.append(Paragraph("<b>Recommendations:</b>", h3_style))
    for r in [
        "<b>1. Build the agentic core first:</b> qqlaw's Gather→Act→Verify loop with RBAC-gated tools. 3-week PoC.",
        "<b>2. Connect to Baioniq immediately:</b> Model Router Bridge + RAG Skill as the first two integrations.",
        "<b>3. Dogfood internally:</b> Deploy for Quantiphi engineering, sales, delivery. Surface real requirements.",
        "<b>4. Demo at GCP Next / re:Invent:</b> Enterprise agents responding across Slack, Teams, WhatsApp with Vertex AI.",
        "<b>5. Protect the IP:</b> The architecture of Baioniq guardrails wrapping an agentic loop with tenant-isolated "
        "workspace execution is novel. Consider provisional patent filing.",
    ]:
        story.append(Paragraph(r, bullet_style))

    story.append(Spacer(1, 0.4*inch))
    story.append(hr())
    story.append(Paragraph("— End of Report —",
        ParagraphStyle('End', parent=body_style, alignment=TA_CENTER, fontSize=10, textColor=DARK_GRAY)))
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}<br/>"
        "Sources: OpenClaw Docs (docs.openclaw.ai) · Claude Code Docs (code.claude.com) · Quantiphi (quantiphi.com)<br/>"
        "<i>qqlaw is an original design concept. OpenClaw is MIT-licensed open-source. Claude Code is proprietary (Anthropic).</i>",
        ParagraphStyle('Footer', parent=body_style, alignment=TA_CENTER, fontSize=8, textColor=MED_GRAY)))

    doc.build(story)
    print(f"✅ Report generated: {OUTPUT_PATH}")
    print(f"   Size: {os.path.getsize(OUTPUT_PATH) / 1024:.0f} KB")

if __name__ == "__main__":
    build_report()
