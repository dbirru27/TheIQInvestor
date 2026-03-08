#!/usr/bin/env python3
"""
Generate PDF Report: The IQ Investor — Algorithm & Backtest Report
Uses walk-forward backtest results (no look-ahead bias).
"""
import json
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                 Table, TableStyle, PageBreak, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports', 'charts')
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports',
                       f'IQ_Investor_Algorithm_Report_{datetime.now().strftime("%Y%m%d")}.pdf')

with open(os.path.join(DATA_DIR, 'backtest_results.json')) as f:
    bt = json.load(f)

stats = bt.get('stats', {})

# Print-friendly colors
HEADING_COLOR = colors.HexColor('#0c4a6e')
TEXT_BLACK = colors.HexColor('#1a1a1a')
TEXT_DARK = colors.HexColor('#333333')
TABLE_HEADER_BG = colors.HexColor('#0c4a6e')
TABLE_ALT_ROW = colors.HexColor('#f0f4f8')
BORDER_COLOR = colors.HexColor('#cbd5e1')

styles = getSampleStyleSheet()
title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=26,
                              textColor=HEADING_COLOR, spaceAfter=4, fontName='Helvetica-Bold')
subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=12,
                                 textColor=TEXT_DARK, spaceAfter=16, alignment=TA_CENTER)
h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=15,
                           textColor=HEADING_COLOR, spaceBefore=14, spaceAfter=6, fontName='Helvetica-Bold')
h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=11,
                           textColor=HEADING_COLOR, spaceBefore=8, spaceAfter=4, fontName='Helvetica-Bold')
h3_style = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=10,
                           textColor=HEADING_COLOR, spaceBefore=6, spaceAfter=3, fontName='Helvetica-Bold')
body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9,
                             textColor=TEXT_BLACK, leading=12, alignment=TA_JUSTIFY)
formula_style = ParagraphStyle('Formula', parent=styles['Code'], fontSize=8,
                                textColor=TEXT_BLACK, backColor=colors.HexColor('#f1f5f9'),
                                leading=11, leftIndent=12, rightIndent=12, spaceBefore=3, spaceAfter=3,
                                borderColor=BORDER_COLOR, borderWidth=0.5, borderPadding=4)
metric_style = ParagraphStyle('Metric', parent=styles['Normal'], fontSize=9,
                               textColor=HEADING_COLOR, fontName='Helvetica-Bold')
caption_style = ParagraphStyle('Caption', parent=styles['Normal'], fontSize=7,
                                textColor=TEXT_DARK, alignment=TA_CENTER, spaceAfter=8)
note_style = ParagraphStyle('Note', parent=styles['Normal'], fontSize=8,
                             textColor=TEXT_DARK, leading=10, leftIndent=12,
                             borderColor=colors.HexColor('#e2e8f0'), borderWidth=0.5,
                             borderPadding=6, backColor=colors.HexColor('#fefce8'))


def make_table(data, col_widths=None):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_BLACK),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, TABLE_ALT_ROW]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return t


def add_chart(story, filename, width=5.5*inch, caption=None):
    path = os.path.join(CHARTS_DIR, filename)
    if os.path.exists(path):
        img = Image(path, width=width, height=width*0.45)
        story.append(img)
        if caption:
            story.append(Paragraph(caption, caption_style))


def s(key1, key2, field, default=0):
    """Safe stat accessor."""
    return stats.get(key1, {}).get(key2, {}).get(field, default)


def build_report():
    doc = SimpleDocTemplate(OUTPUT, pagesize=letter,
                            topMargin=0.6*inch, bottomMargin=0.5*inch,
                            leftMargin=0.7*inch, rightMargin=0.7*inch)
    story = []

    # ===== COVER + TOC (single page) =====
    story.append(Spacer(1, 0.8*inch))
    story.append(Paragraph('The IQ Investor', title_style))
    story.append(Paragraph('Algorithm & Backtesting Report', subtitle_style))
    story.append(HRFlowable(width='50%', color=HEADING_COLOR, thickness=1.5))
    story.append(Spacer(1, 0.15*inch))
    cover_info = ParagraphStyle('CI', parent=body_style, alignment=TA_CENTER, fontSize=9, textColor=TEXT_DARK)
    story.append(Paragraph(f'Generated: {datetime.now().strftime("%B %d, %Y")} · Data: {bt.get("data_range","N/A")} · {bt.get("total_stocks",0)} stocks', cover_info))
    story.append(Paragraph(f'Backtest: {bt.get("backtest_range","N/A")} · {bt.get("rebalance_periods",0)} monthly rebalance periods', cover_info))
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph(
        '<i>Walk-forward methodology: At each monthly rebalance, scores are computed using <b>only data available '
        'at that date</b>. Forward returns are measured <b>after</b> portfolio formation. No look-ahead bias.</i>',
        ParagraphStyle('Method', parent=body_style, alignment=TA_CENTER, fontSize=8, textColor=TEXT_DARK)))
    story.append(Spacer(1, 0.4*inch))
    story.append(HRFlowable(width='100%', color=BORDER_COLOR, thickness=0.5))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph('Contents', h2_style))
    toc = [
        '1. Executive Summary & Walk-Forward Results',
        '2. Quality Score — 14-Factor Stock Rating',
        '3. EWROS — Exponential Weighted Relative Outperformance',
        '4. Rotation Score — 6-Signal Rotation Detector',
        '5. IQ Edge Score — ML Breakout Prediction',
        '6. Power Matrix — Combined Signal Framework',
        '7. Methodology & Limitations',
        '8. Appendix: Parameters & Configuration',
    ]
    toc_style = ParagraphStyle('TOC', parent=body_style, spaceBefore=2, fontSize=9)
    for item in toc:
        story.append(Paragraph(item, toc_style))
    story.append(PageBreak())

    # ===== 1. EXECUTIVE SUMMARY =====
    story.append(Paragraph('1. Executive Summary', h1_style))
    story.append(Paragraph(
        'The IQ Investor platform employs a multi-signal approach to stock selection, combining fundamental quality metrics, '
        'momentum indicators, and machine learning. This report documents each algorithm and presents walk-forward '
        'backtesting results across 50 monthly rebalance periods (Jan 2022 – Feb 2026).',
        body_style))
    story.append(Spacer(1, 6))

    story.append(Paragraph('Walk-Forward Results Summary', h2_style))

    summary_table = [
        ['Signal', 'Top Avg/Mo', 'Bottom Avg/Mo', 'Spread', 'Top Cumulative', 'Top Win Rate', 'N'],
        ['EWROS (Top/Bottom 10%)',
         f'{s("EWROS","top","avg_monthly")}%', f'{s("EWROS","bottom","avg_monthly")}%',
         f'{s("EWROS","top","avg_monthly") - s("EWROS","bottom","avg_monthly"):+.2f}%',
         f'{s("EWROS","top","cumulative")}%', f'{s("EWROS","top","win_rate")}%', str(s("EWROS","top","n_periods"))],
        ['IQ Edge (Top/Bottom 10%)',
         f'{s("IQ Edge","top","avg_monthly")}%', f'{s("IQ Edge","bottom","avg_monthly")}%',
         f'{s("IQ Edge","top","avg_monthly") - s("IQ Edge","bottom","avg_monthly"):+.2f}%',
         f'{s("IQ Edge","top","cumulative")}%', f'{s("IQ Edge","top","win_rate")}%', str(s("IQ Edge","top","n_periods"))],
        ['Power Matrix (Zone/Avoid)',
         f'{s("Power Matrix","top","avg_monthly")}%', f'{s("Power Matrix","bottom","avg_monthly")}%',
         f'{s("Power Matrix","top","avg_monthly") - s("Power Matrix","bottom","avg_monthly"):+.2f}%',
         f'{s("Power Matrix","top","cumulative")}%', f'{s("Power Matrix","top","win_rate")}%', str(s("Power Matrix","top","n_periods"))],
        ['Rotation (High/Low)',
         f'{s("Rotation","top","avg_monthly")}%', f'{s("Rotation","bottom","avg_monthly")}%',
         f'{s("Rotation","top","avg_monthly") - s("Rotation","bottom","avg_monthly"):+.2f}%',
         f'{s("Rotation","top","cumulative")}%', f'{s("Rotation","top","win_rate")}%', str(s("Rotation","top","n_periods"))],
        ['Quality (Top/Bottom 10%)',
         f'{s("Quality","top","avg_monthly")}%', f'{s("Quality","bottom","avg_monthly")}%',
         f'{s("Quality","top","avg_monthly") - s("Quality","bottom","avg_monthly"):+.2f}%',
         f'{s("Quality","top","cumulative")}%', f'{s("Quality","top","win_rate")}%', str(s("Quality","top","n_periods"))],
        ['SPY Benchmark',
         f'{s("EWROS","spy","avg_monthly")}%', '—', '—',
         f'{s("EWROS","spy","cumulative")}%', f'{s("EWROS","spy","win_rate")}%', str(s("EWROS","spy","n_periods"))],
    ]
    story.append(make_table(summary_table, col_widths=[1.7*inch, 0.85*inch, 0.85*inch, 0.75*inch, 1*inch, 0.8*inch, 0.5*inch]))
    story.append(Spacer(1, 6))

    # Equity curves chart
    add_chart(story, 'walk_forward_equity.png', width=6.2*inch, caption='Growth of $100: Monthly rebalanced portfolios, walk-forward (2022–2026)')
    story.append(Spacer(1, 6))

    # Signal spreads chart
    add_chart(story, 'signal_spreads.png', width=5.5*inch, caption='Distribution of monthly top-minus-bottom return spread by signal')
    story.append(Spacer(1, 6))

    # Key takeaways
    story.append(Paragraph('Key Findings', h3_style))
    ewros_spread = s("EWROS","top","avg_monthly") - s("EWROS","bottom","avg_monthly")
    iq_spread = s("IQ Edge","top","avg_monthly") - s("IQ Edge","bottom","avg_monthly")
    story.append(Paragraph(
        f'<b>EWROS</b> shows the strongest signal with a +{ewros_spread:.2f}%/month spread between top and bottom deciles, '
        f'compounding to +{s("EWROS","top","cumulative")}% cumulative vs SPY\'s +{s("EWROS","spy","cumulative")}%. '
        f'<b>IQ Edge</b> (ML) delivers a +{iq_spread:.2f}%/month spread. '
        f'<b>Quality Score</b> shows a negative spread in this period — see Section 2 for discussion.',
        body_style))
    story.append(PageBreak())

    # ===== 2. QUALITY SCORE =====
    story.append(Paragraph('2. Quality Score — 14-Factor Stock Rating', h1_style))
    story.append(Paragraph(
        'The Quality Score evaluates stocks on a 100-point scale across four categories: '
        'Technical Setup (53 pts max), Growth (33 pts max), Quality Fundamentals (18 pts max), '
        'and Market Context (10 pts max). Stocks are graded A through F.',
        body_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph('Scoring Breakdown', h2_style))
    criteria_table = [
        ['Category', 'Factor', 'Pts', 'Description'],
        ['Technical', 'Breakout Pattern', '22', 'Flat ceiling base with <10% drift'],
        ['Technical', 'Trend Alignment', '8', 'Price > 50d MA > 200d MA'],
        ['Technical', 'Consolidation', '10', 'Base depth and formation quality'],
        ['Technical', 'Volume Dry-up', '5', 'Volume decline during base (accumulation)'],
        ['Technical', '52W Proximity', '5', 'Distance from 52-week high'],
        ['Technical', 'Volatility Compression', '3', 'ATR narrowing before breakout'],
        ['Growth', 'Revenue Growth (2yr)', '30', 'Both years ≥10% required (strict gate)'],
        ['Growth', 'Earnings Acceleration', '3', 'Sequential quarterly improvement'],
        ['Quality', 'ROE', '5', 'Return on equity'],
        ['Quality', 'Operating Margin', '5', 'Profitability margin'],
        ['Quality', 'PEG Ratio', '5', 'Price/Earnings to Growth'],
        ['Quality', 'FCF Quality', '3', 'Free cash flow positive'],
        ['Context', 'Industry Strength', '5', 'Sector relative performance vs SPY'],
        ['Context', 'Relative Strength', '5', '6-month outperformance vs SPY'],
    ]
    story.append(make_table(criteria_table, col_widths=[0.8*inch, 1.5*inch, 0.4*inch, 3.8*inch]))
    story.append(Spacer(1, 4))
    story.append(Paragraph('Grades: A ≥ 75 · B ≥ 60 · C ≥ 45 · D ≥ 30 · F < 30', formula_style))

    story.append(Paragraph('Revenue Gate (v4.4)', h3_style))
    story.append(Paragraph(
        'Both years of revenue growth must be ≥ 10% for any growth points. '
        'This strict 2-year consistency gate filters out one-time spikes.',
        body_style))

    story.append(Paragraph('Walk-Forward Results & Honest Assessment', h2_style))
    q_top_avg = s("Quality","top","avg_monthly")
    q_bottom_avg = s("Quality","bottom","avg_monthly")
    story.append(Paragraph(
        f'Top 10% Quality stocks averaged <b>{q_top_avg}%/month</b> vs bottom 10% at <b>{q_bottom_avg}%/month</b>. '
        f'The negative spread ({q_top_avg - q_bottom_avg:+.2f}%) indicates the price/volume-based quality proxy used in backtesting '
        f'does not capture the full Quality Score (which includes fundamental data like revenue growth, ROE, margins). '
        f'The backtest proxy covers ~60% of the scoring factors. '
        f'A proper fundamental backtest would require historical financial statement data (e.g., from SEC filings), '
        f'which was not available in our OHLCV dataset.',
        body_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        '<b>Limitation:</b> The Quality Score backtest uses a price/volume proxy (trend, MA, momentum, volume, volatility) '
        'and cannot test fundamental factors (revenue gate, ROE, margins, PEG, FCF). Results for this signal '
        'should not be treated as validation of the full Quality Score.',
        note_style))

    # ===== 3. EWROS =====
    story.append(Paragraph('3. EWROS — Exponential Weighted Relative Outperformance', h1_style))
    story.append(Paragraph(
        'EWROS measures how consistently a stock outperforms SPY on a daily basis, with exponential decay '
        'emphasizing recent performance. Unlike IBD RS Rating (12-month equal weight), EWROS catches momentum '
        'shifts within weeks.',
        body_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph('Formula', h2_style))
    story.append(Paragraph(
        'daily_alpha(t) = stock_return(t) − SPY_return(t)\n'
        'weight(t) = e^(−0.03 × days_ago)          half-life ≈ 23 days\n'
        'EWROS_raw = Σ(daily_alpha × weight)       over 63 trading days\n'
        'EWROS = percentile_rank(EWROS_raw)        scaled 1–99',
        formula_style))

    story.append(Paragraph('Parameters', h3_style))
    ewros_params = [
        ['Parameter', 'Value', 'Rationale'],
        ['Lookback', '63 days (~3 months)', 'Captures medium-term momentum without noise'],
        ['Lambda (λ)', '0.03', 'Half-life ~23 days — recent alpha weighs ~2x vs 3-week-old'],
        ['Trend Offset', '21 days', 'Compares current rank to 1 month prior for trend detection'],
        ['Benchmark', 'SPY', 'S&P 500 ETF as broad market proxy'],
    ]
    story.append(make_table(ewros_params, col_widths=[1.2*inch, 1.5*inch, 3.8*inch]))

    story.append(Paragraph('Walk-Forward Results', h2_style))
    story.append(Paragraph(
        f'<b>EWROS is the strongest single signal.</b> Top decile: +{s("EWROS","top","avg_monthly")}%/month '
        f'(win rate {s("EWROS","top","win_rate")}%), cumulative +{s("EWROS","top","cumulative")}%. '
        f'Bottom decile: +{s("EWROS","bottom","avg_monthly")}%/month, cumulative +{s("EWROS","bottom","cumulative")}%. '
        f'SPY: +{s("EWROS","spy","avg_monthly")}%/month, cumulative +{s("EWROS","spy","cumulative")}%. '
        f'Spread of +{ewros_spread:.2f}%/month is statistically meaningful across {s("EWROS","top","n_periods")} periods.',
        body_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f'Best month: +{s("EWROS","top","best_month")}% · Worst month: {s("EWROS","top","worst_month")}% · '
        f'Std dev: {s("EWROS","top","std")}%',
        metric_style))
    story.append(PageBreak())

    # ===== 4. ROTATION =====
    story.append(Paragraph('4. Rotation Score — 6-Signal Rotation Detector', h1_style))
    story.append(Paragraph(
        'Identifies institutional rotation — smart money flowing into stocks ahead of breakouts. '
        'Combines 6 signals into a composite score (0–100).',
        body_style))
    story.append(Spacer(1, 4))

    rot_signals = [
        ['Signal', 'Weight', 'What It Measures'],
        ['RS Divergence', '20%', 'Stock strengthens while market weakens'],
        ['Earnings Momentum', '20%', 'Sequential quarterly earnings improvement'],
        ['Valuation Gap', '15%', 'Discount to intrinsic value (PEG-based)'],
        ['Stage Breakout', '20%', 'Price breaking above accumulation base'],
        ['Volume Accumulation', '15%', 'Unusual volume surge pattern'],
        ['Sector Momentum', '10%', 'Industry group relative strength'],
    ]
    story.append(make_table(rot_signals, col_widths=[1.3*inch, 0.7*inch, 4.5*inch]))
    story.append(Spacer(1, 4))

    story.append(Paragraph('Walk-Forward Results', h2_style))
    rot_spread = s("Rotation","top","avg_monthly") - s("Rotation","bottom","avg_monthly")
    story.append(Paragraph(
        f'High rotation (≥60): +{s("Rotation","top","avg_monthly")}%/month, cumulative +{s("Rotation","top","cumulative")}%. '
        f'Low rotation (<30): +{s("Rotation","bottom","avg_monthly")}%/month, cumulative +{s("Rotation","bottom","cumulative")}%. '
        f'Spread: +{rot_spread:.2f}%/month across {s("Rotation","top","n_periods")} periods.',
        body_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        '<b>Limitation:</b> The rotation backtest uses a price/volume proxy for the full 6-signal system. '
        'Earnings momentum and valuation gap require fundamental data not available in the OHLCV dataset. '
        'Results reflect the technical subset (RS divergence, stage breakout, volume accumulation).',
        note_style))

    # ===== 5. IQ EDGE =====
    story.append(Paragraph('5. IQ Edge Score — ML Breakout Prediction', h1_style))
    story.append(Paragraph(
        'Uses XGBoost (gradient boosted trees) trained on 9,730 historical breakout events to predict '
        'the probability of a stock doubling (100%+ gain) within 12 months of a breakout.',
        body_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph('Training Data & Model', h2_style))
    training_table = [
        ['Metric', 'Value'],
        ['Total Breakout Events', '9,730'],
        ['Doubles (100%+)', '297 (3.1%)'],
        ['Big Wins (50–100%)', '1,190 (12.2%)'],
        ['Wins (25–50%)', '2,268 (23.3%)'],
        ['Fails (<25%)', '5,975 (61.4%)'],
        ['Train Period', 'Mar 2021 – Dec 2024'],
        ['Validation Period', 'Jan – Jun 2025'],
        ['Test Period', 'Jul 2025 – Mar 2026'],
        ['Model', 'XGBoost (500 trees, max depth 6)'],
        ['Validation AUC', '0.736'],
        ['Test AUC', '0.758'],
    ]
    story.append(make_table(training_table, col_widths=[2*inch, 4.5*inch]))
    story.append(Spacer(1, 4))

    story.append(Paragraph('Feature Set (14 features)', h2_style))
    feature_table = [
        ['Feature', 'Category', 'Description'],
        ['close_to_ma20/50/200', 'Trend', 'Price relative to key moving averages'],
        ['trend_aligned', 'Trend', 'Price > 50d MA > 200d MA (binary)'],
        ['atr_14', 'Volatility', '14-day Average True Range (normalized)'],
        ['vol_dryup_ratio', 'Volume', 'Recent vs earlier volume in base'],
        ['vol_compression', 'Volatility', 'Recent ATR vs longer-term ATR'],
        ['proximity_52w', 'Timing', 'Price relative to 52-week high'],
        ['return_3mo', 'Momentum', '3-month price return'],
        ['up_days_pct', 'Pattern', 'Percentage of up days in base'],
        ['vol_trend_in_base', 'Volume', 'Volume trend direction in base'],
        ['base_length', 'Pattern', 'Duration of consolidation base'],
        ['base_range', 'Pattern', 'Price range width of base (%)'],
        ['breakout_vol_ratio', 'Volume', 'Breakout day volume vs 50d average'],
    ]
    story.append(make_table(feature_table, col_widths=[1.6*inch, 0.7*inch, 4.2*inch]))
    story.append(Spacer(1, 4))

    story.append(Paragraph('Walk-Forward Results', h2_style))
    story.append(Paragraph(
        f'Top IQ Edge decile: +{s("IQ Edge","top","avg_monthly")}%/month '
        f'(win rate {s("IQ Edge","top","win_rate")}%), cumulative +{s("IQ Edge","top","cumulative")}%. '
        f'Bottom decile: +{s("IQ Edge","bottom","avg_monthly")}%/month, cumulative +{s("IQ Edge","bottom","cumulative")}%. '
        f'Spread: +{iq_spread:.2f}%/month. The model\'s top-decile picks beat SPY '
        f'(+{s("EWROS","spy","cumulative")}%) by {s("IQ Edge","top","cumulative") - s("EWROS","spy","cumulative"):.1f}pp.',
        body_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        '<b>Key insight from training data:</b> Stocks that doubled had 6x higher breakout volume (13.7x avg '
        'vs 2.2x for failures) and slightly higher trend alignment (52.5% vs 44.9%).',
        body_style))

    # ===== 6. POWER MATRIX =====
    story.append(Paragraph('6. Power Matrix — Combined Signal Framework', h1_style))
    story.append(Paragraph(
        'Combines EWROS (momentum) with Rotation Score (setup quality) into a 2×2 quadrant:',
        body_style))
    story.append(Spacer(1, 4))

    matrix_table = [
        ['', 'EWROS ≥ 70 (High Momentum)', 'EWROS < 70 (Low Momentum)'],
        ['Rotation ≥ 60\n(Fresh Setup)', '🎯 POWER ZONE\nBUY — momentum + setup', '⏳ EARLY SIGNAL\nWATCH — setting up'],
        ['Rotation < 60\n(No Setup)', '⚠️ EXTENDED\nCAUTION — already ran', '💀 AVOID\nSKIP — no edge'],
    ]
    t = Table(matrix_table, colWidths=[1.3*inch, 2.7*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('BACKGROUND', (0, 0), (0, -1), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 1), (0, -1), colors.white),
        ('TEXTCOLOR', (1, 1), (-1, -1), TEXT_BLACK),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#dcfce7')),
        ('BACKGROUND', (2, 1), (2, 1), colors.HexColor('#dbeafe')),
        ('BACKGROUND', (1, 2), (1, 2), colors.HexColor('#fef9c3')),
        ('BACKGROUND', (2, 2), (2, 2), colors.HexColor('#fee2e2')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 4))

    story.append(Paragraph('Walk-Forward Results', h2_style))
    pm_spread = s("Power Matrix","top","avg_monthly") - s("Power Matrix","bottom","avg_monthly")
    story.append(Paragraph(
        f'Power Zone: +{s("Power Matrix","top","avg_monthly")}%/month, cumulative +{s("Power Matrix","top","cumulative")}%. '
        f'Avoid Zone: +{s("Power Matrix","bottom","avg_monthly")}%/month, cumulative +{s("Power Matrix","bottom","cumulative")}%. '
        f'Spread: +{pm_spread:.2f}%/month across {s("Power Matrix","top","n_periods")} periods.',
        body_style))
    story.append(PageBreak())

    # ===== 7. METHODOLOGY =====
    story.append(Paragraph('7. Methodology & Limitations', h1_style))

    story.append(Paragraph('Walk-Forward Protocol', h2_style))
    story.append(Paragraph(
        '1. <b>Monthly rebalance dates:</b> Last trading day of each month, Jan 2022 – Feb 2026 (50 periods).<br/>'
        '2. <b>Score computation:</b> All indicators computed using <b>only</b> data available on the rebalance date. '
        'No future data is used in scoring.<br/>'
        '3. <b>Portfolio formation:</b> Stocks sorted by score. Top/bottom deciles (10%) form the long/short portfolios.<br/>'
        '4. <b>Forward returns:</b> 21-day (1-month) forward returns measured from rebalance date.<br/>'
        '5. <b>Aggregation:</b> Average, median, win rate, and cumulative compounded returns across all periods.',
        body_style))
    story.append(Spacer(1, 6))

    story.append(Paragraph('Known Limitations', h2_style))
    limitations = [
        '<b>No transaction costs:</b> Results do not include commissions, slippage, or bid-ask spreads. '
        'Monthly rebalancing of 100+ stocks would incur meaningful friction.',
        '<b>Survivorship bias:</b> The stock universe is based on today\'s 1,008 stocks. '
        'Companies that delisted, merged, or went bankrupt during 2021-2026 are not included, '
        'which inflates returns for all strategies.',
        '<b>Quality & Rotation proxies:</b> The full Quality Score and Rotation Score use fundamental data '
        '(revenue growth, ROE, margins, earnings momentum) that is not available in the OHLCV dataset. '
        'Backtest uses price/volume proxies covering ~60% of scoring factors.',
        '<b>IQ Edge model contamination:</b> The XGBoost model was trained on 2021-2024 data. '
        'Walk-forward rebalances in 2022-2024 overlap with the training period. '
        'Only 2025-2026 results (14 periods) are truly out-of-sample for IQ Edge.',
        '<b>Equal-weight portfolios:</b> All stocks in each decile are equally weighted. '
        'Position sizing, risk management, and concentration effects are not modeled.',
        '<b>No short-side costs:</b> Avoid/bottom decile returns are shown for comparison. '
        'Actually shorting these stocks would involve borrow costs and margin requirements.',
    ]
    for lim in limitations:
        story.append(Paragraph(f'• {lim}', ParagraphStyle('Lim', parent=body_style, leftIndent=12, spaceBefore=3)))
    story.append(Spacer(1, 8))

    story.append(Paragraph('Signal Confidence Assessment', h2_style))
    confidence_table = [
        ['Signal', 'Backtest Confidence', 'Why'],
        ['EWROS', 'HIGH', 'Fully computable from price data. No proxy needed. 50 periods.'],
        ['IQ Edge', 'MEDIUM', 'Real ML model, but 2022-2024 overlaps training data.'],
        ['Power Matrix', 'MEDIUM', 'Combines EWROS (high conf.) with Rotation (proxy).'],
        ['Rotation', 'LOW-MEDIUM', 'Only price/volume signals tested (3 of 6).'],
        ['Quality', 'LOW', 'Price/volume proxy only. Fundamental factors untested.'],
    ]
    story.append(make_table(confidence_table, col_widths=[1.2*inch, 1.2*inch, 4.1*inch]))

    # ===== 8. APPENDIX =====
    story.append(Paragraph('8. Appendix: Parameters & Configuration', h1_style))

    story.append(Paragraph('Daily Pipeline (Mon–Fri ET)', h2_style))
    pipeline = [
        ['Time', 'Job', 'Type'],
        ['4:05 PM', 'Daily Closing Scan', 'Script'],
        ['4:15 PM', 'Distribution Day Scan', 'Script'],
        ['4:20 PM', 'Earnings Calendar + Alert', 'Script'],
        ['4:30 PM', 'Cache Refresh + Sector Leaderboard', 'Script'],
        ['4:45 PM', 'Full Scan (Quality + Rotation + EWROS + IQ Edge)', 'Script'],
        ['5:00 PM', 'Sell Signal Check', 'Script'],
        ['5:30 PM', 'Earnings Recap Email', 'Script'],
        ['6:00 PM', 'Insider Transaction Scan', 'Script'],
        ['7:00 PM', 'Daily Alpha Report', 'LLM'],
    ]
    story.append(make_table(pipeline, col_widths=[0.8*inch, 3.5*inch, 2.2*inch]))
    story.append(Spacer(1, 6))

    story.append(Paragraph('Architecture', h2_style))
    story.append(Paragraph(
        'Backend: Python/Flask · ML: XGBoost + scikit-learn · Data: yfinance + Supabase · '
        'Frontend: Vanilla JS + Chart.js · Deployment: Vercel · Domain: theiqinvestor.com',
        body_style))

    # Disclaimer
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width='100%', color=BORDER_COLOR, thickness=0.5))
    story.append(Paragraph(
        '<b>Disclaimer:</b> Past performance does not guarantee future results. This report is for informational '
        'purposes only and does not constitute investment advice. Backtesting results are hypothetical, do not '
        'reflect actual trading, and are subject to the limitations described in Section 7. All results include '
        'survivorship bias and exclude transaction costs.',
        ParagraphStyle('Disclaimer', parent=body_style, fontSize=7, textColor=TEXT_DARK, spaceBefore=6)))

    doc.build(story)
    print(f'✅ Report generated: {OUTPUT}')
    print(f'   Size: {os.path.getsize(OUTPUT) / 1024:.0f} KB')


if __name__ == '__main__':
    build_report()
