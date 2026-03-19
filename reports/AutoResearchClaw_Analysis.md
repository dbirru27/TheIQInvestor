# AutoResearchClaw — Deep Analysis

**Repository:** https://github.com/aiming-lab/AutoResearchClaw  
**Version:** v0.3.0 (as of March 17, 2026)  
**License:** MIT  
**Authors:** Jiaqi Liu, Peng Xia, Siwei Han, Shi Qiu, Letian Zhang, Guiming Chen, Haoqin Tu, Xinyu Yang, Jiawei Zhou, Hongtu Zhu, Yun Li, Zeyu Zheng, Cihang Xie, Mingyu Ding, Huaxiu Yao  
**Organization:** aiming-lab  

---

## Executive Summary

AutoResearchClaw is a **fully autonomous, 23-stage research pipeline** that transforms a single natural-language research topic into a conference-ready academic paper — complete with real literature references, sandbox-executed experiments, statistical analysis, multi-agent peer review, and LaTeX output targeting NeurIPS, ICML, and ICLR. The system requires no human intervention (though it provides optional human-in-the-loop gates), can self-heal failed experiments, autonomously pivot when hypotheses fail, and learns from its own mistakes across runs via a self-evolution mechanism. It integrates with OpenClaw for conversational control, supports the Agent Client Protocol (ACP) for using any compatible coding agent as its LLM backend, and as of v0.3.0, features MetaClaw cross-run learning that improves pipeline robustness by 18.3%.

This is not a paper-writing assistant. It is a **complete autonomous research system** — from literature review to experiment execution to paper authoring — and represents one of the most ambitious implementations of end-to-end AI research automation to date.

---

## What Is It?

AutoResearchClaw is an open-source system that automates the entire academic research lifecycle: you provide a research topic in plain English, and the pipeline autonomously decomposes it into research questions, searches real academic databases (OpenAlex, Semantic Scholar, arXiv) for relevant literature, synthesizes findings, generates testable hypotheses through multi-agent debate, designs and runs experiments in a sandboxed environment (with hardware-aware GPU/MPS/CPU adaptation), analyzes results, makes autonomous proceed/refine/pivot decisions, writes a full academic paper (5,000–6,500 words), conducts multi-agent peer review, and exports everything as compile-ready LaTeX with verified BibTeX references. The whole process is one command: `researchclaw run --topic "Your idea" --auto-approve`.

---

## Main Contributions & Innovations

### 1. **23-Stage Pipeline with Decision Loops**
Unlike linear paper-generation tools, AutoResearchClaw implements a non-linear pipeline with autonomous PIVOT/REFINE decision points. Stage 15 (RESEARCH_DECISION) can roll the pipeline back to re-run experiments with tweaked parameters (REFINE → Stage 13) or regenerate hypotheses entirely (PIVOT → Stage 8), with automatic artifact versioning to preserve prior attempts.

### 2. **Multi-Agent Debate Architecture**
Three critical stages — hypothesis generation, result analysis, and peer review — use structured multi-perspective debate among LLM agents rather than single-shot generation. This mirrors real academic discourse where ideas are stress-tested from multiple angles.

### 3. **4-Layer Citation Verification**
A hallucination-elimination system that verifies every reference through four layers:
- **L1:** arXiv ID lookup (direct API query)
- **L2:** DOI resolution via CrossRef/DataCite
- **L3:** Title search on Semantic Scholar + arXiv with Jaccard similarity scoring
- **L4:** LLM-based relevance scoring

References classified as HALLUCINATED are automatically removed from the paper.

### 4. **Self-Evolution with Time-Decay**
Each pipeline run extracts lessons from failures, decision pivots, runtime warnings, and metric anomalies. These are stored in a JSONL evolution store with 30-day half-life exponential decay, ensuring recent lessons have higher weight while stale ones naturally expire after 90 days.

### 5. **MetaClaw Cross-Run Learning (v0.3.0)**
Integration with MetaClaw converts high-severity lessons into reusable "skills" that are injected as prompt overlays into all 23 stages of future runs. This creates a pipeline that genuinely learns from its own mistakes — reducing retry rates by 24.8% and refine cycles by 40% in controlled experiments.

### 6. **Hardware-Aware Experiment Execution**
Automatic detection of NVIDIA CUDA, Apple MPS, or CPU-only environments with adaptive code generation — the pipeline adjusts package selection, import statements, and experiment scale based on available hardware.

### 7. **Typed Adapter Protocol for OpenClaw Integration**
A clean `Protocol`-based adapter system (cron, message, memory, sessions, web_fetch, browser) that allows the pipeline to seamlessly consume OpenClaw capabilities when available, while falling back to recording stubs when running standalone.

### 8. **ACP (Agent Client Protocol) Support**
Can use any ACP-compatible coding agent (Claude Code, Codex CLI, Gemini CLI, OpenCode, Kimi CLI) as its LLM backend via a persistent session across all 23 stages — eliminating the need for API keys entirely.

---

## Architecture Overview

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AutoResearchClaw System                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │   CLI    │───▶│  RCConfig    │───▶│   Pipeline Runner        │  │
│  │ (cli.py) │    │ (config.py)  │    │   (runner.py)            │  │
│  └──────────┘    └──────────────┘    │                          │  │
│                                      │  ┌────────────────────┐  │  │
│  ┌──────────────────────────┐        │  │  Stage Executor    │  │  │
│  │   Adapter Bundle         │───────▶│  │  (executor.py)     │  │  │
│  │  ┌─────┐ ┌───────┐      │        │  │                    │  │  │
│  │  │Cron │ │Message│      │        │  │  23 Stage Handlers  │  │  │
│  │  └─────┘ └───────┘      │        │  │  (stages.py)       │  │  │
│  │  ┌──────┐ ┌────────┐    │        │  └────────────────────┘  │  │
│  │  │Memory│ │Sessions│    │        │                          │  │
│  │  └──────┘ └────────┘    │        │  ┌────────────────────┐  │  │
│  │  ┌────────┐ ┌────────┐  │        │  │  Decision Engine   │  │  │
│  │  │WebFetch│ │Browser │  │        │  │  PIVOT / REFINE    │  │  │
│  │  └────────┘ └────────┘  │        │  │  loop with version │  │  │
│  └──────────────────────────┘        │  └────────────────────┘  │  │
│                                      └──────────────────────────┘  │
│                                                                     │
│  ┌────────────────────┐  ┌───────────────┐  ┌──────────────────┐   │
│  │  Literature Engine │  │  Experiment   │  │  Evolution Store │   │
│  │  ┌──────────────┐  │  │  Sandbox      │  │  (JSONL + decay) │   │
│  │  │ OpenAlex     │  │  │  ┌─────────┐  │  └──────────────────┘   │
│  │  │ Sem.Scholar  │  │  │  │Hardware │  │                         │
│  │  │ arXiv        │  │  │  │Detect   │  │  ┌──────────────────┐   │
│  │  └──────────────┘  │  │  └─────────┘  │  │  MetaClaw Bridge │   │
│  │  ┌──────────────┐  │  │  ┌─────────┐  │  │  (skill inject)  │   │
│  │  │ Verify (4-L) │  │  │  │Code Gen │  │  └──────────────────┘   │
│  │  │ Novelty      │  │  │  │Self-Heal│  │                         │
│  │  │ Cache        │  │  │  └─────────┘  │  ┌──────────────────┐   │
│  │  └──────────────┘  │  └───────────────┘  │  Quality Engine  │   │
│  └────────────────────┘                      │  (template det.) │   │
│                                              └──────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    LLM Layer                                 │   │
│  │  ┌──────────────┐  ┌─────────┐  ┌────────────────────────┐  │   │
│  │  │OpenAI-compat │  │  ACP    │  │  MetaClaw Proxy        │  │   │
│  │  │(GPT-4o, etc.)│  │(Claude, │  │  (skill-injected LLM)  │  │   │
│  │  │              │  │ Codex…) │  │                        │  │   │
│  │  └──────────────┘  └─────────┘  └────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Pipeline Data Flow

```
User Input: "Research topic X"
       │
       ▼
┌──────────────────────── PHASE A: SCOPING ────────────────────────┐
│  [1] TOPIC_INIT ──▶ [2] PROBLEM_DECOMPOSE                       │
│       │                    │                                      │
│       ▼                    ▼                                      │
│  topic.json          problem_tree.json                           │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────── PHASE B: LITERATURE ─────────────────────────┐
│  [3] SEARCH_STRATEGY ──▶ [4] LITERATURE_COLLECT (OpenAlex/S2/arXiv)
│       │                         │                                 │
│       ▼                         ▼                                 │
│  queries.json              papers_raw.json                       │
│                                 │                                 │
│                    [5] LITERATURE_SCREEN ◀── [GATE: approve?]    │
│                                 │                                 │
│                    [6] KNOWLEDGE_EXTRACT                          │
│                                 │                                 │
│                         knowledge_cards.json                      │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────── PHASE C: SYNTHESIS ──────────────────────────┐
│  [7] SYNTHESIS ──▶ [8] HYPOTHESIS_GEN (multi-agent debate)       │
│       │                    │                                      │
│       ▼                    ▼                                      │
│  gaps.json           hypotheses.json                             │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────── PHASE D: DESIGN ─────────────────────────────┐
│  [9] EXPERIMENT_DESIGN ◀── [GATE] ──▶ [10] CODE_GENERATION      │
│       │                                      │                    │
│       ▼                                      ▼                    │
│  exp_plan.json                        experiment_code.py          │
│                               [11] RESOURCE_PLANNING              │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────── PHASE E: EXECUTION ──────────────────────────────┐
│  [12] EXPERIMENT_RUN ──▶ [13] ITERATIVE_REFINE (self-healing)    │
│       │                         │  ▲                              │
│       ▼                         │  │ (up to 10 rounds)            │
│  results.json ◀─────────────────┘  │                              │
│                                     │                              │
│  NaN/Inf detection ─── LLM repair ──┘                             │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────── PHASE F: ANALYSIS & DECISION ────────────────────┐
│  [14] RESULT_ANALYSIS (multi-agent) ──▶ [15] RESEARCH_DECISION   │
│       │                                        │                  │
│       ▼                                        ▼                  │
│  analysis.json                          ┌─────────────────┐      │
│                                         │ PROCEED ────────▶ Ph.G │
│                                         │ REFINE ─────────▶ [13] │
│                                         │ PIVOT ──────────▶ [8]  │
│                                         └─────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
       │ (PROCEED)
       ▼
┌──────────────── PHASE G: WRITING ────────────────────────────────┐
│  [16] PAPER_OUTLINE ──▶ [17] PAPER_DRAFT (5,000-6,500 words)    │
│       │                         │                                 │
│       ▼                         ▼                                 │
│  outline.json              paper_draft.md                        │
│                                 │                                 │
│  [18] PEER_REVIEW (evidence consistency) ──▶ [19] PAPER_REVISION │
│       │                                            │              │
│       ▼                                            ▼              │
│  reviews.md                                  paper_revised.md    │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────── PHASE H: FINALIZATION ───────────────────────────┐
│  [20] QUALITY_GATE ◀── [GATE] ──▶ [21] KNOWLEDGE_ARCHIVE        │
│       │                                  │                        │
│       ▼                                  ▼                        │
│  quality_report.json              kb/ (6 categories)             │
│                                                                   │
│  [22] EXPORT_PUBLISH (LaTeX) ──▶ [23] CITATION_VERIFY (4-layer)  │
│       │                                  │                        │
│       ▼                                  ▼                        │
│  paper.tex + refs.bib            verification_report.json        │
│                                                                   │
│  ──────▶ deliverables/  (compile-ready for Overleaf)             │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────── POST-PIPELINE ───────────────────────────────────┐
│  Evolution Store: extract_lessons() → lessons.jsonl              │
│  MetaClaw Bridge: lessons → arc-* skills → ~/.metaclaw/skills/   │
│  Pipeline Summary: pipeline_summary.json                          │
└──────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

| Component | Directory / File | Purpose |
|-----------|-----------------|---------|
| **CLI** | `researchclaw/cli.py` | Entry point (`researchclaw run/init/doctor/validate/report`) |
| **Config** | `researchclaw/config.py` | YAML config parsing with validation |
| **Pipeline Runner** | `researchclaw/pipeline/runner.py` | Orchestrates 23 stages, handles checkpoints, PIVOT/REFINE loops, deliverable packaging |
| **Stage Executor** | `researchclaw/pipeline/executor.py` | Dispatches individual stages |
| **Stage Definitions** | `researchclaw/pipeline/stages.py` | Stage enum, sequence, decision rollback maps |
| **Literature Engine** | `researchclaw/literature/` | OpenAlex, Semantic Scholar, arXiv clients; search, cache, verification, novelty detection |
| **Experiment Sandbox** | `researchclaw/experiment/` | Code generation, sandbox execution, self-healing |
| **Multi-Agent System** | `researchclaw/agents/` | CodeAgent, BenchmarkAgent, FigureAgent subsystems |
| **Knowledge Base** | `researchclaw/knowledge/` | Structured KB across 6 categories (markdown/obsidian backends) |
| **Evolution System** | `researchclaw/evolution.py` | Lesson extraction, JSONL store, time-decay, prompt overlay generation |
| **Quality Engine** | `researchclaw/quality.py` | Template/placeholder detection, anti-fabrication checks |
| **Hardware Detection** | `researchclaw/hardware.py` | GPU/MPS/CPU detection, PyTorch auto-install |
| **Adapters** | `researchclaw/adapters.py` | Typed Protocol interfaces for OpenClaw bridge capabilities |
| **MetaClaw Bridge** | `researchclaw/metaclaw_bridge/` | Cross-run skill injection, lesson-to-skill conversion |
| **Prompts** | `researchclaw/prompts.py` | LLM prompt templates for all stages |
| **Writing Guide** | `researchclaw/writing_guide.py` | Academic writing rules, anti-disclaimer enforcement |
| **Templates** | `researchclaw/templates/` | LaTeX templates (NeurIPS 2025, ICLR 2026, ICML 2026) |
| **Docker** | `researchclaw/docker/` | Docker sandbox with network policies |
| **Feedback** | `researchclaw/feedback/` | Multi-agent peer review system |

---

## Key Technical Details

### 1. The Evolution System — Self-Learning with Time Decay

The evolution system (`evolution.py`) is one of the most technically interesting components. It implements a complete learn-from-failure loop:

**Lesson extraction** automatically classifies errors into 6 categories using keyword matching:

```python
class LessonCategory(str, Enum):
    SYSTEM = "system"          # Environment / network / timeout
    EXPERIMENT = "experiment"  # Code validation, sandbox timeout
    WRITING = "writing"        # Paper quality issues
    ANALYSIS = "analysis"      # Weak analysis, missing comparison
    LITERATURE = "literature"  # Search / verification failures
    PIPELINE = "pipeline"      # Stage orchestration issues
```

**Time-weighted decay** ensures lessons naturally age out:

```python
HALF_LIFE_DAYS: float = 30.0
MAX_AGE_DAYS: float = 90.0

def _time_weight(timestamp_iso: str) -> float:
    """Compute exponential decay weight: weight = exp(-age_days * ln(2) / 30).
    Returns 0.0 for lessons older than 90 days."""
    ts = datetime.fromisoformat(timestamp_iso)
    age_days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
    if age_days > MAX_AGE_DAYS:
        return 0.0
    return math.exp(-age_days * math.log(2) / HALF_LIFE_DAYS)
```

**Why this matters:** This is a genuinely elegant approach to continual improvement. A 30-day half-life means a lesson from 30 days ago has 50% weight, from 60 days 25%, and it auto-expires at 90 days. The system learns from recent mistakes without being burdened by stale ones.

### 2. The PIVOT/REFINE Decision Loop

The pipeline runner implements recursive self-correction. When Stage 15 decides to REFINE or PIVOT:

```python
if (stage == Stage.RESEARCH_DECISION
    and result.status == StageStatus.DONE
    and result.decision in DECISION_ROLLBACK):
    
    pivot_count = _read_pivot_count(run_dir)
    
    # Safety: detect infinite refine loops with empty metrics
    if pivot_count > 0 and _consecutive_empty_metrics(run_dir, pivot_count):
        # Force PROCEED to break the loop
        ...
    elif pivot_count < MAX_DECISION_PIVOTS:
        rollback_target = DECISION_ROLLBACK[result.decision]
        _version_rollback_stages(run_dir, rollback_target, pivot_count + 1)
        
        # Recurse from rollback target
        pivot_results = execute_pipeline(
            run_dir=run_dir, from_stage=rollback_target, ...
        )
        results.extend(pivot_results)
        break  # Recursive call handles the rest
```

**Key design decisions:**
- **Artifact versioning** before rollback preserves all intermediate results
- **Pivot count limits** prevent infinite loops (MAX_DECISION_PIVOTS)
- **Empty metrics detection** catches degenerate refine cycles where experiments produce no useful data
- **Recursive pipeline execution** — the runner calls itself with a new starting stage

### 3. The 4-Layer Citation Verification Engine

The verification system (`literature/verify.py`) is designed to eliminate hallucinated references — one of the most common failure modes of LLM-generated papers:

```python
class VerifyStatus(str, Enum):
    VERIFIED = "verified"        # API confirms + title similarity ≥ 0.80
    SUSPICIOUS = "suspicious"    # Found but metadata diverges (0.50 ≤ sim < 0.80)
    HALLUCINATED = "hallucinated"  # Not found or sim < 0.50
    SKIPPED = "skipped"          # Cannot verify (no title, APIs unreachable)
```

**Title similarity** uses word-overlap Jaccard:

```python
def title_similarity(a: str, b: str) -> float:
    """Word-overlap Jaccard-ish similarity. Uses max(len) as denominator
    so short titles don't inflate the score."""
    def _words(t: str) -> set[str]:
        return set(re.sub(r"[^a-z0-9\s]", "", t.lower()).split()) - {""}
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))
```

**Design note:** Uses only `urllib` (zero extra pip dependencies) for all network I/O. This is a deliberate choice to minimize the dependency footprint.

### 4. Quality Detection — Anti-Fabrication Guard

The quality module (`quality.py`) detects template/placeholder content in LLM-generated text:

```python
_TEMPLATE_PATTERNS = [
    (r"(?i)\[INSERT\s+.*?\]", "Insert placeholder"),
    (r"(?i)\[TODO\s*:?\s*.*?\]", "TODO placeholder"),
    (r"(?i)lorem\s+ipsum", "Lorem ipsum filler"),
    (r"(?i)this\s+section\s+will\s+(describe|discuss|present)", "Future-tense placeholder"),
    (r"(?i)add\s+(your|the)\s+(content|text)\s+here", "Add content placeholder"),
    # ... 12 patterns total
]
```

The `check_strict_quality()` function gates the paper — if template_ratio exceeds 5%, the paper is flagged.

### 5. Typed Adapter System — Clean External Integration

```python
class CronAdapter(Protocol):
    def schedule_resume(self, run_id: str, stage_id: int, reason: str) -> str: ...

class MessageAdapter(Protocol):
    def notify(self, channel: str, subject: str, body: str) -> str: ...

# ... 6 typed protocols total

@dataclass
class AdapterBundle:
    cron: CronAdapter = field(default_factory=RecordingCronAdapter)
    message: MessageAdapter = field(default_factory=RecordingMessageAdapter)
    # ... all default to recording stubs
```

**Why this is clever:** The system runs identically standalone or within OpenClaw. Recording adapters capture what *would* have been called, enabling testing and replay. When OpenClaw is present, it injects real adapters — zero code changes needed.

### 6. Hardware Detection — Adaptive Experiment Generation

```python
def detect_hardware() -> HardwareProfile:
    """Detection order: NVIDIA → Apple MPS → CPU-only"""
    profile = _detect_nvidia()  # nvidia-smi query
    if profile is not None:
        return profile
    profile = _detect_mps()     # platform.machine() == "arm64"
    if profile is not None:
        return profile
    return HardwareProfile(has_gpu=False, gpu_type="cpu", tier="cpu_only", ...)
```

The `HardwareProfile` is passed to code generation stages, which adapt imports (`torch.cuda` vs `torch.mps` vs numpy-only), model sizes, and batch sizes accordingly.

---

## Significance to AI Scientists

### What Problems Does It Solve?

1. **The "Last Mile" Problem in AI Research Automation:** Previous systems (AI Scientist, AutoResearch) demonstrated that LLMs can draft papers, but they struggle with the full lifecycle — especially experiment execution, iterative refinement, and citation integrity. AutoResearchClaw addresses all of these.

2. **Hallucinated References:** LLMs routinely fabricate citations. The 4-layer verification engine is a production-grade solution that checks against real APIs (arXiv, CrossRef, DataCite, Semantic Scholar) and automatically removes unverifiable references.

3. **Experiment Reliability:** LLM-generated code often fails. The sandbox execution system with AST validation, NaN/Inf fast-fail, self-healing repair (up to 10 rounds), and partial result capture makes experiments dramatically more reliable.

4. **Research Decision-Making:** The autonomous PIVOT/REFINE mechanism means the system can respond to negative results like a real researcher would — adjusting parameters, trying new approaches, or changing direction entirely.

5. **Cross-Run Learning:** The evolution system + MetaClaw bridge mean the pipeline genuinely improves over time, unlike one-shot systems that repeat the same mistakes.

### How Does It Advance the Field?

- **From "paper writing" to "research conducting":** This is a paradigm shift from tools that help *write* papers to systems that *do research* and happen to produce papers as output.
- **Multi-agent reasoning at scale:** Three distinct multi-agent debate subsystems (hypothesis generation, result analysis, peer review) demonstrate that multi-agent architectures can handle complex, multi-step reasoning tasks.
- **Practical self-improvement:** The evolution system with time-decay is a pragmatic, production-ready approach to continual learning that avoids the complexity of full meta-learning while delivering measurable improvements (+18.3% robustness).
- **Adapter-based integration architecture:** The typed Protocol adapter system is a reusable pattern for building AI tools that work both standalone and within larger agent ecosystems.

### Comparison to Prior Work

The README explicitly acknowledges three predecessors:

| System | Scope | Key Difference from AutoResearchClaw |
|--------|-------|--------------------------------------|
| **AI Scientist** (Sakana AI) | Idea → paper | Pioneered the concept; less emphasis on citation verification and experiment self-healing |
| **AutoResearch** (Karpathy) | End-to-end automation | Broader vision; AutoResearchClaw offers more granular pipeline control and decision loops |
| **FARS** (Analemma) | Fully automated research | Industry system; AutoResearchClaw is open-source with OpenClaw integration |

AutoResearchClaw differentiates through: (a) its 23-stage granularity with decision loops, (b) 4-layer citation verification, (c) cross-run learning via MetaClaw, and (d) the adapter architecture enabling multiple deployment modes.

### Potential Applications & Research Directions

1. **Rapid Literature Survey Generation** — Even without experiments, the literature discovery pipeline (Phases A-C) is valuable as a standalone tool for systematic reviews.
2. **Research Hypothesis Generation** — The multi-agent debate mechanism for hypothesis generation could be extracted and applied to brainstorming and ideation tools.
3. **Automated Replication Studies** — Given a published paper's methodology, the pipeline could potentially reproduce or validate results.
4. **Education** — Students could use it to understand the research process by observing an AI execute each stage.
5. **Meta-Research** — Studying the pipeline's decisions (when it pivots, what kinds of hypotheses it generates) could yield insights about research methodology itself.

---

## Limitations & Open Questions

### Known Limitations

1. **LLM Quality Ceiling:** The output quality is bounded by the underlying LLM. A GPT-4o-powered run will produce different quality than a GPT-4o-mini run. The system doesn't solve the fundamental problem of LLM reasoning limitations.

2. **Experiment Scope:** Sandbox experiments are constrained to what can run in a Python subprocess within a time budget (default 300s). This excludes:
   - Large-scale distributed training
   - Multi-day experiments
   - Hardware-specific optimizations requiring custom CUDA kernels

3. **No Real Peer Review:** While multi-agent "peer review" catches some issues, it is fundamentally different from domain-expert human review. The system may miss subtle methodological flaws that an expert would catch.

4. **Citation Verification Gaps:** The 4-layer system is impressive but not perfect:
   - Very new papers may not yet be indexed
   - Papers behind paywalls may not have full metadata
   - Title similarity can be fooled by papers with very common titles

5. **Single-Paper Scope:** The system produces one paper per run. It doesn't manage a research program — no multi-paper coherence, no long-term research agenda.

6. **Evaluation Challenge:** How do you evaluate whether an autonomously generated paper is "good"? The 7-dimensional review scoring and NeurIPS checklist are proxies, but ground truth requires human expert evaluation.

### Open Questions

- **Ethical implications:** If AI systems can produce conference-quality papers autonomously, what does this mean for academic publishing, peer review, and the research enterprise?
- **Novelty vs. synthesis:** Can an LLM-driven pipeline produce genuinely novel insights, or does it primarily synthesize existing knowledge?
- **Scalability:** How does the pipeline perform across different domains (biology, physics, social sciences) vs. its apparent home turf (ML/NLP)?
- **Adversarial robustness:** Can the quality gates be gamed? Could someone use it to generate plausible-looking but fundamentally flawed papers?
- **Resource costs:** A full pipeline run involves dozens of LLM calls across 23 stages — what are the actual API costs and runtimes?

---

## How to Get Started

### Prerequisites
- Python 3.11+
- An LLM API key (OpenAI, OpenRouter, DeepSeek) or an ACP-compatible agent (Claude Code, Codex CLI, etc.)

### Quick-Start (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/aiming-lab/AutoResearchClaw.git
cd AutoResearchClaw

# 2. Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install
pip install -e .

# 4. Initialize config (interactive provider selection)
researchclaw init

# 5. Set your API key
export OPENAI_API_KEY="sk-..."

# 6. Check environment health
researchclaw doctor

# 7. Run your first paper!
researchclaw run --config config.arc.yaml \
  --topic "Evaluating chain-of-thought prompting strategies for mathematical reasoning" \
  --auto-approve
```

### Output Structure
```
artifacts/rc-YYYYMMDD-HHMMSS-<hash>/
├── deliverables/          # Everything you need, compile-ready
│   ├── paper_final.md     # Full paper (Markdown)
│   ├── paper.tex          # LaTeX (NeurIPS/ICML/ICLR template)
│   ├── references.bib     # Verified BibTeX
│   └── charts/            # Auto-generated figures
├── stage-01/              # Per-stage artifacts
├── stage-02/
├── ...
├── stage-23/
│   └── verification_report.json
├── evolution/
│   └── lessons.jsonl      # Extracted lessons
├── checkpoint.json        # Resume point
├── heartbeat.json         # Watchdog heartbeat
└── pipeline_summary.json  # Run statistics
```

### Key CLI Commands

| Command | Purpose |
|---------|---------|
| `researchclaw run` | Execute the full 23-stage pipeline |
| `researchclaw init` | Create config from template (interactive) |
| `researchclaw doctor` | Check environment health |
| `researchclaw validate` | Validate config file |
| `researchclaw report --run-dir <path>` | Generate human-readable run report |

### Key Run Flags

| Flag | Effect |
|------|--------|
| `--auto-approve` | Skip human approval gates (stages 5, 9, 20) |
| `--resume` | Resume from last checkpoint |
| `--from-stage STAGE_NAME` | Start from a specific stage |
| `--skip-preflight` | Skip LLM connectivity check |
| `--skip-noncritical-stage` | Continue on non-critical stage failures |

### Using with OpenClaw (Easiest Path)

If you already use OpenClaw, simply share the repo URL in chat:

```
You: "Research the effectiveness of retrieval-augmented generation for code documentation"
OpenClaw: [clones repo, installs, configures, runs pipeline, returns paper]
```

---

## References & Links

- **GitHub Repository:** https://github.com/aiming-lab/AutoResearchClaw
- **MetaClaw (Cross-Run Learning):** https://github.com/aiming-lab/MetaClaw
- **OpenClaw (AI Assistant Platform):** https://github.com/openclaw/openclaw
- **ACP Protocol (acpx):** https://github.com/openclaw/acpx
- **Discord Community:** https://discord.gg/u4ksqW5P
- **Integration Guide:** https://github.com/aiming-lab/AutoResearchClaw/blob/main/docs/integration-guide.md
- **Tester Guide:** https://github.com/aiming-lab/AutoResearchClaw/blob/main/docs/TESTER_GUIDE.md

### Acknowledged Inspirations
- [AI Scientist](https://github.com/SakanaAI/AI-Scientist) (Sakana AI) — Automated research pioneer
- [AutoResearch](https://github.com/karpathy/autoresearch) (Andrej Karpathy) — End-to-end research automation
- [FARS](https://analemma.ai/blog/introducing-fars/) (Analemma) — Fully Automated Research System

### Citation
```bibtex
@misc{liu2026autoresearchclaw,
  author       = {Liu, Jiaqi and Xia, Peng and Han, Siwei and Qiu, Shi and Zhang, Letian 
                  and Chen, Guiming and Tu, Haoqin and Yang, Xinyu and Zhou, Jiawei 
                  and Zhu, Hongtu and Li, Yun and Zheng, Zeyu and Xie, Cihang 
                  and Ding, Mingyu and Yao, Huaxiu},
  title        = {AutoResearchClaw: Fully Autonomous Research from Idea to Paper},
  year         = {2026},
  organization = {GitHub},
  url          = {https://github.com/aiming-lab/AutoResearchClaw},
}
```

---

*Report generated on March 17, 2026 by Danswiz 🦉 | AI Assistant*  
*For Dagnachew Birru — Quantiphi*
