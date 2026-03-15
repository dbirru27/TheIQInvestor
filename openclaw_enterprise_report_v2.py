#!/usr/bin/env python3
"""
OpenClaw Architecture Deep Dive & qqlaw Enterprise Multi-Tenant Proposal
v2 — cleaner diagrams, qqlaw branding, inspired-by framing
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black, Color
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

styles = getSampleStyleSheet()

title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=28, leading=34, textColor=ACCENT_BLUE, spaceAfter=6, alignment=TA_CENTER)
subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=14, leading=18, textColor=DARK_GRAY, alignment=TA_CENTER, spaceAfter=20)
h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=20, leading=24, textColor=ACCENT_BLUE, spaceBefore=24, spaceAfter=12)
h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=16, leading=20, textColor=DARK_GRAY, spaceBefore=16, spaceAfter=8)
h3_style = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=13, leading=17, textColor=ACCENT_PURPLE, spaceBefore=12, spaceAfter=6)
body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10.5, leading=15, textColor=black, alignment=TA_JUSTIFY, spaceAfter=8)
bullet_style = ParagraphStyle('Bullet', parent=body_style, leftIndent=20, bulletIndent=10, spaceAfter=4)
callout_style = ParagraphStyle('Callout', parent=body_style, fontSize=10, leading=14, textColor=DARK_GRAY, leftIndent=15, rightIndent=15, spaceBefore=8, spaceAfter=8, backColor=HexColor("#eaf2f8"), borderWidth=1, borderColor=ACCENT_BLUE, borderPadding=8)
code_style = ParagraphStyle('Code', parent=styles['Code'], fontSize=8.5, leading=11, textColor=HexColor("#2c3e50"), backColor=HexColor("#f8f9fa"), borderWidth=0.5, borderColor=MED_GRAY, borderPadding=6, leftIndent=10, rightIndent=10, spaceAfter=8)
caption_style = ParagraphStyle('Caption', parent=styles['Normal'], fontSize=9, leading=12, textColor=DARK_GRAY, alignment=TA_CENTER, spaceBefore=4, spaceAfter=12, italic=True)

def hr():
    return HRFlowable(width="100%", thickness=1, color=MED_GRAY, spaceBefore=6, spaceAfter=6)

def draw_rounded_box(d, x, y, w, h, color, label, font_size=8, text_color=white):
    """Draw a rounded rectangle with centered multi-line label."""
    d.add(Rect(x, y, w, h, fillColor=color, strokeColor=HexColor("#444444"), strokeWidth=0.75, rx=5, ry=5))
    lines = label.split('\n')
    total_height = len(lines) * (font_size + 2)
    start_y = y + h/2 + total_height/2 - font_size
    for i, line in enumerate(lines):
        d.add(String(x + w/2, start_y - i * (font_size + 2),
                     line, fontSize=font_size, fillColor=text_color, textAnchor='middle', fontName='Helvetica-Bold'))

def draw_arrow_down(d, x1, y1, x2, y2, color=DARK_GRAY):
    """Draw a downward arrow."""
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.2))
    d.add(Polygon(points=[x2-3.5, y2+5, x2+3.5, y2+5, x2, y2], fillColor=color, strokeColor=color))

def draw_arrow_right(d, x1, y1, x2, y2, color=DARK_GRAY):
    """Draw a rightward arrow."""
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.2))
    d.add(Polygon(points=[x2-5, y2-3.5, x2-5, y2+3.5, x2, y2], fillColor=color, strokeColor=color))

def draw_arrow_left(d, x1, y1, x2, y2, color=DARK_GRAY):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.2))
    d.add(Polygon(points=[x2+5, y2-3.5, x2+5, y2+3.5, x2, y2], fillColor=color, strokeColor=color))

def draw_bidi_arrow(d, x1, y1, x2, y2, color=DARK_GRAY):
    """Draw a bidirectional horizontal arrow."""
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.2))
    d.add(Polygon(points=[x2-5, y2-3, x2-5, y2+3, x2, y2], fillColor=color, strokeColor=color))
    d.add(Polygon(points=[x1+5, y1-3, x1+5, y1+3, x1, y1], fillColor=color, strokeColor=color))

# ════════════════════════════════════════════════════════
# DIAGRAM BUILDERS
# ════════════════════════════════════════════════════════

def diagram_cover_flow():
    """Cover page: clean 3-step flow."""
    d = Drawing(460, 80)
    draw_rounded_box(d, 10, 20, 120, 45, ACCENT_BLUE, "OpenClaw\nArchitecture\nStudy", 9)
    draw_rounded_box(d, 170, 20, 120, 45, QQ_BLUE, "qqlaw\nEnterprise\nDesign", 9)
    draw_rounded_box(d, 330, 20, 120, 45, BAIONIQ_PURPLE, "Baioniq\nPlatform\nIntegration", 9)
    draw_arrow_right(d, 130, 42, 170, 42, ACCENT_TEAL)
    draw_arrow_right(d, 290, 42, 330, 42, ACCENT_TEAL)
    # Labels above arrows
    d.add(String(150, 55, "inspires", fontSize=7, fillColor=ACCENT_TEAL, textAnchor='middle', fontName='Helvetica-Oblique'))
    d.add(String(310, 55, "integrates", fontSize=7, fillColor=ACCENT_TEAL, textAnchor='middle', fontName='Helvetica-Oblique'))
    return d

def diagram_gateway_architecture():
    """Figure 1: OpenClaw Gateway — clean layered diagram."""
    d = Drawing(480, 230)
    d.add(String(240, 218, "OpenClaw Gateway Architecture", fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle', fontName='Helvetica-Bold'))

    # ── Layer 1: Messaging Channels (top) ──
    d.add(Rect(15, 170, 450, 30, fillColor=HexColor("#e8f5e9"), strokeColor=ACCENT_GREEN, strokeWidth=0.75, rx=4))
    d.add(String(240, 181, "Messaging Channels", fontSize=8, fillColor=ACCENT_GREEN, textAnchor='middle', fontName='Helvetica-Bold'))
    channels = ["WhatsApp", "Telegram", "Discord", "Slack", "Signal", "iMessage", "Teams", "IRC"]
    x_start = 25
    for i, ch in enumerate(channels):
        cx = x_start + i * 55
        d.add(String(cx + 24, 172, ch, fontSize=6.5, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica'))

    # Arrow down
    draw_arrow_down(d, 240, 170, 240, 155)

    # ── Layer 2: Gateway Control Plane ──
    d.add(Rect(60, 105, 360, 45, fillColor=ACCENT_BLUE, strokeColor=HexColor("#0a2540"), strokeWidth=1, rx=5))
    d.add(String(240, 133, "Gateway Control Plane", fontSize=10, fillColor=white, textAnchor='middle', fontName='Helvetica-Bold'))
    d.add(String(240, 118, "WebSocket Server  ·  Session Router  ·  Event Bus  ·  Cron Scheduler", fontSize=7, fillColor=HexColor("#bbdefb"), textAnchor='middle', fontName='Helvetica'))
    d.add(String(240, 108, "ws://127.0.0.1:18789  ·  JSON Schema validated  ·  Idempotent ops", fontSize=6.5, fillColor=HexColor("#90caf9"), textAnchor='middle', fontName='Helvetica-Oblique'))

    # Arrows down to components
    for ax in [100, 195, 290, 385]:
        draw_arrow_down(d, ax, 105, ax, 88)

    # ── Layer 3: Components ──
    draw_rounded_box(d, 35, 52, 130, 33, ACCENT_TEAL, "Agent Runtime (Pi RPC)\nTool Exec · Streaming", 7)
    draw_rounded_box(d, 175, 52, 130, 33, ACCENT_PURPLE, "Session Store\nJSONL · DM Scoping", 7)
    draw_rounded_box(d, 315, 52, 130, 33, ACCENT_ORANGE, "Skills Platform\nClawHub · Plugins", 7)

    # ── Layer 4: Clients (bottom) ──
    d.add(Rect(15, 5, 450, 30, fillColor=HexColor("#fce4ec"), strokeColor=ACCENT_RED, strokeWidth=0.75, rx=4))
    d.add(String(240, 16, "Clients:   CLI  ·  Web Control UI  ·  macOS App  ·  iOS/Android Nodes  ·  WebChat", fontSize=7.5, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica'))

    # Arrows up from clients to gateway
    draw_arrow_down(d, 240, 52, 240, 38)

    return d

def diagram_multi_agent_routing():
    """Figure 2: Multi-agent routing — binding resolution."""
    d = Drawing(480, 195)
    d.add(String(240, 183, "Multi-Agent Routing Engine", fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle', fontName='Helvetica-Bold'))

    # Inbound
    draw_rounded_box(d, 10, 130, 90, 35, ACCENT_ORANGE, "Inbound\nMessage", 9)

    # Binding Router
    draw_rounded_box(d, 130, 125, 130, 42, ACCENT_BLUE, "Binding Router\n(most-specific wins)", 8)
    d.add(String(195, 125, "peer > guild > account > channel > default", fontSize=5.5, fillColor=HexColor("#90caf9"), textAnchor='middle', fontName='Helvetica-Oblique'))

    draw_arrow_right(d, 100, 147, 130, 147, ACCENT_TEAL)

    # Agent workspaces (3 boxes)
    agents = [
        ("Agent: main", "Workspace A\nSOUL.md · Sessions", ACCENT_TEAL),
        ("Agent: coding", "Workspace B\nSOUL.md · Sessions", ACCENT_PURPLE),
        ("Agent: support", "Workspace C\nSOUL.md · Sessions", ACCENT_GREEN),
    ]
    for i, (title, desc, color) in enumerate(agents):
        bx = 50 + i * 150
        draw_rounded_box(d, bx, 15, 130, 55, color, f"{title}\n{desc}", 7.5)

    # Arrows from router to agents
    draw_arrow_down(d, 155, 125, 115, 70)
    draw_arrow_down(d, 195, 125, 265, 70)
    draw_arrow_down(d, 235, 125, 415, 70)

    # Isolation callout
    d.add(Rect(310, 130, 155, 35, fillColor=HexColor("#fff3e0"), strokeColor=ACCENT_ORANGE, strokeWidth=0.5, rx=3))
    d.add(String(387, 150, "Each agent is fully isolated:", fontSize=7, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica-Bold'))
    d.add(String(387, 140, "Own workspace · auth · sessions", fontSize=6.5, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica'))
    d.add(String(387, 131, "No cross-agent credential sharing", fontSize=6.5, fillColor=ACCENT_RED, textAnchor='middle', fontName='Helvetica-Oblique'))

    return d

def diagram_qqlaw_enterprise():
    """Figure 3: qqlaw Enterprise Multi-Tenant Architecture."""
    d = Drawing(480, 310)
    d.add(String(240, 298, "qqlaw — Enterprise Multi-Tenant Architecture", fontSize=11, fillColor=QQ_DARK, textAnchor='middle', fontName='Helvetica-Bold'))

    # ── Top: External Clients ──
    d.add(Rect(100, 260, 280, 25, fillColor=HexColor("#e3f2fd"), strokeColor=QQ_BLUE, strokeWidth=0.75, rx=4))
    d.add(String(240, 269, "Enterprise Users:  Slack · Teams · WhatsApp · Web · Mobile", fontSize=7.5, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica'))
    draw_arrow_down(d, 240, 260, 240, 248)

    # ── API Gateway + Auth ──
    draw_rounded_box(d, 80, 215, 320, 30, DARK_GRAY, "API Gateway / Load Balancer  +  IAM (OIDC · RBAC · MFA)", 8)
    draw_arrow_down(d, 240, 215, 240, 200)

    # ── Tenant Router ──
    draw_rounded_box(d, 140, 170, 200, 27, QQ_BLUE, "qqlaw Tenant Router", 9)
    
    # Arrows to tenant pods
    draw_arrow_down(d, 170, 170, 65, 150)
    draw_arrow_down(d, 210, 170, 195, 150)
    draw_arrow_down(d, 270, 170, 325, 150)
    draw_arrow_down(d, 310, 170, 435, 150)

    # ── Tenant Pods ──
    tenant_colors = [ACCENT_BLUE, ACCENT_TEAL, ACCENT_PURPLE, ACCENT_GREEN]
    tenant_labels = ["Tenant A\nGateway Pod", "Tenant B\nGateway Pod", "Tenant C\nGateway Pod", "Tenant N\nGateway Pod"]
    for i in range(4):
        tx = 15 + i * 120
        draw_rounded_box(d, tx, 102, 100, 48, tenant_colors[i], tenant_labels[i], 8)
        # Isolation badge
        d.add(Rect(tx+25, 95, 50, 10, fillColor=HexColor("#ffcdd2"), strokeColor=ACCENT_RED, strokeWidth=0.3, rx=2))
        d.add(String(tx+50, 97, "Isolated", fontSize=5.5, fillColor=ACCENT_RED, textAnchor='middle', fontName='Helvetica-Bold'))

    # ── Divider ──
    d.add(Line(15, 88, 465, 88, strokeColor=MED_GRAY, strokeWidth=0.5, strokeDashArray=[3, 2]))
    d.add(String(240, 80, "Shared Services Layer", fontSize=8, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica-Bold'))

    # ── Shared Services ──
    services = [
        ("Model Router\n(LLM Gateway)", HexColor("#455a64")),
        ("Skill Registry\n(Approved Only)", HexColor("#455a64")),
        ("Data Layer\n(Postgres · S3)", HexColor("#455a64")),
        ("Observability\n(Audit · Metrics)", HexColor("#455a64")),
    ]
    for i, (label, color) in enumerate(services):
        sx = 15 + i * 120
        draw_rounded_box(d, sx, 35, 100, 38, color, label, 7)

    # ── Baioniq Bridge ──
    draw_rounded_box(d, 100, 0, 280, 25, BAIONIQ_PURPLE, "Baioniq Platform Bridge  —  RAG · Guardrails · Model Mgmt · Governance", 7)
    
    # Arrows from shared services down to Baioniq
    for sx in [65, 195, 325, 435]:
        draw_arrow_down(d, sx, 35, 240, 25)

    return d

def diagram_baioniq_integration():
    """Figure 4: Baioniq + qqlaw Integration Architecture."""
    d = Drawing(480, 260)
    d.add(String(240, 248, "Baioniq + qqlaw Integration Architecture", fontSize=11, fillColor=BAIONIQ_PURPLE, textAnchor='middle', fontName='Helvetica-Bold'))

    # ── Baioniq Platform (top) ──
    d.add(Rect(30, 200, 420, 35, fillColor=BAIONIQ_PURPLE, strokeColor=HexColor("#4a148c"), strokeWidth=1, rx=5))
    d.add(String(240, 220, "Baioniq Platform", fontSize=10, fillColor=white, textAnchor='middle', fontName='Helvetica-Bold'))
    d.add(String(240, 207, "Model Management  ·  RAG Pipeline  ·  Guardrails  ·  Governance", fontSize=7, fillColor=HexColor("#e1bee7"), textAnchor='middle', fontName='Helvetica'))

    # ── Integration Layer ──
    draw_arrow_down(d, 150, 200, 150, 185)
    draw_arrow_down(d, 240, 200, 240, 185)
    draw_arrow_down(d, 330, 200, 330, 185)

    d.add(Rect(60, 153, 360, 28, fillColor=ACCENT_ORANGE, strokeColor=HexColor("#bf360c"), strokeWidth=0.75, rx=4))
    d.add(String(240, 166, "Integration Layer — qqlaw Agent Bridge API", fontSize=8.5, fillColor=white, textAnchor='middle', fontName='Helvetica-Bold'))
    d.add(String(240, 156, "Model Router Bridge  ·  RAG Skill Proxy  ·  Guardrails Middleware  ·  Telemetry", fontSize=6.5, fillColor=HexColor("#fff3e0"), textAnchor='middle', fontName='Helvetica'))

    # ── Agent Orchestrator ──
    draw_arrow_down(d, 240, 153, 240, 138)
    draw_rounded_box(d, 100, 100, 280, 35, QQ_DARK, "qqlaw Multi-Tenant Agent Orchestrator\nTenant Routing · Session Isolation · Skill Dispatch", 8)

    # ── Bottom Components ──
    draw_arrow_down(d, 100, 100, 55, 82)
    draw_arrow_down(d, 195, 100, 175, 82)
    draw_arrow_down(d, 285, 100, 295, 82)
    draw_arrow_down(d, 380, 100, 415, 82)

    components = [
        ("Tenant\nWorkspaces\n(K8s Pods)", ACCENT_TEAL),
        ("Skill\nRegistry\n(Vetted)", ACCENT_GREEN),
        ("Channel\nHub\n(25+ Surfaces)", ACCENT_PURPLE),
        ("Audit &\nCompliance\nEngine", ACCENT_RED),
    ]
    for i, (label, color) in enumerate(components):
        cx = 10 + i * 120
        draw_rounded_box(d, cx, 25, 100, 55, color, label, 7.5)

    # Use cases at bottom
    d.add(Rect(30, 0, 420, 18, fillColor=HexColor("#f3e5f5"), strokeColor=BAIONIQ_PURPLE, strokeWidth=0.5, rx=3))
    d.add(String(240, 5, "Use Cases:  IT Helpdesk Agent  ·  Sales Copilot  ·  HR Policy Bot  ·  Code Review Agent  ·  Customer Support", fontSize=6.5, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica'))

    return d

def diagram_session_flow():
    """Figure 5: Session isolation — how DMs route per tenant."""
    d = Drawing(480, 140)
    d.add(String(240, 128, "Session Isolation Model (Inspired by OpenClaw DM Scoping)", fontSize=10, fillColor=ACCENT_BLUE, textAnchor='middle', fontName='Helvetica-Bold'))

    # 4 modes as boxes
    modes = [
        ("Shared\n(main)", "All DMs → 1 session\nSingle-user only", HexColor("#e57373")),
        ("Per-Peer", "1 session per sender\nMulti-user basic", HexColor("#ffb74d")),
        ("Per-Channel\n-Peer", "Channel + sender\nRecommended", HexColor("#81c784")),
        ("Per-Tenant\n-User", "Tenant + user + role\nqqlaw enterprise", QQ_BLUE),
    ]
    for i, (title, desc, color) in enumerate(modes):
        mx = 10 + i * 120
        draw_rounded_box(d, mx, 40, 108, 55, color, f"{title}\n{desc}", 7)

    # Arrow across bottom
    d.add(Line(30, 30, 440, 30, strokeColor=DARK_GRAY, strokeWidth=1, strokeDashArray=[2, 2]))
    draw_arrow_right(d, 30, 30, 440, 30, DARK_GRAY)
    d.add(String(140, 18, "Personal", fontSize=7, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica-Oblique'))
    d.add(String(350, 18, "Enterprise", fontSize=7, fillColor=QQ_DARK, textAnchor='middle', fontName='Helvetica-Bold'))
    d.add(String(240, 8, "Increasing isolation →", fontSize=7, fillColor=DARK_GRAY, textAnchor='middle', fontName='Helvetica'))

    return d

# ════════════════════════════════════════════════════════
# REPORT BUILDER
# ════════════════════════════════════════════════════════

def build_report():
    doc = SimpleDocTemplate(
        OUTPUT_PATH, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch
    )
    story = []

    # ══════════════════════════════════════════
    # COVER PAGE
    # ══════════════════════════════════════════
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("OpenClaw Architecture Deep Dive", title_style))
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("& qqlaw Enterprise Multi-Tenant Proposal", ParagraphStyle('Sub2', parent=subtitle_style, fontSize=16, textColor=QQ_DARK)))
    story.append(hr())
    story.append(Spacer(1, 0.2*inch))

    story.append(diagram_cover_flow())
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph(
        f'<b>Date:</b> {datetime.now().strftime("%B %d, %Y")}<br/>'
        "<b>Author:</b> Dan's Bot",
        ParagraphStyle('CoverMeta', parent=body_style, alignment=TA_CENTER, fontSize=11, leading=16, textColor=DARK_GRAY)
    ))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(
        '<i>Note: qqlaw is an original enterprise agentic platform design inspired by architectural patterns '
        'observed in OpenClaw. This is not a fork, copy, or derivative of the OpenClaw codebase.</i>',
        ParagraphStyle('Disclaimer', parent=body_style, alignment=TA_CENTER, fontSize=9, textColor=MED_GRAY)
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # TABLE OF CONTENTS
    # ══════════════════════════════════════════
    story.append(Paragraph("Table of Contents", h1_style))
    story.append(hr())
    toc_items = [
        ("1.", "Executive Summary"),
        ("2.", "OpenClaw Architecture — Technical Deep Dive"),
        ("  2.1", "Gateway Control Plane"),
        ("  2.2", "WebSocket Protocol & Connection Lifecycle"),
        ("  2.3", "Multi-Agent Routing Engine"),
        ("  2.4", "Session Management & Isolation"),
        ("  2.5", "Skills Platform & Plugin Ecosystem"),
        ("  2.6", "Sandboxing & Security Model"),
        ("  2.7", "Automation Engine (Cron, Heartbeats, Webhooks)"),
        ("  2.8", "Multi-Channel Media Pipeline"),
        ("3.", "Why OpenClaw Achieved Rapid Adoption"),
        ("  3.1", "Zero-to-Agent in 5 Minutes"),
        ("  3.2", "Channel-First Design"),
        ("  3.3", "Personal Assistant Trust Model"),
        ("  3.4", "Developer-Centric Extensibility"),
        ("  3.5", "Self-Hosted Sovereignty"),
        ("4.", "qqlaw — Enterprise Multi-Tenant Architecture"),
        ("  4.1", "From Personal to Corporate: The Gap"),
        ("  4.2", "qqlaw Architecture Overview"),
        ("  4.3", "Tenant Isolation Model"),
        ("  4.4", "Identity & Access Management"),
        ("  4.5", "Shared Services Layer"),
        ("  4.6", "Observability & Compliance"),
        ("5.", "Baioniq Integration Strategy"),
        ("  5.1", "Baioniq Platform Overview"),
        ("  5.2", "Synergy Map: qqlaw ↔ Baioniq"),
        ("  5.3", "Integration Architecture"),
        ("  5.4", "Differentiation & GTM Positioning"),
        ("6.", "Implementation Roadmap"),
        ("7.", "Risk Analysis & Mitigations"),
        ("8.", "Conclusion & Recommendations"),
    ]
    for num, title in toc_items:
        indent = 20 if num.startswith("  ") else 0
        story.append(Paragraph(
            f'<b>{num.strip()}</b>  {title}',
            ParagraphStyle('TOC', parent=body_style, leftIndent=indent, fontSize=10, spaceAfter=3)
        ))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # 1. EXECUTIVE SUMMARY
    # ══════════════════════════════════════════
    story.append(Paragraph("1. Executive Summary", h1_style))
    story.append(hr())
    story.append(Paragraph(
        "OpenClaw has emerged as one of the fastest-growing open-source AI agent frameworks, gaining significant "
        "traction among developers and power users seeking a self-hosted, channel-agnostic personal AI assistant. "
        "Its architecture — centered on a single-process Gateway control plane with WebSocket-based client orchestration — "
        "represents a fundamentally different approach from cloud-native agentic platforms.",
        body_style
    ))
    story.append(Paragraph(
        "This report provides a comprehensive technical analysis of OpenClaw's architecture, identifies the core "
        "innovations that enabled its rapid adoption, and proposes <b>qqlaw</b> — an original enterprise multi-tenant "
        "agentic platform <i>inspired by</i> OpenClaw's architectural patterns but purpose-built for corporate deployment. "
        "qqlaw is designed to complement and extend Quantiphi's <b>Baioniq</b> platform, creating a differentiated offering "
        "that combines Baioniq's enterprise GenAI stack with qqlaw's agent orchestration, multi-channel delivery, and "
        "tenant-isolated workspaces.",
        body_style
    ))
    story.append(Paragraph('<b>Key findings:</b>', body_style))
    findings = [
        "OpenClaw's single-Gateway architecture eliminates distributed coordination overhead — a pattern qqlaw adapts for tenant-scoped pods",
        "Multi-agent routing with workspace isolation provides a blueprint for tenant separation without container-per-user overhead",
        "The Skills platform (AgentSkills-compatible) creates a composable tool ecosystem applicable to enterprise tool registries",
        "Channel-first design (25+ messaging surfaces) is directly translatable to enterprise communication consolidation",
        "The personal assistant trust model must be fundamentally redesigned for hostile multi-tenant enterprise use — qqlaw addresses this with IAM, RBAC, and hard isolation",
    ]
    for f in findings:
        story.append(Paragraph(f'• {f}', bullet_style))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # 2. OPENCLAW ARCHITECTURE
    # ══════════════════════════════════════════
    story.append(Paragraph("2. OpenClaw Architecture — Technical Deep Dive", h1_style))
    story.append(hr())

    # 2.1 Gateway
    story.append(Paragraph("2.1 Gateway Control Plane", h2_style))
    story.append(Paragraph(
        "The Gateway is the central nervous system of OpenClaw. It is a single long-lived Node.js process that owns "
        "all messaging surface connections, session state, agent orchestration, and tool execution. Every component — "
        "from WhatsApp (via Baileys) to Telegram (via grammY) to Discord (discord.js) — connects through this single process.",
        body_style
    ))

    story.append(diagram_gateway_architecture())
    story.append(Paragraph("Figure 1: OpenClaw Gateway Architecture — Layered Control Plane", caption_style))

    story.append(Paragraph('<b>Key architectural properties:</b>', body_style))
    gw_props = [
        "<b>Single-process design:</b> No distributed coordination, no service mesh, no message queue. The Gateway IS the system.",
        "<b>WebSocket-native:</b> All control plane communication uses typed WS frames with JSON Schema validation.",
        "<b>Loopback-bound:</b> Default bind to 127.0.0.1:18789. External access via Tailscale Serve/Funnel or SSH tunnels.",
        "<b>Event-driven:</b> Emits typed events (agent, chat, presence, health, heartbeat, cron) that clients subscribe to.",
        "<b>Idempotent operations:</b> Side-effecting methods require idempotency keys with server-side dedupe cache.",
    ]
    for p in gw_props:
        story.append(Paragraph(f'• {p}', bullet_style))

    # 2.2 WebSocket Protocol
    story.append(Paragraph("2.2 WebSocket Protocol & Connection Lifecycle", h2_style))
    story.append(Paragraph(
        "OpenClaw defines a strict typed wire protocol over WebSocket text frames. The first frame must always be a "
        "<font face='Courier' size=9>connect</font> request — any non-JSON or non-connect first frame triggers an "
        "immediate hard close. This handshake-first design prevents unauthorized access and enables device-based pairing.",
        body_style
    ))
    story.append(Paragraph(
        '<font face="Courier" size=8>'
        'Client → Gateway:  {type:"req", method:"connect", params:{auth:{token}, role, caps}}<br/>'
        'Gateway → Client:  {type:"res", ok:true, payload:{snapshot: {presence, health}}}<br/>'
        'Gateway → Client:  {type:"event", event:"presence", payload:{...}}<br/>'
        'Client → Gateway:  {type:"req", method:"agent", params:{message, idempotencyKey}}<br/>'
        'Gateway → Client:  {type:"res", ok:true, payload:{runId, status:"accepted"}}<br/>'
        'Gateway → Client:  {type:"event", event:"agent", payload:{streaming...}}<br/>'
        'Gateway → Client:  {type:"res", ok:true, payload:{runId, status:"complete"}}<br/>'
        '</font>',
        code_style
    ))
    story.append(Paragraph(
        "Device pairing uses challenge-response signing (v3 payload binds platform + deviceFamily). "
        "Local connects (loopback/tailnet) can be auto-approved; non-local connects require explicit approval. "
        "The Gateway pins paired device metadata on reconnect — metadata changes require re-pairing.",
        body_style
    ))

    # 2.3 Multi-Agent Routing
    story.append(Paragraph("2.3 Multi-Agent Routing Engine", h2_style))
    story.append(Paragraph(
        "OpenClaw's multi-agent system enables multiple isolated \"brains\" to coexist on a single Gateway. Each agent is a "
        "fully scoped entity with its own workspace (AGENTS.md, SOUL.md, USER.md), state directory (auth profiles, model "
        "registry), and session store. This is the architectural pattern most relevant to enterprise multi-tenancy.",
        body_style
    ))

    story.append(diagram_multi_agent_routing())
    story.append(Paragraph("Figure 2: Multi-Agent Routing — Deterministic Binding Resolution", caption_style))

    story.append(Paragraph(
        "Auth profiles are per-agent. Each agent reads from "
        "<font face='Courier' size=8>~/.openclaw/agents/&lt;agentId&gt;/agent/auth-profiles.json</font>. "
        "Main agent credentials are never shared automatically — reusing agentDir across agents causes collisions.",
        callout_style
    ))

    # 2.4 Session Management
    story.append(Paragraph("2.4 Session Management & Isolation", h2_style))
    story.append(Paragraph(
        "Sessions are the fundamental unit of conversational state. OpenClaw provides four DM scoping modes "
        "that control how direct messages are grouped — a pattern qqlaw extends with tenant-level isolation:",
        body_style
    ))

    story.append(diagram_session_flow())
    story.append(Paragraph("Figure 3: Session Isolation Progression — Personal to Enterprise", caption_style))

    session_data = [
        ['Mode', 'Key Pattern', 'Use Case'],
        ['main (default)', 'agent:<id>:<mainKey>', 'Single user, all DMs share context'],
        ['per-peer', 'agent:<id>:direct:<peerId>', 'Multi-user, isolate by sender'],
        ['per-channel-peer', 'agent:<id>:<ch>:direct:<peer>', 'Multi-user inbox (recommended)'],
        ['per-tenant-user\n(qqlaw extension)', 'tenant:<tid>:agent:<id>:\nuser:<uid>', 'Enterprise: tenant + user + role'],
    ]
    session_table = Table(session_data, colWidths=[110, 170, 160])
    session_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 4), (-1, 4), HexColor("#e3f2fd")),
    ]))
    story.append(session_table)
    story.append(Paragraph("Table 1: Session Scoping — OpenClaw Modes + qqlaw Extension", caption_style))

    # 2.5 Skills Platform
    story.append(Paragraph("2.5 Skills Platform & Plugin Ecosystem", h2_style))
    story.append(Paragraph(
        "The Skills platform is OpenClaw's extensibility engine. Skills are directories with a SKILL.md containing YAML "
        "frontmatter, compatible with the AgentSkills spec. Loaded from three locations with clear precedence:",
        body_style
    ))

    skills_data = [
        ['Layer', 'Location', 'Scope'],
        ['Workspace', '<workspace>/skills', 'Per-agent only'],
        ['Managed/Local', '~/.openclaw/skills', 'All agents on machine'],
        ['Bundled', 'npm package', 'All installs (lowest priority)'],
        ['Extra Dirs', 'skills.load.extraDirs', 'Configurable shared packs'],
    ]
    skills_table = Table(skills_data, colWidths=[90, 180, 170])
    skills_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT_TEAL),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(skills_table)
    story.append(Paragraph("Table 2: Skills Loading Precedence", caption_style))

    story.append(Paragraph(
        "Skills support gating: binary presence checks (requires.bins), environment variables (requires.env), "
        "config flags (requires.config), and OS filtering. ClawHub (clawhub.com) provides discovery and sync. "
        "This pattern directly informs qqlaw's enterprise Skill Registry with approval workflows.",
        body_style
    ))

    # 2.6 Sandboxing
    story.append(Paragraph("2.6 Sandboxing & Security Model", h2_style))
    story.append(Paragraph(
        "OpenClaw operates under a <b>personal assistant trust model</b> — one trusted operator boundary per gateway. "
        "This is explicitly NOT a hostile multi-tenant security boundary. However, it provides optional Docker-based "
        "sandboxing to limit blast radius:",
        body_style
    ))
    sandbox_items = [
        "<b>Modes:</b> off (default) · non-main (sandbox non-main sessions) · all (every session sandboxed)",
        "<b>Scope:</b> per-session (one container each) · per-agent · shared (global container)",
        "<b>Workspace access:</b> none (isolated) · ro (read-only mount) · rw (read-write mount)",
        "<b>Network:</b> Default no-network. Configurable via docker.network",
        "<b>Browser sandbox:</b> Dedicated CDP browser with noVNC observer, CIDR allowlists",
    ]
    for item in sandbox_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    story.append(Paragraph(
        "⚠️ <b>Enterprise gap:</b> OpenClaw explicitly states it is NOT a hostile multi-tenant boundary. "
        "sessionKey is routing, not authorization. Any user messaging a tool-enabled agent can steer its full "
        "permission set. qqlaw addresses this with per-tenant pods, IAM-enforced authorization, and tool-level RBAC.",
        callout_style
    ))

    # 2.7 Automation
    story.append(Paragraph("2.7 Automation Engine", h2_style))
    story.append(Paragraph("The Gateway includes a built-in cron scheduler, heartbeat system, and webhook handler:", body_style))
    auto_items = [
        "<b>Cron:</b> Persistent jobs (at/every/cron), main or isolated execution, delivery modes (announce/webhook/none)",
        "<b>Heartbeats:</b> Periodic agent polls for proactive work — batch checks, memory maintenance, inbox monitoring",
        "<b>Webhooks:</b> Inbound HTTP triggers that spawn agent turns or enqueue events",
        "<b>Gmail Pub/Sub:</b> Real-time email notification integration",
    ]
    for item in auto_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    # 2.8 Media
    story.append(Paragraph("2.8 Multi-Channel Media Pipeline", h2_style))
    story.append(Paragraph(
        "Unified media handling across 25+ surfaces: images, audio, video, documents. Voice transcription hooks, "
        "size caps, temp file lifecycle, per-channel format adaptation. Block streaming with coalescing for long responses.",
        body_style
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # 3. WHY OPENCLAW ACHIEVED RAPID ADOPTION
    # ══════════════════════════════════════════
    story.append(Paragraph("3. Why OpenClaw Achieved Rapid Adoption", h1_style))
    story.append(hr())

    story.append(Paragraph("3.1 Zero-to-Agent in 5 Minutes", h2_style))
    story.append(Paragraph(
        "The onboarding wizard (<font face='Courier' size=9>openclaw onboard --install-daemon</font>) handles "
        "API keys, channel pairing, workspace init, and daemon installation in one interactive CLI session. "
        "The BOOTSTRAP.md ritual gives the agent a personality-discovery conversation on first run, eliminating "
        "the typical \"blank canvas\" problem.",
        body_style
    ))

    story.append(Paragraph("3.2 Channel-First Design", h2_style))
    story.append(Paragraph(
        "Unlike frameworks that treat messaging as an afterthought, OpenClaw was built channels-first. Day-one support "
        "for WhatsApp, Telegram, Discord, Slack, Signal, iMessage, Teams, and 15+ more surfaces means users interact "
        "from the app they already live in — no new URL, no new app to install.",
        body_style
    ))

    # Adoption chart
    chart_d = Drawing(450, 170)
    chart_d.add(String(225, 158, "Adoption Driver Impact Assessment", fontSize=10, fillColor=ACCENT_BLUE, textAnchor='middle', fontName='Helvetica-Bold'))
    bc = VerticalBarChart()
    bc.x = 60; bc.y = 25; bc.height = 115; bc.width = 350
    bc.data = [[92, 88, 85, 82, 78, 75]]
    bc.categoryAxis.categoryNames = ['Channel\nFirst', 'Zero\nSetup', 'Self\nHosted', 'Open\nSource', 'Skills\nEcosystem', 'Voice\n+ Canvas']
    bc.categoryAxis.labels.fontSize = 7
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 100
    bc.valueAxis.labels.fontSize = 7
    bc.bars[0].fillColor = ACCENT_TEAL
    chart_d.add(bc)
    story.append(chart_d)
    story.append(Paragraph("Figure 4: Estimated Adoption Impact by Feature Category", caption_style))

    story.append(Paragraph("3.3 Personal Assistant Trust Model", h2_style))
    story.append(Paragraph(
        "By scoping to \"one trusted operator per gateway,\" OpenClaw avoids multi-tenant authorization complexity. "
        "The agent has full access to the operator's tools, files, devices, browser, and shell — making it genuinely "
        "useful rather than a restricted chatbot. This \"trust by default\" creates experiences that feel like a real assistant.",
        body_style
    ))

    story.append(Paragraph("3.4 Developer-Centric Extensibility", h2_style))
    story.append(Paragraph(
        "The Skills system, ClawHub registry, workspace files (SOUL.md for persona, AGENTS.md for behavior), "
        "and plugin architecture create deep customizability. Users don't just configure — they teach. The agent "
        "learns from workspace files and memory, creating emergent personalization that deepens over time.",
        body_style
    ))

    story.append(Paragraph("3.5 Self-Hosted Sovereignty", h2_style))
    story.append(Paragraph(
        "Data stays on your machine. Conversations don't train someone else's model. You choose your LLM provider. "
        "MIT license means no usage fees beyond model API costs. This positions OpenClaw as the \"Linux of AI assistants\" "
        "— a framing that resonates in an era of data sovereignty concerns.",
        body_style
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # 4. QQLAW ARCHITECTURE
    # ══════════════════════════════════════════
    story.append(Paragraph("4. qqlaw — Enterprise Multi-Tenant Architecture", h1_style))
    story.append(hr())
    story.append(Paragraph(
        "qqlaw is an enterprise agentic platform inspired by OpenClaw's architectural patterns but purpose-built for "
        "corporate multi-tenant deployment. It preserves the strengths (workspace isolation, skill composability, "
        "channel universality) while adding enterprise foundations (authorization, hard isolation, auditability).",
        body_style
    ))

    # 4.1
    story.append(Paragraph("4.1 From Personal to Corporate: The Gap", h2_style))
    gaps = [
        "<b>Trust model inversion:</b> Personal = trust by default. Enterprise = zero trust by default",
        "<b>Authorization:</b> OpenClaw's sessionKey is routing, not auth. qqlaw needs RBAC/ABAC per tool, per resource",
        "<b>Isolation:</b> Shared-process agents can reach each other's files. qqlaw needs hard container boundaries",
        "<b>Auditability:</b> JSONL transcripts are per-agent files. qqlaw needs centralized, immutable audit logs",
        "<b>Scalability:</b> Single-process Gateway limits vertical scale. qqlaw needs horizontal scaling",
        "<b>Compliance:</b> No built-in data classification, retention policies, or regulatory controls",
    ]
    for g in gaps:
        story.append(Paragraph(f'• {g}', bullet_style))

    # 4.2
    story.append(Paragraph("4.2 qqlaw Architecture Overview", h2_style))
    story.append(diagram_qqlaw_enterprise())
    story.append(Paragraph("Figure 5: qqlaw Enterprise Multi-Tenant Architecture", caption_style))

    # 4.3
    story.append(Paragraph("4.3 Tenant Isolation Model", h2_style))
    story.append(Paragraph(
        "qqlaw uses <b>pod-per-tenant isolation</b> — each tenant gets a dedicated Gateway-derived instance "
        "running in its own Kubernetes pod:",
        body_style
    ))
    isolation_items = [
        "<b>Namespace isolation:</b> Kubernetes namespace per tenant with network policies",
        "<b>Dedicated workspace:</b> Tenant workspace on persistent volume (not shared filesystem)",
        "<b>Sandboxed execution:</b> All tool execution in gVisor containers within the tenant pod",
        "<b>Credential isolation:</b> Vault-backed per-tenant secrets (model API keys, channel tokens)",
        "<b>Session store:</b> Per-tenant PostgreSQL schema (replacing JSONL) for query capability",
        "<b>Resource quotas:</b> CPU/memory limits, token budgets, and rate limiting per tenant",
    ]
    for item in isolation_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    # 4.4
    story.append(Paragraph("4.4 Identity & Access Management", h2_style))
    iam_data = [
        ['Layer', 'OpenClaw (Personal)', 'qqlaw (Enterprise)'],
        ['Authentication', 'Device pairing +\nchallenge-response', 'OIDC / SAML SSO +\nMFA enforcement'],
        ['Authorization', 'sessionKey routing\n(no per-user auth)', 'RBAC + ABAC per tool,\nresource, channel'],
        ['Identity', 'Device token\n(paired metadata)', 'Corporate identity +\nfederation (Okta/Entra)'],
        ['Admin', 'CLI + config file', 'Admin portal + API +\nfull audit trail'],
        ['Multi-user', 'dmScope per-peer\n(session isolation)', 'Tenant admin + user roles\n+ permission boundaries'],
    ]
    iam_table = Table(iam_data, colWidths=[80, 150, 170])
    iam_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QQ_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor("#e3f2fd")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(iam_table)
    story.append(Paragraph("Table 3: IAM — OpenClaw vs qqlaw", caption_style))

    # 4.5
    story.append(Paragraph("4.5 Shared Services Layer", h2_style))
    shared_items = [
        "<b>Model Router:</b> Central LLM gateway handling model selection, failover, token accounting, and cost "
        "attribution per tenant. Inspired by OpenClaw's model failover but with per-tenant quotas and billing.",
        "<b>Skill Registry:</b> Centralized skill catalog with approval workflows, version pinning, and security scanning. "
        "Tenants select from approved skills only — no arbitrary code execution.",
        "<b>Channel Hub:</b> Shared channel infrastructure (Slack bots, Teams apps) with per-tenant message routing.",
        "<b>Object Store:</b> S3-compatible storage for media, transcripts, and artifacts with per-tenant bucket prefixes.",
    ]
    for item in shared_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    # 4.6
    story.append(Paragraph("4.6 Observability & Compliance", h2_style))
    obs_items = [
        "<b>Audit logs:</b> Every tool invocation, model call, and message logged immutably with tenant/user attribution",
        "<b>Metrics:</b> Token usage, latency, error rates, session counts — per tenant, agent, model (Prometheus + Grafana)",
        "<b>Traces:</b> OpenTelemetry from message receipt through agent execution to response delivery",
        "<b>Data classification:</b> PII detection/redaction with configurable retention policies",
        "<b>Compliance exports:</b> SOC 2 Type II evidence, GDPR DSAR support",
    ]
    for item in obs_items:
        story.append(Paragraph(f'• {item}', bullet_style))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # 5. BAIONIQ INTEGRATION
    # ══════════════════════════════════════════
    story.append(Paragraph("5. Baioniq Integration Strategy", h1_style))
    story.append(hr())

    story.append(Paragraph("5.1 Baioniq Platform Overview", h2_style))
    story.append(Paragraph(
        "Baioniq is Quantiphi's enterprise GenAI platform enabling organizations to own their GenAI stack. "
        "Key capabilities include:",
        body_style
    ))
    baioniq_caps = [
        "<b>GenAI Application Framework:</b> Pre-built accelerators for document intelligence, conversational AI, "
        "code generation, and content creation",
        "<b>Model Management:</b> Multi-model orchestration across Vertex AI, Bedrock, Azure OpenAI, and open-source — "
        "with evaluation, selection, and lifecycle management",
        "<b>RAG Pipeline:</b> Enterprise retrieval-augmented generation with vector stores, document processing, "
        "and knowledge base management",
        "<b>Guardrails & Governance:</b> Content safety, hallucination detection, prompt injection defense, "
        "and responsible AI policy enforcement",
        "<b>Enterprise Integration:</b> Connectors for Salesforce, ServiceNow, SAP, Confluence, SharePoint",
        "<b>Deployment & Ops:</b> K8s-native deployment, auto-scaling, A/B testing, operational dashboards",
    ]
    for cap in baioniq_caps:
        story.append(Paragraph(f'• {cap}', bullet_style))

    # 5.2
    story.append(Paragraph("5.2 Synergy Map: qqlaw ↔ Baioniq", h2_style))
    synergy_data = [
        ['Capability', 'qqlaw Provides', 'Baioniq Provides', 'Combined Value'],
        ['Agent\nExecution', 'Tool use, exec,\nbrowser, canvas', 'Model routing,\nguardrails', 'Governed\nagentic AI'],
        ['Channel\nDelivery', '25+ messaging\nsurfaces', 'Enterprise\nconnectors', 'Omnichannel\nagent UX'],
        ['Knowledge', 'Workspace files,\nmemory, skills', 'RAG pipeline,\nvector stores', 'Context-rich\nagent memory'],
        ['Security', 'Pod isolation,\ntool RBAC', 'Guardrails,\ngovernance', 'Defense-in-\ndepth'],
        ['Ops', 'Cron, heartbeats,\nwebhooks', 'K8s deploy,\nmonitoring', 'Enterprise\nautomation'],
        ['Persona', 'SOUL.md,\nworkspace files', 'Prompt\ntemplates', 'Brand-aligned\nagent personas'],
    ]
    synergy_table = Table(synergy_data, colWidths=[65, 105, 105, 95])
    synergy_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BAIONIQ_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor("#f3e5f5")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(synergy_table)
    story.append(Paragraph("Table 4: qqlaw ↔ Baioniq Synergy Matrix", caption_style))

    # 5.3
    story.append(Paragraph("5.3 Integration Architecture", h2_style))
    story.append(diagram_baioniq_integration())
    story.append(Paragraph("Figure 6: Baioniq + qqlaw Integration Architecture", caption_style))

    story.append(Paragraph('<b>Integration touchpoints:</b>', body_style))
    integration_items = [
        "<b>Model Router Bridge:</b> Tenant pods route LLM calls through Baioniq's model management — giving Baioniq "
        "control over selection, cost attribution, guardrails, and A/B testing while qqlaw handles execution.",
        "<b>RAG Skill:</b> Custom skill bridging qqlaw's tool interface to Baioniq's RAG pipeline. Agent queries "
        "enterprise knowledge (policies, CRM, docs) via Baioniq's retrieval API.",
        "<b>Guardrails Middleware:</b> Baioniq's content safety wraps agent I/O. Every user message is filtered "
        "before the agent; every response is checked before delivery.",
        "<b>Workspace Templates:</b> Baioniq manages tenant workspace provisioning — pre-configured personas, "
        "operating procedures, and approved skill sets per tenant/department.",
        "<b>Telemetry Pipeline:</b> Agent execution telemetry flows into Baioniq's operational dashboard alongside "
        "RAG metrics and model performance data.",
    ]
    for item in integration_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    # 5.4
    story.append(Paragraph("5.4 Differentiation & GTM Positioning", h2_style))
    story.append(Paragraph(
        '<b>"Baioniq Agents" — Enterprise Agentic AI, Delivered Where Your Teams Already Work</b>',
        ParagraphStyle('Tagline', parent=body_style, fontSize=12, textColor=BAIONIQ_PURPLE, alignment=TA_CENTER, spaceBefore=8, spaceAfter=12)
    ))

    diff_data = [
        ['Competitor', 'Limitation', 'Baioniq Agents Advantage'],
        ['Microsoft\nCopilot', 'Locked to M365\necosystem', 'Any channel (WhatsApp, Slack,\nTeams, custom) + any model'],
        ['Google\nAgentspace', 'Google Cloud\nonly', 'Multi-cloud + self-hosted option\nfor regulated industries'],
        ['Salesforce\nAgentforce', 'CRM-centric,\nlimited tooling', 'Full tool execution (browser,\ncode, devices) + RAG'],
        ['Custom\nLangChain', 'DIY ops burden,\nno channel layer', 'Managed platform with\n25+ channels built-in'],
        ['OpenClaw\n(OSS)', 'Personal only,\nno enterprise', 'Multi-tenant, governed,\ncompliant, supported'],
    ]
    diff_table = Table(diff_data, colWidths=[75, 120, 195])
    diff_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUANTIPHI_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(diff_table)
    story.append(Paragraph("Table 5: Competitive Differentiation Matrix", caption_style))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # 6. ROADMAP
    # ══════════════════════════════════════════
    story.append(Paragraph("6. Implementation Roadmap", h1_style))
    story.append(hr())

    roadmap_data = [
        ['Phase', 'Timeline', 'Deliverables', 'Dependencies'],
        ['Phase 1:\nFoundation', 'Weeks 1–6', '• qqlaw Gateway engine\n• Pod-per-tenant K8s manifests\n• IAM integration (OIDC)\n• PostgreSQL session store', 'K8s cluster,\nIdentity provider,\nPostgres instance'],
        ['Phase 2:\nBaioniq\nBridge', 'Weeks 7–12', '• Model Router Bridge API\n• RAG Skill implementation\n• Guardrails middleware\n• Workspace template system', 'Baioniq API access,\nRAG pipeline,\nGuardrails service'],
        ['Phase 3:\nChannels\n& Skills', 'Weeks 13–18', '• Enterprise Channel Hub\n• Skill Registry + approval flow\n• Admin portal MVP\n• Per-tenant metrics/dashboards', 'Slack/Teams apps,\nUI framework,\nPrometheus/Grafana'],
        ['Phase 4:\nHarden\n& Ship', 'Weeks 19–24', '• Security audit + pen test\n• SOC 2 evidence pack\n• Performance benchmarks\n• Customer pilot (2 tenants)', 'Security team,\nCompliance team,\nPilot customers'],
    ]
    roadmap_table = Table(roadmap_data, colWidths=[65, 65, 195, 115])
    roadmap_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QQ_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor("#e3f2fd")]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(roadmap_table)
    story.append(Paragraph("Table 6: qqlaw Implementation Roadmap — 24 Weeks", caption_style))

    story.append(Paragraph("<b>Estimated team:</b> 2 platform engineers, 1 Baioniq specialist, 1 security engineer, "
                           "0.5 PM. Total: ~4.5 FTE for 6 months.", body_style))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # 7. RISK ANALYSIS
    # ══════════════════════════════════════════
    story.append(Paragraph("7. Risk Analysis & Mitigations", h1_style))
    story.append(hr())

    risk_data = [
        ['Risk', 'Severity', 'Likelihood', 'Mitigation'],
        ['Upstream OpenClaw\npatterns diverge\nfrom qqlaw needs', 'Medium', 'Medium', 'qqlaw is inspired-by, not\na fork — no upstream\ndependency'],
        ['Pod-per-tenant\ncost at scale\n(100+ tenants)', 'Medium', 'Medium', 'Resource right-sizing;\nshared-pool mode for\nsmaller tenants'],
        ['Channel API\nbreaking changes\n(WhatsApp/Slack)', 'Medium', 'Medium', 'Abstract channel adapter\nlayer; use official APIs\n(WABA, Bolt)'],
        ['Model vendor\nlock-in through\nBaioniq bridge', 'Medium', 'Low', 'qqlaw multi-model support\nas escape hatch;\nopen LLM fallbacks'],
        ['Security vuln\nin agent tool\nexecution', 'Critical', 'Medium', 'gVisor sandboxing;\nnetwork policies;\ntool-level RBAC'],
        ['Enterprise adoption\nfriction (teams\ndon\'t want agents)', 'High', 'Medium', 'Start with simple use cases\n(Q&A bots); graduate to\nfull tool enablement'],
    ]
    risk_table = Table(risk_data, colWidths=[100, 55, 65, 180])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT_RED),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor("#fce4ec")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(risk_table)
    story.append(Paragraph("Table 7: Risk Assessment Matrix", caption_style))
    story.append(PageBreak())

    # ══════════════════════════════════════════
    # 8. CONCLUSION
    # ══════════════════════════════════════════
    story.append(Paragraph("8. Conclusion & Recommendations", h1_style))
    story.append(hr())
    story.append(Paragraph(
        "OpenClaw represents a rare architectural achievement: a genuinely useful AI agent framework built by solving "
        "the right problems in the right order. Its rapid adoption validates the hypothesis that people want AI assistants "
        "delivered through their existing communication channels — not through yet another web application.",
        body_style
    ))
    story.append(Paragraph(
        "qqlaw takes these validated patterns and rebuilds them for enterprise reality: multi-tenant authorization, "
        "hard container isolation, centralized audit logs, and compliance-ready infrastructure. It is not a copy or "
        "fork of OpenClaw — it is an original platform informed by the same architectural insights.",
        body_style
    ))
    story.append(Paragraph(
        "Integrating qqlaw with Baioniq creates a platform that neither could achieve alone:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Baioniq without agents</b> = powerful GenAI stack, but outputs trapped in dashboards and APIs<br/>"
        "• <b>Agents without Baioniq</b> = powerful execution, but no governance, RAG, or enterprise integration<br/>"
        "• <b>Baioniq + qqlaw</b> = governed, enterprise-grade agentic AI delivered through 25+ channels with "
        "full tool execution, RAG-powered knowledge, and brand-aligned personas",
        callout_style
    ))

    story.append(Paragraph("<b>Recommendations:</b>", h3_style))
    recs = [
        "<b>1. Prototype immediately:</b> Build a single-tenant qqlaw PoC connected to Baioniq's model router "
        "and RAG pipeline. Target: working demo in 3 weeks.",
        "<b>2. Start with internal deployment:</b> Deploy qqlaw for Quantiphi's own teams first — "
        "engineering, sales, delivery. Dogfooding surfaces real enterprise requirements.",
        "<b>3. Position for GCP Next / re:Invent:</b> A \"Baioniq Agents\" demo showing enterprise AI agents "
        "responding across Slack, Teams, and WhatsApp with Vertex AI backing would be a compelling showcase.",
        "<b>4. Engage cloud partners:</b> Position qqlaw as a value-add to Google Cloud and AWS partnerships — "
        "enterprise customers get agentic AI without building the infrastructure.",
        "<b>5. Consider IP protection:</b> The specific architecture of Baioniq's guardrails wrapping qqlaw's "
        "agent execution engine with multi-tenant workspace isolation is novel and potentially patentable.",
    ]
    for r in recs:
        story.append(Paragraph(r, bullet_style))

    story.append(Spacer(1, 0.5*inch))
    story.append(hr())
    story.append(Paragraph("— End of Report —",
        ParagraphStyle('EndMark', parent=body_style, alignment=TA_CENTER, fontSize=10, textColor=DARK_GRAY)))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}<br/>"
        "Sources: OpenClaw Docs (docs.openclaw.ai), GitHub (github.com/openclaw/openclaw), "
        "Quantiphi (quantiphi.com)<br/>"
        "<i>qqlaw is an original design concept. Not affiliated with or derived from OpenClaw.</i>",
        ParagraphStyle('Footer', parent=body_style, alignment=TA_CENTER, fontSize=8, textColor=MED_GRAY)
    ))

    doc.build(story)
    print(f"✅ Report generated: {OUTPUT_PATH}")
    print(f"   Size: {os.path.getsize(OUTPUT_PATH) / 1024:.0f} KB")

if __name__ == "__main__":
    build_report()
