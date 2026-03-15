#!/usr/bin/env python3
"""
OpenClaw Architecture Deep Dive & Enterprise Multi-Tenant Proposal
Linked to Quantiphi's Baioniq Platform
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, ListFlowable, ListItem, KeepTogether, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
import os
from datetime import datetime

OUTPUT_PATH = os.path.expanduser("~/.openclaw/workspace/OpenClaw_Enterprise_Architecture_Report.pdf")

# ── Colors ──
DARK_BG = HexColor("#1a1a2e")
ACCENT_BLUE = HexColor("#0f3460")
ACCENT_TEAL = HexColor("#16a085")
ACCENT_RED = HexColor("#e74c3c")
ACCENT_ORANGE = HexColor("#e67e22")
ACCENT_GREEN = HexColor("#27ae60")
ACCENT_PURPLE = HexColor("#8e44ad")
LIGHT_GRAY = HexColor("#f5f5f5")
MED_GRAY = HexColor("#bdc3c7")
DARK_GRAY = HexColor("#2c3e50")
QUANTIPHI_BLUE = HexColor("#003366")
BAIONIQ_PURPLE = HexColor("#6c3483")

styles = getSampleStyleSheet()

# Custom styles
title_style = ParagraphStyle(
    'CustomTitle', parent=styles['Title'],
    fontSize=28, leading=34, textColor=ACCENT_BLUE,
    spaceAfter=6, alignment=TA_CENTER
)
subtitle_style = ParagraphStyle(
    'Subtitle', parent=styles['Normal'],
    fontSize=14, leading=18, textColor=DARK_GRAY,
    alignment=TA_CENTER, spaceAfter=20
)
h1_style = ParagraphStyle(
    'H1', parent=styles['Heading1'],
    fontSize=20, leading=24, textColor=ACCENT_BLUE,
    spaceBefore=24, spaceAfter=12,
    borderWidth=0, borderColor=ACCENT_TEAL, borderPadding=4
)
h2_style = ParagraphStyle(
    'H2', parent=styles['Heading2'],
    fontSize=16, leading=20, textColor=DARK_GRAY,
    spaceBefore=16, spaceAfter=8
)
h3_style = ParagraphStyle(
    'H3', parent=styles['Heading3'],
    fontSize=13, leading=17, textColor=ACCENT_PURPLE,
    spaceBefore=12, spaceAfter=6
)
body_style = ParagraphStyle(
    'Body', parent=styles['Normal'],
    fontSize=10.5, leading=15, textColor=black,
    alignment=TA_JUSTIFY, spaceAfter=8
)
bullet_style = ParagraphStyle(
    'Bullet', parent=body_style,
    leftIndent=20, bulletIndent=10, spaceAfter=4
)
callout_style = ParagraphStyle(
    'Callout', parent=body_style,
    fontSize=10, leading=14, textColor=DARK_GRAY,
    leftIndent=15, rightIndent=15, spaceBefore=8, spaceAfter=8,
    backColor=HexColor("#eaf2f8"), borderWidth=1, borderColor=ACCENT_BLUE,
    borderPadding=8
)
code_style = ParagraphStyle(
    'Code', parent=styles['Code'],
    fontSize=8.5, leading=11, textColor=HexColor("#2c3e50"),
    backColor=HexColor("#f8f9fa"), borderWidth=0.5, borderColor=MED_GRAY,
    borderPadding=6, leftIndent=10, rightIndent=10, spaceAfter=8
)
caption_style = ParagraphStyle(
    'Caption', parent=styles['Normal'],
    fontSize=9, leading=12, textColor=DARK_GRAY,
    alignment=TA_CENTER, spaceBefore=4, spaceAfter=12, italic=True
)

def hr():
    return HRFlowable(width="100%", thickness=1, color=MED_GRAY, spaceBefore=6, spaceAfter=6)

def make_box_diagram(width, height, boxes, connections=None, title_text=None):
    """Create a simple box-and-arrow diagram."""
    d = Drawing(width, height)
    if title_text:
        d.add(String(width/2, height-15, title_text, fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle', fontName='Helvetica-Bold'))
    for box in boxes:
        x, y, w, h, label, color = box
        d.add(Rect(x, y, w, h, fillColor=color, strokeColor=HexColor("#333333"), strokeWidth=1, rx=4, ry=4))
        # Multi-line support
        lines = label.split('\n')
        for i, line in enumerate(lines):
            d.add(String(x + w/2, y + h/2 - 5 + (len(lines)-1-i)*12 - (len(lines)-1)*6,
                        line, fontSize=8, fillColor=white, textAnchor='middle', fontName='Helvetica-Bold'))
    if connections:
        for conn in connections:
            x1, y1, x2, y2 = conn
            d.add(Line(x1, y1, x2, y2, strokeColor=DARK_GRAY, strokeWidth=1.5))
            # Arrow head
            if y2 < y1:  # downward
                d.add(Polygon(points=[x2-4, y2+6, x2+4, y2+6, x2, y2], fillColor=DARK_GRAY))
            elif x2 > x1:  # rightward
                d.add(Polygon(points=[x2-6, y2-4, x2-6, y2+4, x2, y2], fillColor=DARK_GRAY))
            elif x2 < x1:  # leftward
                d.add(Polygon(points=[x2+6, y2-4, x2+6, y2+4, x2, y2], fillColor=DARK_GRAY))
    return d

def build_report():
    doc = SimpleDocTemplate(
        OUTPUT_PATH, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch
    )
    story = []

    # ══════════════════════════════════════════════════════════════
    # COVER PAGE
    # ══════════════════════════════════════════════════════════════
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("OpenClaw Architecture Deep Dive", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Core Innovation Analysis & Enterprise Multi-Tenant Proposal", subtitle_style))
    story.append(hr())
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(
        '<b>Prepared for:</b> Quantiphi — Baioniq Platform Strategy Team<br/>'
        f'<b>Date:</b> {datetime.now().strftime("%B %d, %Y")}<br/>'
        '<b>Author:</b> Dagnachew Birru<br/>'
        '<b>Classification:</b> Internal — Strategic Analysis',
        ParagraphStyle('CoverMeta', parent=body_style, alignment=TA_CENTER, fontSize=11, leading=16, textColor=DARK_GRAY)
    ))
    story.append(Spacer(1, 0.5*inch))

    # Cover diagram
    cover_diag = make_box_diagram(500, 120, [
        (30, 60, 100, 40, "OpenClaw\nGateway", ACCENT_BLUE),
        (200, 60, 100, 40, "Enterprise\nMulti-Tenant", ACCENT_TEAL),
        (370, 60, 100, 40, "Baioniq\nIntegration", BAIONIQ_PURPLE),
        (200, 5, 100, 35, "Agentic AI\nPlatform", ACCENT_ORANGE),
    ], [
        (130, 80, 200, 80),
        (300, 80, 370, 80),
        (250, 60, 250, 40),
    ])
    story.append(cover_diag)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ══════════════════════════════════════════════════════════════
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
        ("4.", "Enterprise Multi-Tenant Architecture Proposal"),
        ("  4.1", "From Personal to Corporate: The Gap"),
        ("  4.2", "Proposed Architecture Overview"),
        ("  4.3", "Tenant Isolation Model"),
        ("  4.4", "Identity & Access Management"),
        ("  4.5", "Shared Services Layer"),
        ("  4.6", "Observability & Compliance"),
        ("5.", "Baioniq Integration Strategy"),
        ("  5.1", "Baioniq Platform Overview"),
        ("  5.2", "Synergy Map: OpenClaw ↔ Baioniq"),
        ("  5.3", "Proposed Integration Architecture"),
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

    # ══════════════════════════════════════════════════════════════
    # 1. EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════
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
        "innovations that enabled its rapid adoption, and proposes a corporate multi-tenant architecture that adapts "
        "these principles for enterprise deployment. The proposal is specifically designed to complement and extend "
        "Quantiphi's <b>Baioniq</b> platform — creating a differentiated agentic AI offering that combines Baioniq's "
        "enterprise GenAI stack with OpenClaw-inspired agent orchestration, multi-channel delivery, and workspace isolation.",
        body_style
    ))
    story.append(Paragraph(
        '<b>Key findings:</b>', body_style
    ))
    findings = [
        "OpenClaw's single-Gateway architecture eliminates distributed coordination overhead, enabling sub-second message-to-response latency",
        "Multi-agent routing with workspace isolation provides a blueprint for tenant separation without container-per-user overhead",
        "The Skills platform (AgentSkills-compatible) creates a composable tool ecosystem applicable to enterprise tool registries",
        "Channel-first design (25+ messaging surfaces) is directly translatable to enterprise communication consolidation",
        "The personal assistant trust model must be fundamentally redesigned for hostile multi-tenant enterprise use",
    ]
    for f in findings:
        story.append(Paragraph(f'• {f}', bullet_style))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 2. OPENCLAW ARCHITECTURE — TECHNICAL DEEP DIVE
    # ══════════════════════════════════════════════════════════════
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

    # Gateway architecture diagram
    gw_diag = make_box_diagram(500, 200, [
        # Top row - channels
        (10, 150, 65, 30, "WhatsApp", HexColor("#25D366")),
        (85, 150, 65, 30, "Telegram", HexColor("#0088cc")),
        (160, 150, 65, 30, "Discord", HexColor("#5865F2")),
        (235, 150, 65, 30, "Slack", HexColor("#4A154B")),
        (310, 150, 65, 30, "Signal", HexColor("#3A76F0")),
        (385, 150, 65, 30, "iMessage", HexColor("#34C759")),
        # Gateway box
        (80, 70, 340, 50, "Gateway Control Plane (ws://127.0.0.1:18789)", ACCENT_BLUE),
        # Bottom row - clients
        (10, 10, 80, 35, "Pi Agent\n(RPC)", ACCENT_TEAL),
        (110, 10, 80, 35, "CLI\nSurface", DARK_GRAY),
        (210, 10, 80, 35, "Web UI\nControl", ACCENT_ORANGE),
        (310, 10, 80, 35, "macOS\nApp", HexColor("#555555")),
        (410, 10, 60, 35, "iOS/\nAndroid", ACCENT_PURPLE),
    ], [
        (42, 150, 150, 120), (117, 150, 200, 120), (192, 150, 250, 120),
        (267, 150, 300, 120), (342, 150, 350, 120), (417, 150, 400, 120),
        (150, 70, 50, 45), (250, 70, 150, 45), (300, 70, 250, 45),
        (350, 70, 350, 45), (400, 70, 440, 45),
    ])
    story.append(gw_diag)
    story.append(Paragraph("Figure 1: OpenClaw Gateway Architecture — Single Control Plane", caption_style))

    story.append(Paragraph('<b>Key architectural properties:</b>', body_style))
    gw_props = [
        "<b>Single-process design:</b> No distributed coordination, no service mesh, no message queue. The Gateway IS the system.",
        "<b>WebSocket-native:</b> All control plane communication (clients, nodes, tools) uses typed WS frames with JSON Schema validation.",
        "<b>Loopback-bound:</b> Default bind to 127.0.0.1:18789. External access via Tailscale Serve/Funnel or SSH tunnels only.",
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
        'Client → Gateway:  {type:"req", id, method:"connect", params:{auth:{token}, role, caps}}\n'
        'Gateway → Client:  {type:"res", id, ok:true, payload:{snapshot: {presence, health}}}\n'
        'Gateway → Client:  {type:"event", event:"presence", payload:{...}}\n'
        'Client → Gateway:  {type:"req", id, method:"agent", params:{message, idempotencyKey}}\n'
        'Gateway → Client:  {type:"res", id, ok:true, payload:{runId, status:"accepted"}}\n'
        'Gateway → Client:  {type:"event", event:"agent", payload:{streaming chunks...}}\n'
        'Gateway → Client:  {type:"res", id, ok:true, payload:{runId, status:"complete", summary}}\n'
        '</font>',
        code_style
    ))
    story.append(Paragraph(
        "Device pairing uses challenge-response signing (v3 payload binds platform + deviceFamily). "
        "Local connects (loopback/tailnet) can be auto-approved. Non-local connects require explicit operator approval. "
        "The Gateway pins paired device metadata on reconnect — metadata changes require re-pairing.",
        body_style
    ))

    # 2.3 Multi-Agent Routing
    story.append(Paragraph("2.3 Multi-Agent Routing Engine", h2_style))
    story.append(Paragraph(
        "OpenClaw's multi-agent system enables multiple isolated \"brains\" to coexist on a single Gateway. Each agent is a "
        "fully scoped entity with its own workspace (AGENTS.md, SOUL.md, USER.md), state directory (auth profiles, model "
        "registry), and session store. This is the architectural pattern most directly relevant to enterprise multi-tenancy.",
        body_style
    ))

    # Multi-agent diagram
    ma_diag = make_box_diagram(500, 160, [
        (30, 110, 120, 35, "Inbound Message", ACCENT_ORANGE),
        (200, 110, 120, 35, "Binding Router", ACCENT_BLUE),
        # Agent workspaces
        (50, 20, 100, 55, "Agent: main\nWorkspace A\nSessions A", ACCENT_TEAL),
        (200, 20, 100, 55, "Agent: coding\nWorkspace B\nSessions B", ACCENT_PURPLE),
        (350, 20, 100, 55, "Agent: social\nWorkspace C\nSessions C", ACCENT_GREEN),
    ], [
        (150, 127, 200, 127),
        (260, 110, 100, 75),
        (260, 110, 250, 75),
        (260, 110, 400, 75),
    ])
    story.append(ma_diag)
    story.append(Paragraph("Figure 2: Multi-Agent Routing — Deterministic Binding Resolution", caption_style))

    story.append(Paragraph('<b>Binding resolution order (most-specific wins):</b>', body_style))
    bindings = [
        "1. <b>Peer match</b> — exact DM/group/channel ID",
        "2. <b>Parent peer</b> — thread inheritance",
        "3. <b>Guild + Roles</b> — Discord role-based routing",
        "4. <b>Guild ID</b> — Discord server level",
        "5. <b>Team ID</b> — Slack workspace level",
        "6. <b>Account ID</b> — channel account match",
        "7. <b>Channel</b> — channel-level wildcard (accountId: \"*\")",
        "8. <b>Default agent</b> — fallback (first in list or marked default)",
    ]
    for b in bindings:
        story.append(Paragraph(f'  {b}', bullet_style))

    story.append(Paragraph(
        "Critical design insight: auth profiles are per-agent. Each agent reads from its own "
        "<font face='Courier' size=9>~/.openclaw/agents/&lt;agentId&gt;/agent/auth-profiles.json</font>. "
        "Main agent credentials are never shared automatically. Reusing agentDir across agents causes auth/session collisions.",
        callout_style
    ))

    # 2.4 Session Management
    story.append(Paragraph("2.4 Session Management & Isolation", h2_style))
    story.append(Paragraph(
        "Sessions are the fundamental unit of conversational state. OpenClaw's session model provides four DM scoping modes "
        "that control how direct messages are grouped:",
        body_style
    ))

    session_data = [
        ['Mode', 'Key Pattern', 'Use Case'],
        ['main (default)', 'agent:<id>:<mainKey>', 'Single user, all DMs share context'],
        ['per-peer', 'agent:<id>:direct:<peerId>', 'Multi-user, isolate by sender'],
        ['per-channel-peer', 'agent:<id>:<ch>:direct:<peer>', 'Multi-user inbox (recommended)'],
        ['per-account-\nchannel-peer', 'agent:<id>:<ch>:<acct>:\ndirect:<peer>', 'Multi-account isolation'],
    ]
    session_table = Table(session_data, colWidths=[110, 170, 160])
    session_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(session_table)
    story.append(Paragraph("Table 1: Session DM Scoping Modes", caption_style))

    story.append(Paragraph(
        "Session state is gateway-owned. Transcripts are stored as JSONL files at "
        "<font face='Courier' size=8>~/.openclaw/agents/&lt;agentId&gt;/sessions/&lt;SessionId&gt;.jsonl</font>. "
        "Maintenance is configurable: pruneAfter (30d default), maxEntries (500), rotateBytes (10MB), and optional "
        "disk budgets (maxDiskBytes + highWaterBytes at 80%).",
        body_style
    ))

    # 2.5 Skills Platform
    story.append(Paragraph("2.5 Skills Platform & Plugin Ecosystem", h2_style))
    story.append(Paragraph(
        "The Skills platform is OpenClaw's extensibility engine. Skills are directories containing a SKILL.md with YAML "
        "frontmatter and instructions, compatible with the AgentSkills specification. They are loaded from three locations "
        "with clear precedence: workspace skills > managed/local skills > bundled skills.",
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
        ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(skills_table)
    story.append(Paragraph("Table 2: Skills Loading Precedence", caption_style))

    story.append(Paragraph(
        "Skills support gating via metadata: binary presence checks (requires.bins), environment variables (requires.env), "
        "config flags (requires.config), and OS filtering. The ClawHub registry (clawhub.com) provides discovery, installation, "
        "and synchronization. Skills can also ship with plugins, creating a two-tier extensibility model.",
        body_style
    ))

    # 2.6 Sandboxing
    story.append(Paragraph("2.6 Sandboxing & Security Model", h2_style))
    story.append(Paragraph(
        "OpenClaw operates under a <b>personal assistant trust model</b> — one trusted operator boundary per gateway. "
        "This is explicitly NOT a hostile multi-tenant security boundary. However, it provides optional Docker-based "
        "sandboxing to reduce blast radius when the model \"does something dumb.\"",
        body_style
    ))
    sandbox_items = [
        "<b>Modes:</b> off (default), non-main (sandbox non-main sessions only), all (every session sandboxed)",
        "<b>Scope:</b> per-session (one container each), per-agent (shared container), shared (global container)",
        "<b>Workspace access:</b> none (isolated), ro (read-only mount), rw (read-write mount)",
        "<b>Network:</b> Default no-network. Configurable via docker.network",
        "<b>Browser:</b> Dedicated sandbox browser with CDP, noVNC observer, CIDR allowlists",
        "<b>Elevated exec:</b> Explicitly bypasses sandbox — runs on host with elevated permissions",
    ]
    for item in sandbox_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    story.append(Paragraph(
        "⚠️ <b>Enterprise gap:</b> The security docs explicitly state that OpenClaw is NOT a hostile multi-tenant boundary. "
        "sessionKey is routing, not authorization. Any user who can message a tool-enabled agent can steer its full "
        "permission set. This is the single biggest architectural change needed for enterprise.",
        callout_style
    ))

    # 2.7 Automation
    story.append(Paragraph("2.7 Automation Engine", h2_style))
    story.append(Paragraph(
        "The Gateway includes a built-in cron scheduler, heartbeat system, and webhook handler:",
        body_style
    ))
    auto_items = [
        "<b>Cron:</b> Persistent jobs (at/every/cron schedules), main session or isolated execution, delivery modes (announce/webhook/none), IANA timezone support",
        "<b>Heartbeats:</b> Periodic agent polls for proactive work — batch checks, memory maintenance, inbox monitoring",
        "<b>Webhooks:</b> Inbound HTTP triggers that spawn agent turns or enqueue events",
        "<b>Gmail Pub/Sub:</b> Real-time email notification integration",
    ]
    for item in auto_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    # 2.8 Media Pipeline
    story.append(Paragraph("2.8 Multi-Channel Media Pipeline", h2_style))
    story.append(Paragraph(
        "OpenClaw handles images, audio, video, and documents across 25+ messaging surfaces with a unified pipeline. "
        "Features include voice note transcription hooks, size caps, temp file lifecycle management, and per-channel "
        "format adaptation. Block streaming supports chunked delivery of long responses with coalescing to reduce "
        "single-line spam.",
        body_style
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 3. WHY OPENCLAW ACHIEVED RAPID ADOPTION
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("3. Why OpenClaw Achieved Rapid Adoption", h1_style))
    story.append(hr())

    # 3.1
    story.append(Paragraph("3.1 Zero-to-Agent in 5 Minutes", h2_style))
    story.append(Paragraph(
        "The onboarding wizard (<font face='Courier' size=9>openclaw onboard --install-daemon</font>) walks users through "
        "complete setup — API keys, channel pairing, workspace initialization, daemon installation — in a single interactive "
        "CLI session. The BOOTSTRAP.md ritual gives the agent a personality-discovery conversation on first run. "
        "This removes the typical \"blank canvas\" problem that plagues most agent frameworks.",
        body_style
    ))

    # 3.2
    story.append(Paragraph("3.2 Channel-First Design", h2_style))
    story.append(Paragraph(
        "Unlike frameworks that treat messaging as an afterthought (\"deploy a web UI, maybe add Slack later\"), "
        "OpenClaw was built channels-first. Day one support for WhatsApp, Telegram, Discord, Slack, Signal, iMessage, "
        "Google Chat, IRC, Microsoft Teams, Matrix, and 15+ more surfaces means users interact with their AI assistant "
        "from the app they already live in — no new app to install, no new URL to bookmark.",
        body_style
    ))

    # Adoption drivers chart
    chart_d = Drawing(450, 180)
    chart_d.add(String(225, 168, "Adoption Driver Impact Assessment", fontSize=10, fillColor=ACCENT_BLUE, textAnchor='middle', fontName='Helvetica-Bold'))
    bc = VerticalBarChart()
    bc.x = 60
    bc.y = 30
    bc.height = 120
    bc.width = 360
    bc.data = [[92, 88, 85, 82, 78, 75]]
    bc.categoryAxis.categoryNames = ['Channel\nFirst', 'Zero\nSetup', 'Self\nHosted', 'Open\nSource', 'Skills\nPlatform', 'Voice\n+ Canvas']
    bc.categoryAxis.labels.fontSize = 7
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 100
    bc.valueAxis.labels.fontSize = 7
    bc.bars[0].fillColor = ACCENT_TEAL
    chart_d.add(bc)
    story.append(chart_d)
    story.append(Paragraph("Figure 3: Estimated Adoption Impact by Feature Category (relative scoring)", caption_style))

    # 3.3
    story.append(Paragraph("3.3 Personal Assistant Trust Model", h2_style))
    story.append(Paragraph(
        "By explicitly scoping to \"one trusted operator boundary per gateway,\" OpenClaw avoids the complexity tax of "
        "multi-tenant authorization. The agent has full access to the operator's tools, files, and devices — which makes "
        "it genuinely useful (browser control, file editing, shell execution, camera access, home automation). "
        "This \"trust by default\" approach creates an experience that feels like a real assistant, not a restricted chatbot.",
        body_style
    ))

    # 3.4
    story.append(Paragraph("3.4 Developer-Centric Extensibility", h2_style))
    story.append(Paragraph(
        "The Skills system, ClawHub registry, workspace files (SOUL.md for persona, AGENTS.md for behavior, "
        "TOOLS.md for environment), and plugin architecture create a deeply customizable system. Users "
        "don't just configure — they teach. The agent learns from workspace files, memory files (MEMORY.md + daily notes), "
        "and skill instructions. This creates an emergent personalization effect that deepens over time.",
        body_style
    ))

    # 3.5
    story.append(Paragraph("3.5 Self-Hosted Sovereignty", h2_style))
    story.append(Paragraph(
        "In an era of increasing concern about data sovereignty and AI vendor lock-in, OpenClaw's self-hosted model "
        "resonates strongly. Your data stays on your machine. Your conversations aren't training someone else's model. "
        "You choose your LLM provider (Anthropic, OpenAI, Google, OpenRouter). MIT license means no usage fees beyond "
        "the underlying model API costs. This positions OpenClaw as the \"Linux of AI assistants.\"",
        body_style
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 4. ENTERPRISE MULTI-TENANT ARCHITECTURE PROPOSAL
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("4. Enterprise Multi-Tenant Architecture Proposal", h1_style))
    story.append(hr())

    # 4.1
    story.append(Paragraph("4.1 From Personal to Corporate: The Gap", h2_style))
    story.append(Paragraph(
        "OpenClaw's architecture provides powerful primitives (multi-agent routing, workspace isolation, session scoping, "
        "skill gating) that map surprisingly well to enterprise requirements. However, several fundamental gaps must be "
        "addressed:",
        body_style
    ))
    gaps = [
        "<b>Trust model inversion:</b> Personal = trust by default. Enterprise = zero trust by default",
        "<b>Authorization:</b> sessionKey is routing, not auth. Enterprise needs RBAC/ABAC per tool, per resource",
        "<b>Isolation:</b> Shared-process agents can reach each other's files. Enterprise needs hard boundaries",
        "<b>Auditability:</b> JSONL transcripts are per-agent files. Enterprise needs centralized, immutable audit logs",
        "<b>Scalability:</b> Single-process Gateway limits vertical scale. Enterprise needs horizontal scaling",
        "<b>Compliance:</b> No built-in data classification, retention policies, or regulatory controls",
    ]
    for g in gaps:
        story.append(Paragraph(f'• {g}', bullet_style))

    # 4.2
    story.append(Paragraph("4.2 Proposed Architecture Overview", h2_style))

    # Enterprise architecture diagram
    ent_diag = make_box_diagram(500, 280, [
        # Top - API Gateway
        (170, 240, 160, 30, "API Gateway / LB", DARK_GRAY),
        # Auth layer
        (170, 195, 160, 30, "IAM / Auth Service\n(OIDC + RBAC)", ACCENT_RED),
        # Tenant router
        (170, 150, 160, 30, "Tenant Router", ACCENT_ORANGE),
        # Tenant gateways
        (20, 85, 100, 45, "Tenant A\nGateway Pod\n(Isolated)", ACCENT_BLUE),
        (140, 85, 100, 45, "Tenant B\nGateway Pod\n(Isolated)", ACCENT_TEAL),
        (260, 85, 100, 45, "Tenant C\nGateway Pod\n(Isolated)", ACCENT_PURPLE),
        (380, 85, 100, 45, "Tenant N\nGateway Pod\n(Isolated)", ACCENT_GREEN),
        # Shared services
        (20, 15, 105, 45, "Shared Services\nModel Router\nSkill Registry", HexColor("#555555")),
        (145, 15, 105, 45, "Observability\nAudit Logs\nMetrics", HexColor("#555555")),
        (270, 15, 105, 45, "Data Layer\nPostgres\nObject Store", HexColor("#555555")),
        (395, 15, 85, 45, "Baioniq\nPlatform\nBridge", BAIONIQ_PURPLE),
    ], [
        (250, 240, 250, 225),
        (250, 195, 250, 180),
        (200, 150, 70, 130), (230, 150, 190, 130),
        (270, 150, 310, 130), (300, 150, 430, 130),
        (70, 85, 70, 60), (190, 85, 197, 60),
        (310, 85, 322, 60), (430, 85, 437, 60),
    ])
    story.append(ent_diag)
    story.append(Paragraph("Figure 4: Proposed Enterprise Multi-Tenant Architecture", caption_style))

    # 4.3
    story.append(Paragraph("4.3 Tenant Isolation Model", h2_style))
    story.append(Paragraph(
        "The proposed architecture uses <b>pod-per-tenant isolation</b> — each tenant gets a dedicated OpenClaw-derived "
        "Gateway instance running in its own Kubernetes pod with:",
        body_style
    ))
    isolation_items = [
        "<b>Namespace isolation:</b> Kubernetes namespace per tenant with network policies",
        "<b>Dedicated workspace:</b> Tenant workspace mounted as a persistent volume (not shared filesystem)",
        "<b>Sandboxed execution:</b> All tool execution runs in Docker-in-Docker (DinD) or gVisor containers",
        "<b>Credential isolation:</b> Vault-backed per-tenant secrets (model API keys, channel tokens)",
        "<b>Session store:</b> Per-tenant PostgreSQL schema (not JSONL files) for horizontal query capability",
        "<b>Resource quotas:</b> CPU/memory limits, token budgets, and rate limiting per tenant",
    ]
    for item in isolation_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    story.append(Paragraph(
        "This mirrors OpenClaw's multi-agent model but hardens it: where OpenClaw uses filesystem separation + "
        "convention, the enterprise version uses container boundaries + enforcement.",
        callout_style
    ))

    # 4.4
    story.append(Paragraph("4.4 Identity & Access Management", h2_style))
    story.append(Paragraph(
        "The enterprise IAM layer replaces OpenClaw's pairing-based device trust with corporate identity:",
        body_style
    ))

    iam_data = [
        ['Layer', 'OpenClaw (Personal)', 'Enterprise Proposal'],
        ['Authentication', 'Device pairing +\nchallenge-response', 'OIDC / SAML SSO +\nMFA enforcement'],
        ['Authorization', 'sessionKey routing\n(no per-user auth)', 'RBAC + ABAC per tool,\nresource, channel'],
        ['Identity', 'Device token\n(paired metadata)', 'Corporate identity +\nidentity federation'],
        ['Admin', 'CLI + config file', 'Admin portal + API +\naudit trail'],
        ['Multi-user', 'dmScope per-peer\n(session isolation)', 'Tenant admin + user\nroles + permissions'],
    ]
    iam_table = Table(iam_data, colWidths=[80, 150, 170])
    iam_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT_RED),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(iam_table)
    story.append(Paragraph("Table 3: IAM Comparison — Personal vs Enterprise", caption_style))

    # 4.5
    story.append(Paragraph("4.5 Shared Services Layer", h2_style))
    story.append(Paragraph(
        "While tenant Gateways are isolated, several services are shared across tenants for efficiency:",
        body_style
    ))

    shared_items = [
        "<b>Model Router:</b> Central LLM gateway (like LiteLLM or custom proxy) that handles model selection, "
        "failover, token accounting, and cost attribution per tenant. Maps to OpenClaw's model failover concept "
        "but adds per-tenant quotas and billing.",
        "<b>Skill Registry:</b> Centralized skill catalog (enterprise ClawHub) with approval workflows, version "
        "pinning, and security scanning. Tenants select from approved skills — no arbitrary code execution.",
        "<b>Channel Hub:</b> Shared channel infrastructure (Slack workspace bots, Teams apps, Telegram bots) "
        "with per-tenant message routing. Reduces channel credential sprawl.",
        "<b>Object Store:</b> S3-compatible storage for media, transcripts, and agent artifacts with per-tenant "
        "bucket prefixes and lifecycle policies.",
    ]
    for item in shared_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    # 4.6
    story.append(Paragraph("4.6 Observability & Compliance", h2_style))
    story.append(Paragraph(
        "Enterprise deployments require comprehensive observability beyond OpenClaw's current logging:",
        body_style
    ))
    obs_items = [
        "<b>Audit logs:</b> Every tool invocation, model call, and channel message logged immutably with tenant/user attribution",
        "<b>Metrics:</b> Token usage, latency percentiles, error rates, session counts — per tenant, per agent, per model",
        "<b>Traces:</b> OpenTelemetry distributed tracing from message receipt through agent execution to response delivery",
        "<b>Data classification:</b> PII detection and redaction in logs/transcripts with configurable retention policies",
        "<b>Compliance exports:</b> SOC 2 Type II evidence collection, GDPR data subject access requests",
    ]
    for item in obs_items:
        story.append(Paragraph(f'• {item}', bullet_style))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 5. BAIONIQ INTEGRATION STRATEGY
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("5. Baioniq Integration Strategy", h1_style))
    story.append(hr())

    # 5.1
    story.append(Paragraph("5.1 Baioniq Platform Overview", h2_style))
    story.append(Paragraph(
        "Baioniq is Quantiphi's enterprise GenAI platform that enables organizations to \"own their GenAI stack.\" "
        "It provides a comprehensive framework for building, deploying, and managing generative AI applications at "
        "enterprise scale. Key Baioniq capabilities include:",
        body_style
    ))
    baioniq_caps = [
        "<b>GenAI Application Framework:</b> Pre-built templates and accelerators for common enterprise GenAI use cases "
        "(document intelligence, conversational AI, code generation, content creation)",
        "<b>Model Management:</b> Multi-model orchestration with support for Google Cloud (Vertex AI), AWS (Bedrock), "
        "Azure OpenAI, and open-source models — model evaluation, selection, and lifecycle management",
        "<b>RAG Pipeline:</b> Enterprise retrieval-augmented generation with vector store integration, document processing, "
        "chunking strategies, and knowledge base management",
        "<b>Guardrails & Governance:</b> Content safety, hallucination detection, prompt injection defense, and "
        "responsible AI policy enforcement at the platform level",
        "<b>Enterprise Integration:</b> Connectors for enterprise data sources (Salesforce, ServiceNow, SAP, "
        "Confluence, SharePoint) with secure data pipelines",
        "<b>Deployment & Operations:</b> Kubernetes-native deployment, auto-scaling, A/B testing of prompts/models, "
        "and operational dashboards for GenAI workloads",
    ]
    for cap in baioniq_caps:
        story.append(Paragraph(f'• {cap}', bullet_style))

    # 5.2
    story.append(Paragraph("5.2 Synergy Map: OpenClaw ↔ Baioniq", h2_style))
    story.append(Paragraph(
        "The integration creates a platform greater than the sum of its parts. OpenClaw-inspired architecture provides "
        "the agentic execution layer that Baioniq's GenAI stack currently lacks, while Baioniq provides the enterprise "
        "foundation that OpenClaw was explicitly not designed for:",
        body_style
    ))

    synergy_data = [
        ['Capability', 'OpenClaw Provides', 'Baioniq Provides', 'Combined Value'],
        ['Agent\nExecution', 'Tool use, exec,\nbrowser, canvas', 'Model routing,\nguardrails', 'Governed\nagentic AI'],
        ['Channel\nDelivery', '25+ messaging\nsurfaces', 'Enterprise\nconnectors', 'Omnichannel\nagent UX'],
        ['Knowledge', 'Workspace files,\nmemory, skills', 'RAG pipeline,\nvector stores', 'Context-rich\nagent memory'],
        ['Security', 'Sandboxing,\ntool policy', 'Guardrails,\ngovernance', 'Defense-in-\ndepth'],
        ['Ops', 'Cron, heartbeats,\nwebhooks', 'K8s deploy,\nmonitoring', 'Enterprise\nautomation'],
        ['Persona', 'SOUL.md,\nAGENTS.md', 'Prompt\ntemplates', 'Brand-aligned\nagent personas'],
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
    story.append(Paragraph("Table 4: OpenClaw ↔ Baioniq Synergy Matrix", caption_style))

    # 5.3
    story.append(Paragraph("5.3 Proposed Integration Architecture", h2_style))

    # Integration diagram
    int_diag = make_box_diagram(500, 260, [
        # Baioniq Platform
        (20, 200, 460, 40, "Baioniq Platform — GenAI Stack (Model Mgmt | RAG | Guardrails | Governance)", BAIONIQ_PURPLE),
        # Integration Layer
        (80, 140, 340, 35, "Integration Layer — Baioniq Agent Bridge API", ACCENT_ORANGE),
        # Agent Orchestrator
        (130, 85, 240, 35, "Multi-Tenant Agent Orchestrator\n(OpenClaw-Derived Engine)", ACCENT_BLUE),
        # Bottom components
        (20, 15, 100, 50, "Tenant\nWorkspaces\n(K8s Pods)", ACCENT_TEAL),
        (140, 15, 100, 50, "Skill\nRegistry\n(Approved)", ACCENT_GREEN),
        (260, 15, 100, 50, "Channel\nHub\n(25+ Surfaces)", ACCENT_PURPLE),
        (380, 15, 100, 50, "Audit &\nCompliance\nEngine", ACCENT_RED),
    ], [
        (250, 200, 250, 175),
        (250, 140, 250, 120),
        (200, 85, 70, 65), (230, 85, 190, 65),
        (310, 85, 310, 65), (340, 85, 430, 65),
    ])
    story.append(int_diag)
    story.append(Paragraph("Figure 5: Baioniq + OpenClaw-Derived Integration Architecture", caption_style))

    story.append(Paragraph(
        "<b>Integration touchpoints:</b>",
        body_style
    ))
    integration_items = [
        "<b>Model Router Bridge:</b> Tenant Gateway pods route LLM calls through Baioniq's model management layer "
        "instead of directly calling providers. This gives Baioniq control over model selection, cost attribution, "
        "guardrails enforcement, and A/B testing — while the agent runtime handles tool execution and conversation flow.",
        "<b>RAG Skill:</b> A custom skill that bridges OpenClaw's tool interface to Baioniq's RAG pipeline. When the "
        "agent needs enterprise knowledge (policies, documentation, CRM data), it invokes the RAG skill which calls "
        "Baioniq's retrieval API with the agent's query context.",
        "<b>Guardrails Middleware:</b> Baioniq's content safety and prompt injection defenses wrap the agent's input "
        "and output. Every user message is filtered before reaching the agent; every agent response is checked before "
        "delivery. This replaces OpenClaw's trust-by-default model with defense-in-depth.",
        "<b>Workspace Templates:</b> Baioniq's deployment system manages tenant workspace provisioning — pre-configured "
        "SOUL.md (brand voice), AGENTS.md (operating procedures), and approved skill sets per tenant/department.",
        "<b>Telemetry Pipeline:</b> Agent execution telemetry (tool calls, model usage, latency, errors) flows into "
        "Baioniq's operational dashboard alongside RAG metrics and model performance data.",
    ]
    for item in integration_items:
        story.append(Paragraph(f'• {item}', bullet_style))

    # 5.4
    story.append(Paragraph("5.4 Differentiation & GTM Positioning", h2_style))
    story.append(Paragraph(
        "The combined platform creates a unique market position:",
        body_style
    ))
    story.append(Paragraph(
        '<b>"Baioniq Agents" — Enterprise Agentic AI, Delivered Where Your Teams Already Work"</b>',
        ParagraphStyle('Tagline', parent=body_style, fontSize=12, textColor=BAIONIQ_PURPLE, alignment=TA_CENTER, spaceBefore=8, spaceAfter=12)
    ))

    diff_data = [
        ['Competitor', 'Limitation', 'Baioniq Agents Advantage'],
        ['Microsoft\nCopilot', 'Locked to M365\necosystem', 'Any channel (WhatsApp, Slack,\nTeams, custom) + any model'],
        ['Google\nAgentspace', 'Google Cloud\nonly', 'Multi-cloud + self-hosted\noption for regulated industries'],
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

    # ══════════════════════════════════════════════════════════════
    # 6. IMPLEMENTATION ROADMAP
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("6. Implementation Roadmap", h1_style))
    story.append(hr())

    roadmap_data = [
        ['Phase', 'Timeline', 'Deliverables', 'Dependencies'],
        ['Phase 1:\nFoundation', 'Weeks 1-6', '• Multi-tenant Gateway fork\n• Pod-per-tenant K8s manifests\n• IAM integration (OIDC)\n• PostgreSQL session store', 'K8s cluster,\nIdentity provider,\nPostgres instance'],
        ['Phase 2:\nBaioniq\nBridge', 'Weeks 7-12', '• Model Router Bridge API\n• RAG Skill implementation\n• Guardrails middleware\n• Workspace template system', 'Baioniq API access,\nRAG pipeline,\nGuardrails service'],
        ['Phase 3:\nChannels\n& Skills', 'Weeks 13-18', '• Enterprise Channel Hub\n• Skill Registry + approval\n• Admin portal MVP\n• Per-tenant metrics', 'Slack/Teams apps,\nUI framework,\nPrometheus/Grafana'],
        ['Phase 4:\nHarden\n& Ship', 'Weeks 19-24', '• Security audit + pen test\n• SOC 2 evidence pack\n• Performance benchmarks\n• Customer pilot (2 tenants)', 'Security team,\nCompliance team,\nPilot customers'],
    ]
    roadmap_table = Table(roadmap_data, colWidths=[65, 65, 195, 115])
    roadmap_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(roadmap_table)
    story.append(Paragraph("Table 6: Implementation Roadmap — 24-Week Plan", caption_style))

    story.append(Paragraph("<b>Estimated team:</b> 2 platform engineers, 1 Baioniq specialist, 1 security engineer, "
                           "0.5 PM. Total: ~4.5 FTE for 6 months.", body_style))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # 7. RISK ANALYSIS
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("7. Risk Analysis & Mitigations", h1_style))
    story.append(hr())

    risk_data = [
        ['Risk', 'Severity', 'Likelihood', 'Mitigation'],
        ['OpenClaw license\nchange (MIT → \nrestrictive)', 'High', 'Low', 'Fork at current version;\nbuild proprietary\nextensions on top'],
        ['Pod-per-tenant\ncost at scale\n(100+ tenants)', 'Medium', 'Medium', 'Resource right-sizing;\nshared-pool mode for\nsmall tenants'],
        ['Channel API\nbreaking changes\n(WhatsApp/Baileys)', 'Medium', 'Medium', 'Abstract channel layer;\nfallback to official\nAPIs (WABA)'],
        ['Model vendor\nlock-in through\nBaioniq bridge', 'Medium', 'Low', 'OpenClaw\'s multi-model\nsupport as escape\nhatch'],
        ['Security\nvulnerability in\nagent execution', 'Critical', 'Medium', 'gVisor sandboxing;\nnetwork policies;\ntool allowlists'],
        ['Adoption friction\n(Baioniq users\ndon\'t want agents)', 'High', 'Medium', 'Start with simple\nuse cases (Q&A bots);\ngradual tool enablement'],
    ]
    risk_table = Table(risk_data, colWidths=[100, 60, 65, 175])
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

    # ══════════════════════════════════════════════════════════════
    # 8. CONCLUSION
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph("8. Conclusion & Recommendations", h1_style))
    story.append(hr())
    story.append(Paragraph(
        "OpenClaw represents a rare architectural achievement: a genuinely useful AI agent framework built by solving "
        "the right problems in the right order (channels first, tools second, scale later). Its rapid adoption validates "
        "the hypothesis that people want AI assistants delivered through their existing communication channels — not "
        "through yet another web application.",
        body_style
    ))
    story.append(Paragraph(
        "The proposed enterprise multi-tenant architecture preserves OpenClaw's core strengths (agent workspace isolation, "
        "skill composability, channel universality) while adding the enterprise foundations it explicitly chose not to build "
        "(multi-tenant authorization, hard isolation, auditability, compliance).",
        body_style
    ))
    story.append(Paragraph(
        "Integrating this with Baioniq creates a platform that neither could achieve alone:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Baioniq without agents</b> = powerful GenAI stack, but outputs trapped in dashboards and APIs<br/>"
        "• <b>Agents without Baioniq</b> = powerful execution, but no governance, RAG, or enterprise integration<br/>"
        "• <b>Baioniq + Agents</b> = governed, enterprise-grade agentic AI delivered through 25+ channels with "
        "full tool execution, RAG-powered knowledge, and brand-aligned personas",
        callout_style
    ))

    story.append(Paragraph("<b>Recommendations:</b>", h3_style))
    recs = [
        "<b>1. Prototype immediately:</b> Build a single-tenant Baioniq Agent PoC using OpenClaw's open-source "
        "codebase, connected to Baioniq's model router and RAG pipeline. Target: working demo in 3 weeks.",
        "<b>2. Engage OpenClaw community:</b> Consider contributing enterprise-relevant features upstream "
        "(PostgreSQL session store, OpenTelemetry tracing) to build goodwill and reduce fork maintenance.",
        "<b>3. Start with internal deployment:</b> Deploy Baioniq Agents for Quantiphi's own teams first — "
        "engineering, sales, delivery. Dogfooding builds conviction and surfaces real enterprise requirements.",
        "<b>4. Position for GCP Next / re:Invent:</b> A \"Baioniq Agents\" demo showing enterprise AI agents "
        "responding across Slack, Teams, and WhatsApp with Vertex AI backing would be a compelling showcase.",
        "<b>5. File provisional patent:</b> The specific architecture of Baioniq's guardrails wrapping an "
        "OpenClaw-derived agent execution engine with multi-tenant workspace isolation is novel and defensible.",
    ]
    for r in recs:
        story.append(Paragraph(r, bullet_style))

    story.append(Spacer(1, 0.5*inch))
    story.append(hr())
    story.append(Paragraph(
        "— End of Report —",
        ParagraphStyle('EndMark', parent=body_style, alignment=TA_CENTER, fontSize=10, textColor=DARK_GRAY)
    ))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}<br/>"
        "Sources: OpenClaw Documentation (docs.openclaw.ai), GitHub (github.com/openclaw/openclaw), "
        "Quantiphi Baioniq (quantiphi.com/applications/baioniq)",
        ParagraphStyle('Footer', parent=body_style, alignment=TA_CENTER, fontSize=8, textColor=MED_GRAY)
    ))

    doc.build(story)
    print(f"✅ Report generated: {OUTPUT_PATH}")
    print(f"   Pages: ~15")
    print(f"   Size: {os.path.getsize(OUTPUT_PATH) / 1024:.0f} KB")

if __name__ == "__main__":
    build_report()
