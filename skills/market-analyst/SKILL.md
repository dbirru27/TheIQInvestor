# Skill: Market Analyst (Level 2)

## Description
Institutional-grade stock analysis. Focuses on data density, liquidity, and specific structural catalysts. No fluff.

## Usage
Trigger this skill when the user asks for a "deep dive", "analysis", or "hunter scan".

## Procedure

1.  **Fundamental & Structural Data:**
    *   **Valuation:** Forward P/E vs. 5Y Average. PEG Ratio.
    *   **Short Data:** Short Interest % of Float. Days to Cover. (Is there squeeze fuel?)
    *   **Dates:** Next Earnings Date (Confirmed/Est). Ex-Div Date.

2.  **Technicals & Volume (The "Truth"):**
    *   **RVOL (Relative Volume):** Is current volume > 1.5x of 10-day average? (Institutional footprints).
    *   **Structure:** Price vs VWAP (Volume Weighted Avg Price).
    *   **Support/Resistance:** Specific price levels (e.g., "$410.50 pivot").

3.  **Breadth (Context):**
    *   If analyzing a sector, check: Are >50% of components above their 50d MA? (Is the move real?)

## Output Format

```markdown
**Terminal Report: [TICKER]**
**Price:** $[Price] | **RVOL:** [x]x | **ATR:** $[x]

### ⚙️ Structure & Flow
*   **Volume:** [Analysis of accumulation/distribution]
*   **Shorts:** [Short %] float | [x] Days to Cover
*   **Breadth:** [Sector] is [Weak/Strong] (e.g., "70% of stocks > 50d MA")

### 📅 Hard Catalysts
*   **Earnings:** [Date] ([Days away])
*   **Divs:** [Date] ([Yield])

### 📐 Technical Levels
*   **Pivot:** $[Price]
*   **Support:** $[Price] (200d MA) / $[Price] (Recent Low)
*   **Resistance:** $[Price]

### 🎯 Thesis Verdict
[Direct synthesis of the data. No hedging.]
```
