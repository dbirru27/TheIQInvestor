#!/usr/bin/env python3
"""
TenX Hunter - Hypergrowth 10X Potential Scanner
Qualitative overlay for identifying stocks with 10X potential

Usage: python3 tenx_scan.py [tickers...] or reads from stdin
Example: python3 tenx_scan.py VRT TSM MU LLY
         cat top_stocks.json | python3 tenx_scan.py
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# TenX framework criteria
TENX_CRITERIA = {
    "new_product": {
        "weight": 0.20,
        "description": "New product driving growth, category creator potential"
    },
    "growth_engine": {
        "weight": 0.20,
        "description": "Revenue growth accelerating, operating leverage improving"
    },
    "moat_durability": {
        "weight": 0.20,
        "description": "Competitive advantage widening, high switching costs"
    },
    "visionary_ceo": {
        "weight": 0.15,
        "description": "Founder-led, long-term vision, product obsession"
    },
    "market_tailwinds": {
        "weight": 0.15,
        "description": "20%+ market CAGR, secular trend, early penetration"
    },
    "mega_trend_position": {
        "weight": 0.10,
        "description": "1st or 2nd order beneficiary of mega-trend"
    }
}

# Known 10X candidates with pre-scored attributes
TENX_KNOWLEDGE_BASE = {
    "VRT": {
        "new_product": 9,
        "growth_engine": 9,
        "moat_durability": 8,
        "visionary_ceo": 7,
        "market_tailwinds": 10,
        "mega_trend_position": 9,
        "thesis": "2nd order AI play - data center power infrastructure. Every AI chip needs power. Vertiv has monopoly positioning in thermal management and power distribution. AI data center demand exploding.",
        "mega_trend": "AI Infrastructure (2nd Order)",
        "why_now": "AI data center buildout just beginning. 6-month consolidation breakout pattern. Grid-to-chip theme gaining institutional attention."
    },
    "TSM": {
        "new_product": 7,
        "growth_engine": 9,
        "moat_durability": 10,
        "visionary_ceo": 7,
        "market_tailwinds": 9,
        "mega_trend_position": 9,
        "thesis": "Foundry monopoly - makes chips for NVDA, AMD, AAPL. 2-3 year technology lead. 90% of advanced AI chips. Supply-constrained = pricing power.",
        "mega_trend": "AI Infrastructure (2nd Order)",
        "why_now": "AI chip demand outpacing supply. Geographic diversification reducing geopolitical risk. Every AI model needs more compute."
    },
    "NVDA": {
        "new_product": 10,
        "growth_engine": 10,
        "moat_durability": 9,
        "visionary_ceo": 9,
        "market_tailwinds": 10,
        "mega_trend_position": 10,
        "thesis": "CUDA ecosystem = 15 years of developer lock-in. 90% AI training market. Platform expanding into inference, robotics, autonomous vehicles.",
        "mega_trend": "AI Infrastructure (1st Order)",
        "why_now": "AI boom just beginning. But $4T market cap makes 10X harder. Still best-positioned for AI infrastructure buildout."
    },
    "MU": {
        "new_product": 8,
        "growth_engine": 8,
        "moat_durability": 7,
        "visionary_ceo": 6,
        "market_tailwinds": 9,
        "mega_trend_position": 8,
        "thesis": "HBM memory oligopoly with Samsung/SK Hynix. AI chips need HBM. Memory cycle turning up + AI structural demand. Turnaround story.",
        "mega_trend": "AI Infrastructure (2nd Order)",
        "why_now": "HBM supply-constrained through 2025. Memory prices recovering. AI data centers need exponentially more memory."
    },
    "LLY": {
        "new_product": 10,
        "growth_engine": 10,
        "moat_durability": 8,
        "visionary_ceo": 7,
        "market_tailwinds": 10,
        "mega_trend_position": 9,
        "thesis": "GLP-1 drugs (Mounjaro/Zepbound) for obesity/diabetes. Massive TAM expansion. Patent protection 20 years. Only Novo Nordisk as real competitor.",
        "mega_trend": "GLP-1/Healthcare (1st Order)",
        "why_now": "Obesity drug market just opening. Supply ramping to meet demand. Medicare coverage expanding. Cultural shift around weight loss drugs."
    },
    "AVGO": {
        "new_product": 8,
        "growth_engine": 8,
        "moat_durability": 9,
        "visionary_ceo": 8,
        "market_tailwinds": 8,
        "mega_trend_position": 8,
        "thesis": "Custom chip designs deeply embedded in AAPL products. VMware acquisition adds recurring software revenue. AI chip exposure.",
        "mega_trend": "AI Infrastructure (1st + 2nd Order)",
        "why_now": "AI chip demand + software transformation. VMware integration showing synergies. Custom silicon trend accelerating."
    },
    "ASML": {
        "new_product": 9,
        "growth_engine": 8,
        "moat_durability": 10,
        "visionary_ceo": 7,
        "market_tailwinds": 8,
        "mega_trend_position": 8,
        "thesis": "SOLE supplier of EUV lithography. 100% market share for advanced chips. $200M+ per machine. Years-long backlog.",
        "mega_trend": "Semiconductor Equipment (1st Order)",
        "why_now": "Chip Act funding driving fab construction. Every AI chip needs ASML machines. Supply-constrained for years."
    },
    "TSLA": {
        "new_product": 7,
        "growth_engine": 6,
        "moat_durability": 4,
        "visionary_ceo": 7,
        "market_tailwinds": 7,
        "mega_trend_position": 7,
        "thesis": "EV pioneer with brand strength. But first-mover advantage eroding (BYD competition). No true moat. FSD promises unfulfilled.",
        "mega_trend": "Electrification (1st Order)",
        "why_now": "OVERVALUED. EV competition intensifying. China price wars. 371x PE for auto company. NOT a 10X candidate from here.",
        "warning": "No moat, excessive valuation, competition eroding advantages"
    },
    "PLTR": {
        "new_product": 6,
        "growth_engine": 6,
        "moat_durability": 3,
        "visionary_ceo": 5,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Government AI/data analytics contracts. But lumpy revenue, no switching costs, 200x PE. Hype exceeds fundamentals.",
        "mega_trend": "AI Software (1st Order)",
        "why_now": "OVERVALUED. Government budget uncertainty. No durable moat. AI hype may not translate to sustained growth.",
        "warning": "Extreme valuation, no moat, customer concentration"
    },
    "UBER": {
        "new_product": 4,
        "growth_engine": 6,
        "moat_durability": 3,
        "visionary_ceo": 6,
        "market_tailwinds": 5,
        "mega_trend_position": 4,
        "thesis": "Rideshare + delivery platform. But commoditized service, no pricing power, drivers/riders multi-home. Barely profitable.",
        "mega_trend": "Gig Economy (1st Order)",
        "why_now": "Market saturated. Competition from Lyft/DoorDash. Regulatory risk (employee classification). NOT a 10X candidate.",
        "warning": "No moat, low margins, regulatory risk"
    },
    "NFLX": {
        "new_product": 5,
        "growth_engine": 6,
        "moat_durability": 5,
        "visionary_ceo": 7,
        "market_tailwinds": 5,
        "mega_trend_position": 5,
        "thesis": "Streaming leader with content library. But content is not a moat. Disney+/Apple TV competition intensifying. Market maturing.",
        "mega_trend": "Streaming (1st Order)",
        "why_now": "Market saturated. Content costs rising. Password crackdown one-time boost. Not early innings anymore.",
        "warning": "Content arms race, competition, market maturity"
    },
    "CRWD": {
        "new_product": 6,
        "growth_engine": 6,
        "moat_durability": 4,
        "visionary_ceo": 6,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Endpoint security leader. But crowded market (MSFT Defender, PANW, SentinelOne). Recent outage damaged reputation.",
        "mega_trend": "Cybersecurity (1st Order)",
        "why_now": "Commoditization risk. Microsoft bundling competition. No durable moat in endpoint security.",
        "warning": "Commoditized product, Microsoft competition"
    },
    "PWR": {
        "new_product": 7,
        "growth_engine": 8,
        "moat_durability": 7,
        "visionary_ceo": 7,
        "market_tailwinds": 9,
        "mega_trend_position": 9,
        "thesis": "Grid modernization leader. EVs + data centers + renewable energy all need grid upgrades. 6-month consolidation breakout.",
        "mega_trend": "Electrification (2nd Order)",
        "why_now": "Grid infrastructure aging. Electrification demand surging. Government infrastructure spending. Breakout pattern forming."
    },
    "META": {
        "new_product": 8,
        "growth_engine": 8,
        "moat_durability": 9,
        "visionary_ceo": 7,
        "market_tailwinds": 7,
        "mega_trend_position": 8,
        "thesis": "Social graph lock-in (3B users). Instagram dominance. AI recommendation engine (Reels). Strong moat but already large.",
        "mega_trend": "AI + Social Media (1st Order)",
        "why_now": "AI integration improving engagement. Cost discipline restored. But $1.7T market cap limits 10X potential."
    },
    "MSFT": {
        "new_product": 8,
        "growth_engine": 8,
        "moat_durability": 10,
        "visionary_ceo": 8,
        "market_tailwinds": 8,
        "mega_trend_position": 9,
        "thesis": "Triple moat: Azure switching costs + Office 365 ecosystem + LinkedIn network. Copilot AI integration deepening moat.",
        "mega_trend": "AI + Cloud (1st + 2nd Order)",
        "why_now": "AI leadership with OpenAI partnership. Copilot monetization beginning. But $2.9T market cap limits 10X."
    },
    "GOOGL": {
        "new_product": 8,
        "growth_engine": 7,
        "moat_durability": 9,
        "visionary_ceo": 7,
        "market_tailwinds": 7,
        "mega_trend_position": 8,
        "thesis": "Search data flywheel + YouTube ecosystem. AI integration with Gemini. Strong moat but search dominance mature.",
        "mega_trend": "AI + Search (1st Order)",
        "why_now": "AI search threat from ChatGPT. But data advantage remains. Cloud growth continues."
    },
    "AMZN": {
        "new_product": 7,
        "growth_engine": 7,
        "moat_durability": 7,
        "visionary_ceo": 8,
        "market_tailwinds": 7,
        "mega_trend_position": 7,
        "thesis": "AWS switching costs + logistics scale. But competition intensifying (Azure/GCP, Temu/Shein). Moat narrowing.",
        "mega_trend": "Cloud + E-commerce (1st Order)",
        "why_now": "Cloud optimization headwinds ending. AWS growth stabilizing. Retail margin pressure."
    },
    "AMD": {
        "new_product": 6,
        "growth_engine": 6,
        "moat_durability": 5,
        "visionary_ceo": 6,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Only credible x86 alternative to Intel. Gaming/CPU leadership. But no CUDA-like ecosystem. AI efforts lagging NVDA.",
        "mega_trend": "AI Infrastructure (1st Order)",
        "why_now": "MI300 AI chips gaining traction but late to market. No ecosystem lock-in like CUDA.",
        "warning": "No ecosystem moat, NVDA dominance, custom silicon threat"
    },
    "LRCX": {
        "new_product": 5,
        "growth_engine": 6,
        "moat_durability": 6,
        "visionary_ceo": 6,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Etch/deposition equipment leader in semi capital equipment oligopoly. But no ASML-level monopoly. Cyclical.",
        "mega_trend": "Semiconductor Equipment (2nd Order)",
        "why_now": "Chip Act fab buildouts. But mature oligopoly, cyclical demand, China restrictions."
    },
    "AMAT": {
        "new_product": 5,
        "growth_engine": 6,
        "moat_durability": 6,
        "visionary_ceo": 6,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Broadest equipment portfolio in semi equipment. Materials engineering expertise. But shared oligopoly with LRCX/TEL.",
        "mega_trend": "Semiconductor Equipment (2nd Order)",
        "why_now": "Fab construction boom. But cyclical, competitive, no single-product dominance."
    },
    "MRVL": {
        "new_product": 6,
        "growth_engine": 5,
        "moat_durability": 4,
        "visionary_ceo": 5,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "Data center/AI chip designer. But competes with NVDA, AMD, AVGO. No ecosystem. Customer concentration risk.",
        "mega_trend": "AI Infrastructure (1st Order)",
        "why_now": "NVDA shadow too large. No durable differentiation. Acquired growth, not organic.",
        "warning": "NVDA dominance, customer concentration, no moat"
    },
    "WDC": {
        "new_product": 4,
        "growth_engine": 4,
        "moat_durability": 3,
        "visionary_ceo": 4,
        "market_tailwinds": 5,
        "mega_trend_position": 4,
        "thesis": "HDD/SSD storage commodity player. Duopoly with STX in HDDs but SSDs commoditized. Pure cyclical, no pricing power.",
        "mega_trend": "Data Storage (2nd Order)",
        "why_now": "Commoditized storage. Memory price cycles. No innovation edge.",
        "warning": "Commoditized, cyclical, no moat"
    },
    "STX": {
        "new_product": 4,
        "growth_engine": 4,
        "moat_durability": 3,
        "visionary_ceo": 4,
        "market_tailwinds": 5,
        "mega_trend_position": 4,
        "thesis": "Same as WDC - HDD duopoly but SSD commoditization. No durable advantage. Cyclical commodity business.",
        "mega_trend": "Data Storage (2nd Order)",
        "why_now": "Technology shift to SSDs/NVMe. Declining HDD market. Commoditized."
    },
    "PANW": {
        "new_product": 6,
        "growth_engine": 6,
        "moat_durability": 5,
        "visionary_ceo": 6,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Integrated security platform with some switching costs. But CRWD/ZS competition intense. Feature parity issues.",
        "mega_trend": "Cybersecurity (1st Order)",
        "why_now": "Platform consolidation trend. But crowded market, no clear winner."
    },
    "GE": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 4,
        "visionary_ceo": 5,
        "market_tailwinds": 5,
        "mega_trend_position": 5,
        "thesis": "Aerospace duopoly with RTX. But no pricing power, airline customer concentration, capital intensive. Post-breakup finding footing.",
        "mega_trend": "Aviation (1st Order)",
        "why_now": "Aviation recovery post-COVID. But cyclical, competitive, turnaround story."
    },
    "UNH": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 5,
        "visionary_ceo": 5,
        "market_tailwinds": 5,
        "mega_trend_position": 5,
        "thesis": "Largest US insurer with Optum vertical integration. But regulatory risk, thin margins, political headwinds.",
        "mega_trend": "Healthcare (1st Order)",
        "why_now": "Medicare Advantage growth. But regulatory scrutiny, margin pressure."
    },
    "JPM": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 5,
        "visionary_ceo": 6,
        "market_tailwinds": 4,
        "mega_trend_position": 4,
        "thesis": "Largest US bank with scale advantages. But fintech disruption, regulatory burden, credit cycle exposure. Too big to be agile.",
        "mega_trend": "Financial Services (1st Order)",
        "why_now": "Rate environment stabilizing. But mature market, disruption risk, size constraints."
    },
    "V": {
        "new_product": 4,
        "growth_engine": 6,
        "moat_durability": 8,
        "visionary_ceo": 6,
        "market_tailwinds": 5,
        "mega_trend_position": 5,
        "thesis": "Strong two-sided network effects with 50% margins. But market mature, fintech disruption, crypto alternatives.",
        "mega_trend": "Payments (1st Order)",
        "why_now": "Strong moat but limited growth runway. Market penetration high. Stable, not hypergrowth."
    },
    "BRK-B": {
        "new_product": 3,
        "growth_engine": 4,
        "moat_durability": 7,
        "visionary_ceo": 7,
        "market_tailwinds": 4,
        "mega_trend_position": 4,
        "thesis": "Insurance float + diversified quality holdings. But Buffett succession uncertainty, size drag on returns, mature portfolio.",
        "mega_trend": "Conglomerate (N/A)",
        "why_now": "Stable compounder but not 10X material. $1T+ market cap. Conservative value play."
    },
    "CAT": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 5,
        "visionary_ceo": 5,
        "market_tailwinds": 5,
        "mega_trend_position": 5,
        "thesis": "Heavy equipment brand leader with service network. But cyclical, Komatsu competition, infrastructure spending dependent.",
        "mega_trend": "Infrastructure (1st Order)",
        "why_now": "Infrastructure bill tailwinds. But cyclical peak concerns, China exposure."
    },
    "HD": {
        "new_product": 3,
        "growth_engine": 4,
        "moat_durability": 5,
        "visionary_ceo": 5,
        "market_tailwinds": 4,
        "mega_trend_position": 4,
        "thesis": "Scale + location moat in home improvement. But mature market, housing cycle dependent, Amazon/LOW competition.",
        "mega_trend": "Retail (1st Order)",
        "why_now": "Housing market uncertainty. Interest rate sensitivity. Mature, not hypergrowth."
    },
    "NOW": {
        "new_product": 5,
        "growth_engine": 6,
        "moat_durability": 4,
        "visionary_ceo": 5,
        "market_tailwinds": 5,
        "mega_trend_position": 5,
        "thesis": "ITSM software leader. But Atlassian/MSFT/Salesforce competition. No network effects. High switching costs temporary only.",
        "mega_trend": "Enterprise Software (1st Order)",
        "why_now": "AI integration potential. But 61x PE, commoditization risk, competition.",
        "warning": "High valuation, no moat, competition"
    },
    "ISRG": {
        "new_product": 5,
        "growth_engine": 6,
        "moat_durability": 7,
        "visionary_ceo": 6,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "Da Vinci surgical robot monopoly. 20+ years of installed base, switching costs, training moat. But mature market, competition from Medtronic.",
        "mega_trend": "MedTech/Robotics (1st Order)",
        "why_now": "Surgical robotics adoption growing. But installed base mature, growth slowing, new competition."
    },
    "ORCL": {
        "new_product": 5,
        "growth_engine": 5,
        "moat_durability": 6,
        "visionary_ceo": 6,
        "market_tailwinds": 5,
        "mega_trend_position": 5,
        "thesis": "Database legacy + cloud pivot. Cerner acquisition adds healthcare. But cloud lags AWS/Azure, legacy business declining.",
        "mega_trend": "Cloud/Database (1st Order)",
        "why_now": "Cloud migration continuing. But mature company, growth <10%, AI efforts lagging."
    },
    "CRM": {
        "new_product": 6,
        "growth_engine": 6,
        "moat_durability": 6,
        "visionary_ceo": 6,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "CRM pioneer, enterprise switching costs. Einstein AI integration. But MSFT Dynamics competition, growth slowing, acquisitions dilutive.",
        "mega_trend": "Enterprise Software (1st Order)",
        "why_now": "AI integration efforts. But 50x+ PE, slowing growth, competitive pressure."
    },
    "TMUS": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 4,
        "visionary_ceo": 6,
        "market_tailwinds": 4,
        "mega_trend_position": 3,
        "thesis": "T-Mobile #2 US carrier. 5G network advantage, customer growth. But commoditized service, VZ/T competition, mature market.",
        "mega_trend": "Telecom (1st Order)",
        "why_now": "5G network complete. Market share gains from Sprint merger. But mature, no pricing power."
    },
    "ANET": {
        "new_product": 7,
        "growth_engine": 8,
        "moat_durability": 7,
        "visionary_ceo": 8,
        "market_tailwinds": 9,
        "mega_trend_position": 9,
        "thesis": "AI networking leader. Ethernet for AI clusters. Google/Meta/MSFT all using Arista. Displacing Cisco in cloud data centers.",
        "mega_trend": "AI Infrastructure (2nd Order)",
        "why_now": "AI data centers need high-speed networking. 800G/1.6T transition. Cloud capex surging."
    },
    "LHX": {
        "new_product": 5,
        "growth_engine": 6,
        "moat_durability": 6,
        "visionary_ceo": 6,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Defense electronics, C4ISR, space systems. Strong government relationships. But lumpy contracts, budget dependent.",
        "mega_trend": "Defense/Security (1st Order)",
        "why_now": "Geopolitical tensions rising. NATO spending increases. Space/AI modernization."
    },
    "LMT": {
        "new_product": 5,
        "growth_engine": 5,
        "moat_durability": 6,
        "visionary_ceo": 5,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "Largest defense contractor. F-35, classified programs. But program delays, cost overruns, budget constraints.",
        "mega_trend": "Defense/Security (1st Order)",
        "why_now": "Global tensions support budgets. But mature programs, execution challenges."
    },
    "NOC": {
        "new_product": 6,
        "growth_engine": 6,
        "moat_durability": 6,
        "visionary_ceo": 6,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Space, cyber, autonomous systems. B-21 bomber, GBSD. Higher growth areas than traditional defense.",
        "mega_trend": "Defense/Security (1st Order)",
        "why_now": "Space/cyber growth faster than traditional. Nuclear modernization."
    },
    "PWR": {
        "new_product": 7,
        "growth_engine": 8,
        "moat_durability": 7,
        "visionary_ceo": 7,
        "market_tailwinds": 9,
        "mega_trend_position": 9,
        "thesis": "Grid modernization leader. EVs + data centers + renewables all need grid upgrades. 6-month consolidation breakout.",
        "mega_trend": "Electrification (2nd Order)",
        "why_now": "Grid infrastructure aging. Electrification demand surging. Government infrastructure spending. Breakout pattern forming."
    },
    "GEV": {
        "new_product": 6,
        "growth_engine": 7,
        "moat_durability": 6,
        "visionary_ceo": 6,
        "market_tailwinds": 8,
        "mega_trend_position": 8,
        "thesis": "GE spinoff - pure-play power. Gas turbines, grid, renewables. Cleaner balance sheet post-spin.",
        "mega_trend": "Electrification (2nd Order)",
        "why_now": "Power demand surging. Grid modernization. Cleaner structure post-GE breakup."
    },
    "UFO": {
        "new_product": 5,
        "growth_engine": 6,
        "moat_durability": 3,
        "visionary_ceo": 4,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "ETF holding space companies (satellites, launch, ground equipment). Diversified exposure. But ETF structure, no single-stock 10X potential.",
        "mega_trend": "Space Economy (ETF)",
        "why_now": "Space economy growing but early. ETF diversification limits 10X potential.",
        "warning": "ETF - not a 10X single stock"
    },
    "XLP": {
        "new_product": 3,
        "growth_engine": 4,
        "moat_durability": 5,
        "visionary_ceo": 4,
        "market_tailwinds": 3,
        "mega_trend_position": 3,
        "thesis": "Consumer staples ETF (PG, KO, WMT, etc.). Defensive sector. Slow growth, not 10X material.",
        "mega_trend": "Defensive Staples (ETF)",
        "why_now": "Recession hedge, not growth. Mature companies. ETF structure.",
        "warning": "ETF - defensive, low growth"
    },
    "COPX": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 3,
        "visionary_ceo": 4,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "Copper miners ETF. Electrification needs copper. But commodity ETF - cyclical, no pricing power, no moat.",
        "mega_trend": "Electrification (Commodity ETF)",
        "why_now": "Copper demand rising. Supply constrained. But ETF structure, cyclical.",
        "warning": "Commodity ETF - cyclical, no moat"
    },
    "SIL": {
        "new_product": 3,
        "growth_engine": 4,
        "moat_durability": 3,
        "visionary_ceo": 3,
        "market_tailwinds": 4,
        "mega_trend_position": 3,
        "thesis": "Silver miners ETF. Precious metals exposure. No 10X potential - commodity, cyclical, no moat.",
        "mega_trend": "Precious Metals (Commodity ETF)",
        "why_now": "Silver industrial demand + store of value. But ETF, no single stock alpha.",
        "warning": "Commodity ETF - speculative"
    },
    "XBI": {
        "new_product": 6,
        "growth_engine": 7,
        "moat_durability": 4,
        "visionary_ceo": 5,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Biotech ETF - equal weighted, small/mid cap focus. High risk/high reward sector. Individual biotechs can 10X but ETF diversifies away alpha.",
        "mega_trend": "Biotech Innovation (ETF)",
        "why_now": "GLP-1 success driving biotech interest. But ETF structure limits 10X.",
        "warning": "ETF - high risk sector but diversified"
    },
    "XME": {
        "new_product": 3,
        "growth_engine": 4,
        "moat_durability": 3,
        "visionary_ceo": 3,
        "market_tailwinds": 4,
        "mega_trend_position": 3,
        "thesis": "Metals & Mining ETF. Copper, steel, aluminum, coal. Commodity cyclical exposure. No moat, no 10X potential as ETF.",
        "mega_trend": "Materials/Commodities (ETF)",
        "why_now": "Infrastructure spending. But cyclical, no pricing power.",
        "warning": "Commodity ETF - cyclical"
    },
    "DXJ": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 4,
        "visionary_ceo": 4,
        "market_tailwinds": 5,
        "mega_trend_position": 4,
        "thesis": "Japan hedged equity ETF. Currency hedged Japan exposure. Diversification play, not 10X material.",
        "mega_trend": "International Diversification (ETF)",
        "why_now": "Japan corporate governance improving. But ETF, currency play.",
        "warning": "ETF - international diversification"
    },
    "GRID": {
        "new_product": 5,
        "growth_engine": 6,
        "moat_durability": 4,
        "visionary_ceo": 4,
        "market_tailwinds": 8,
        "mega_trend_position": 7,
        "thesis": "Grid infrastructure ETF. Smart grid, electrical components. Electrification play but diversified - includes utilities.",
        "mega_trend": "Electrification (ETF)",
        "why_now": "Grid modernization theme. But ETF structure, utility exposure limits growth.",
        "warning": "ETF - diversified grid exposure"
    },
    "GLD": {
        "new_product": 2,
        "growth_engine": 2,
        "moat_durability": 2,
        "visionary_ceo": 2,
        "market_tailwinds": 3,
        "mega_trend_position": 2,
        "thesis": "Physical gold ETF. Inflation/uncertainty hedge. No growth, no 10X potential. Store of value only.",
        "mega_trend": "None - Store of Value",
        "why_now": "Inflation hedge. But gold doesn't grow - it's a store of value.",
        "warning": "No 10X potential - store of value"
    },
    "GLDM": {
        "new_product": 2,
        "growth_engine": 2,
        "moat_durability": 2,
        "visionary_ceo": 2,
        "market_tailwinds": 3,
        "mega_trend_position": 2,
        "thesis": "Same as GLD - physical gold ETF, lower expense ratio. No growth, no 10X potential.",
        "mega_trend": "None - Store of Value",
        "why_now": "Same as GLD - inflation hedge only.",
        "warning": "No 10X potential - store of value"
    },
    "ITA": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 4,
        "visionary_ceo": 4,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "Aerospace & Defense ETF. Boeing, Lockheed, RTX, etc. Government spending play. But ETF diversifies away single-stock 10X potential.",
        "mega_trend": "Defense Spending (ETF)",
        "why_now": "Geopolitical tensions. But ETF, mature sector.",
        "warning": "ETF - defense sector exposure"
    },
    "IWM": {
        "new_product": 3,
        "growth_engine": 4,
        "moat_durability": 3,
        "visionary_ceo": 3,
        "market_tailwinds": 4,
        "mega_trend_position": 3,
        "thesis": "Russell 2000 ETF - small cap exposure. Broad diversification. No 10X potential as ETF - it's the benchmark.",
        "mega_trend": "Small Cap Beta (ETF)",
        "why_now": "Small cap value play. But ETF = market return.",
        "warning": "ETF - broad small cap exposure"
    },
    "NLR": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 5,
        "visionary_ceo": 4,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Nuclear energy ETF. Uranium miners + nuclear utilities. Clean energy pivot. But ETF structure.",
        "mega_trend": "Clean Energy/Nuclear (ETF)",
        "why_now": "Nuclear renaissance. But ETF diversified, regulatory risks.",
        "warning": "ETF - nuclear exposure"
    },
    "VOO": {
        "new_product": 2,
        "growth_engine": 3,
        "moat_durability": 3,
        "visionary_ceo": 2,
        "market_tailwinds": 3,
        "mega_trend_position": 2,
        "thesis": "S&P 500 ETF. Market beta exposure. No 10X potential - it's literally the market average.",
        "mega_trend": "US Large Cap (ETF)",
        "why_now": "Core holding. But ETF = 8% annual returns, not 10X.",
        "warning": "No 10X potential - this is the benchmark"
    },
    "XLI": {
        "new_product": 3,
        "growth_engine": 4,
        "moat_durability": 4,
        "visionary_ceo": 3,
        "market_tailwinds": 5,
        "mega_trend_position": 4,
        "thesis": "Industrials Select Sector ETF. GE, CAT, UPS, etc. Diversified industrials exposure. Not 10X material.",
        "mega_trend": "Industrials (ETF)",
        "why_now": "Infrastructure spending. But ETF, cyclical sector.",
        "warning": "ETF - diversified industrials"
    },
    "HALO": {
        "new_product": 8,
        "growth_engine": 9,
        "moat_durability": 7,
        "visionary_ceo": 7,
        "market_tailwinds": 9,
        "mega_trend_position": 8,
        "thesis": "Drug delivery platform technology. Enables other biotechs. Royalty model = recurring revenue. ENHANZE platform partnerships with JNJ, Roche, etc.",
        "mega_trend": "Biotech/Delivery (2nd Order)",
        "why_now": "Platform partnerships expanding. Royalty revenue growing. 6-month breakout candidate."
    },
    "FNB": {
        "new_product": 4,
        "growth_engine": 6,
        "moat_durability": 4,
        "visionary_ceo": 5,
        "market_tailwinds": 5,
        "mega_trend_position": 3,
        "thesis": "Regional bank. Rate environment beneficiary. M&A candidate. But regional banks have no moat, credit cycle exposure.",
        "mega_trend": "Regional Banking (Cyclical)",
        "why_now": "Rate stabilization. But no durable advantage, commodity business.",
        "warning": "No moat, cyclical, regional bank"
    },
    "SON": {
        "new_product": 6,
        "growth_engine": 6,
        "moat_durability": 5,
        "visionary_ceo": 5,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "Sustainable packaging leader. E-commerce demand + sustainability trends. But packaging is cyclical, competitive.",
        "mega_trend": "Sustainability/E-commerce (2nd Order)",
        "why_now": "Sustainability mandates growing. But commodity packaging, limited pricing power."
    },
    "JHG": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 4,
        "visionary_ceo": 5,
        "market_tailwinds": 4,
        "mega_trend_position": 3,
        "thesis": "Asset management. Pending acquisition by Franklin Templeton. No standalone 10X potential - merger arb play.",
        "mega_trend": "Asset Management (Cyclical)",
        "why_now": "Acquisition pending. Not a 10X candidate.",
        "warning": "Acquisition target - merger arb only"
    },
    "ALSN": {
        "new_product": 6,
        "growth_engine": 6,
        "moat_durability": 5,
        "visionary_ceo": 5,
        "market_tailwinds": 6,
        "mega_trend_position": 5,
        "thesis": "Transmission electrification for commercial vehicles. Electric axle growth. But auto supplier - low margins, OEM pricing pressure.",
        "mega_trend": "EV Commercial Vehicles (2nd Order)",
        "why_now": "Commercial EV adoption growing. But supplier to OEMs = no pricing power."
    },
    "EIX": {
        "new_product": 4,
        "growth_engine": 5,
        "moat_durability": 5,
        "visionary_ceo": 4,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "California utility. Grid modernization beneficiary. But regulated utility = slow growth, regulatory risk.",
        "mega_trend": "Grid Modernization (Regulated Utility)",
        "why_now": "Grid investment growing. But 4-6% utility growth, not 10X material.",
        "warning": "Utility - slow growth, regulated"
    },
    "INCY": {
        "new_product": 7,
        "growth_engine": 7,
        "moat_durability": 6,
        "visionary_ceo": 6,
        "market_tailwinds": 7,
        "mega_trend_position": 6,
        "thesis": "Oncology/immunology biotech. Jakafi franchise + pipeline. But patent cliffs, competitive oncology market.",
        "mega_trend": "Biotech/Oncology (1st Order)",
        "why_now": "Pipeline catalysts. But single-product risk, competition."
    }
}

def calculate_tenx_score(stock_data):
    """Calculate weighted 10X score"""
    total_score = 0
    for criterion, config in TENX_CRITERIA.items():
        score = stock_data.get(criterion, 5)
        total_score += score * config["weight"]
    return round(total_score, 1)

def get_grade(score):
    """Convert score (0-10) to letter grade"""
    if score >= 9.0:
        return "A+", "Exceptional 10X Candidate"
    elif score >= 8.5:
        return "A", "Strong 10X Potential"
    elif score >= 8.0:
        return "A-", "Very Good 10X Candidate"
    elif score >= 7.5:
        return "B+", "Possible 5-10X with Execution"
    elif score >= 7.0:
        return "B", "Moderate 10X Potential"
    elif score >= 6.5:
        return "B-", "2-5X Potential, More Mature"
    elif score >= 6.0:
        return "C+", "Limited 10X Characteristics"
    else:
        return "C", "Not a 10X Candidate"

def analyze_stock(ticker):
    """Analyze a single stock for 10X potential"""
    ticker = ticker.upper().strip()
    
    if ticker in TENX_KNOWLEDGE_BASE:
        data = TENX_KNOWLEDGE_BASE[ticker].copy()
    else:
        # Generic analysis for unknown stocks
        data = {
            "new_product": 5,
            "growth_engine": 5,
            "moat_durability": 5,
            "visionary_ceo": 5,
            "market_tailwinds": 5,
            "mega_trend_position": 5,
            "thesis": "No detailed analysis available. Run fundamental/technical scan first.",
            "mega_trend": "Unknown",
            "why_now": "Analysis required"
        }
    
    score = round(calculate_tenx_score(data) * 10, 1)  # Scale 0-10 → 0-100
    grade, description = get_grade(score / 10)  # grade fn still expects 0-10
    
    return {
        "ticker": ticker,
        "score": score,
        "grade": grade,
        "grade_description": description,
        "breakdown": {k: data.get(k, 5) for k in TENX_CRITERIA.keys()},
        "thesis": data.get("thesis", ""),
        "mega_trend": data.get("mega_trend", "Unknown"),
        "why_now": data.get("why_now", ""),
        "warning": data.get("warning", None)
    }

def generate_report(results):
    """Generate HTML report"""
    sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
    
    top_picks = ", ".join([r["ticker"] for r in sorted_results[:3] if r["score"] >= 75])
    
    html = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.4; color: #333; margin: 0; padding: 15px; background: #f5f5f5; }
        .container { max-width: 700px; margin: 0 auto; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 20px; }
        .header p { margin: 5px 0 0; opacity: 0.9; font-size: 12px; }
        
        .summary-box { background: #e8f4f8; border-left: 4px solid #667eea; padding: 12px; margin-bottom: 15px; border-radius: 5px; font-size: 13px; }
        
        .stock-card { border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 12px; background: white; }
        .stock-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 10px; }
        .ticker { font-size: 20px; font-weight: bold; color: #667eea; }
        .score { font-size: 28px; font-weight: bold; }
        .score-a { color: #28a745; }
        .score-b { color: #f39c12; }
        .score-c { color: #dc3545; }
        .grade { font-size: 14px; font-weight: bold; padding: 3px 10px; border-radius: 12px; }
        .grade-a { background: #d4edda; color: #155724; }
        .grade-b { background: #fff3cd; color: #856404; }
        .grade-c { background: #f8d7da; color: #721c24; }
        
        .mega-trend { background: #e3f2fd; color: #1565c0; padding: 4px 10px; border-radius: 12px; font-size: 11px; display: inline-block; margin: 5px 0; }
        
        .section-title { font-size: 11px; font-weight: bold; color: #666; text-transform: uppercase; margin: 12px 0 5px; }
        .thesis { font-size: 13px; color: #555; line-height: 1.5; }
        .why-now { background: #f0f8f0; padding: 10px; border-radius: 5px; font-size: 12px; margin-top: 8px; border-left: 3px solid #28a745; }
        .warning-box { background: #fff3cd; padding: 10px; border-radius: 5px; font-size: 12px; margin-top: 8px; border-left: 3px solid #f39c12; }
        
        .breakdown { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; font-size: 11px; }
        .breakdown-item { display: flex; justify-content: space-between; background: #f8f9fa; padding: 5px 8px; border-radius: 4px; }
        .breakdown-score { font-weight: bold; color: #667eea; }
        
        .footer { text-align: center; padding: 15px; color: #666; font-size: 11px; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 TenX Hunter Report</h1>
            <p>Hypergrowth 10X Potential Analysis | Qualitative Overlay</p>
        </div>

        <div class="summary-box">
            <strong>📊 Analysis Summary:</strong><br>
            Analyzed """ + str(len(results)) + """ stocks for 10X potential based on: New Product, Growth Engine, 
            Moat Durability, Visionary CEO, Market Tailwinds, and Mega-Trend Position.<br><br>
            <strong>🏆 Top 10X Candidates:</strong> """ + top_picks + """
        </div>
"""

    for result in sorted_results:
        score_class = "score-a" if result["score"] >= 80 else ("score-b" if result["score"] >= 65 else "score-c")
        grade_class = "grade-a" if result["grade"].startswith("A") else ("grade-b" if result["grade"].startswith("B") else "grade-c")
        
        html += """
        <div class="stock-card">
            <div class="stock-header">
                <div>
                    <span class="ticker">""" + result["ticker"] + """</span>
                    <span class="mega-trend">""" + result["mega_trend"] + """</span>
                </div>
                <div style="text-align: right;">
                    <span class="score """ + score_class + """">""" + str(result["score"]) + """</span>
                    <span class="grade """ + grade_class + """">""" + result["grade"] + """</span>
                </div>
            </div>
            
            <div class="section-title">10X Thesis</div>
            <div class="thesis">""" + result["thesis"] + """</div>
            
            <div class="section-title">Why Now?</div>
            <div class="why-now">""" + result["why_now"] + """</div>
"""
        if result.get("warning"):
            html += """
            <div class="warning-box"><strong>⚠️ Warning:</strong> """ + result["warning"] + """</div>
"""
        
        html += """
            <div class="breakdown">
                <div class="breakdown-item"><span>New Product</span><span class="breakdown-score">""" + str(result["breakdown"]["new_product"]) + """/10</span></div>
                <div class="breakdown-item"><span>Growth Engine</span><span class="breakdown-score">""" + str(result["breakdown"]["growth_engine"]) + """/10</span></div>
                <div class="breakdown-item"><span>Moat</span><span class="breakdown-score">""" + str(result["breakdown"]["moat_durability"]) + """/10</span></div>
                <div class="breakdown-item"><span>CEO Vision</span><span class="breakdown-score">""" + str(result["breakdown"]["visionary_ceo"]) + """/10</span></div>
                <div class="breakdown-item"><span>Market Tailwinds</span><span class="breakdown-score">""" + str(result["breakdown"]["market_tailwinds"]) + """/10</span></div>
                <div class="breakdown-item"><span>Trend Position</span><span class="breakdown-score">""" + str(result["breakdown"]["mega_trend_position"]) + """/10</span></div>
            </div>
        </div>
"""

    html += """
        <div class="footer">
            <p>TenX Hunter | Hypergrowth Qualitative Analysis</p>
            <p>Disclaimer: 10X stocks are rare and high-risk. Past performance doesn't guarantee future results.</p>
        </div>
    </div>
</body>
</html>
"""
    return html

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        tickers = sys.argv[1:]
    else:
        # Try to read from stdin
        try:
            input_data = sys.stdin.read()
            if input_data:
                # Try to parse as JSON
                try:
                    data = json.loads(input_data)
                    if isinstance(data, list):
                        tickers = [item.get("ticker", item.get("symbol", str(item))) for item in data]
                    elif isinstance(data, dict) and "stocks" in data:
                        tickers = [s.get("ticker", s.get("symbol")) for s in data["stocks"]]
                    else:
                        tickers = []
                except:
                    # Try as space/comma separated
                    tickers = [t.strip() for t in input_data.replace(",", " ").split() if t.strip()]
            else:
                # Default watchlist
                tickers = ["VRT", "TSM", "NVDA", "MU", "LLY", "AVGO", "ASML", "PWR"]
        except:
            tickers = ["VRT", "TSM", "NVDA", "MU", "LLY", "AVGO", "ASML", "PWR"]
    
    print(f"🔍 TenX Hunter: Analyzing {len(tickers)} stocks for 10X potential...")
    
    results = []
    for ticker in tickers:
        result = analyze_stock(ticker)
        results.append(result)
        print(f"  {ticker}: {result['score']:.1f} ({result['grade']}) - {result['grade_description']}")
    
    # Generate HTML report
    html = generate_report(results)
    
    output_path = "/tmp/tenx_scan_report.html"
    with open(output_path, "w") as f:
        f.write(html)
    
    print(f"\n✅ Report saved to: {output_path}")
    
    # Return top picks
    sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
    print(f"\n🏆 Top 10X Candidates:")
    for i, r in enumerate(sorted_results[:5], 1):
        print(f"  {i}. {r['ticker']}: {r['score']:.1f} - {r['mega_trend']}")
    
    return results

if __name__ == "__main__":
    main()
