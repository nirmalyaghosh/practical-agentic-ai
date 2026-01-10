# Filesystem Archaeologist Agent

A multi-agent system for intelligent filesystem cleanup using agentic AI patterns.

- **ReAct Pattern**: Iterative reasoning loops
- **Plan-Execute Pattern**: Workflow orchestration
- **Memory Pattern**: Learning from user feedback
- **HITL Pattern**: Human-in-the-loop approval
- **Safety Layer**: Deterministic validation

[![Stage](https://img.shields.io/badge/Stage-1%20(MVP)-green)]()
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)]()
[![Agentic](https://img.shields.io/badge/Agentic-Tool%20Orchestration%20-orange)]()

## Table of Contents

- [What Is This?](#what-is-this)
- [Architecture](#architecture)
- [MVP Scope & Limitations](#mvp-scope--limitations)
- [Evolution Roadmap](#-evolution-roadmap)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Example Usage](#example-usage)
- [Version History](#version-history)

---

## What Is This?

An intelligent filesystem cleanup agent that uses **LLM-driven tool orchestration** with pattern-based classification to identify and categorise cleanup opportunities.

---

## Architecture

```
┌───────────────────────────────────────────────┐
│ ORCHESTRATOR (Plan-Execute Framework)         │
│ Coordinates the 4-step workflow               │
└────────────────────┬──────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
   ┌─────────┐  ┌────────────┐  ┌────────────┐
   │ SCANNER │  │ CLASSIFIER │  │ REFLECTION │
   │  (@@)   │  │    (@@)    │  │  (Rules) ─ │
   │  ReAct  │  │ ReAct+Mem  │  │ Not Agentic│
   └─────────┘  └────────────┘  └────────────┘
        │            │            │
        └────────────┼────────────┘
                     ▼
              ┌───────────┐
              │ VALIDATOR │
              │ (Safety)  │
              │Non-Agentic│
              └───────────┘

**Note**: @@ indicates partially Agentic, these will be updated
```

### Agent Breakdown
(*along with current status*)

**✅ Scanner Agent**
- Uses LLM-driven ReAct pattern for **tool selection**
- Discovers cleanup opportunities through guided exploration
- Follows prescriptive prompts to: scan directories, identify large items (>1GB), flag common patterns
- **Currently partially Agentic**
  - What is agentic: LLM decides tool sequence and when to finish
  - What is not: Prompts provide step-by-step instructions; discovery strategy is scripted

**✅ Classifier Agent**
- Uses ReAct pattern for **tool orchestration + contextual reasoning** with Memory integration (currently uses SQLite)
- Categorises items (SAFE/LIKELY_SAFE/UNCERTAIN/UNSAFE) through contextual analysis of purpose, dependencies, and recoverability
- Analyses deletion safety using LLM instead of deterministic pattern matching
- Memory enables learning which patterns users approve/reject over time and influences classification decisions
- Falls back to pattern matching only when LLM cannot classify
- **Currently partially Agentic**
  - What is agentic: LLM decides which classification tools to call, when to call them, AND makes safety decisions through contextual reasoning
  - What is not: Fallback pattern matching (used only for error recovery)

**❌ Reflection Agent**
- **Currently rule-based**
  - Reason: the current implementation uses 4 hardcoded validation checks
  - Stage 2 will add LLM-based self-critique

**✅ Validator Agent**
- **Non-Agentic by Design**
- Deterministic safety checks
- System path protection, permission verification
- Intentionally rule-based for reliability

### ⚡ What Is Agentic?

**LLM-Driven (Agentic)**:
- ✓ Tool selection (ReAct loop: LLM decides which tool to call next)
- ✓ Iteration control (LLM decides when exploration is complete)
- ✓ Memory querying (LLM decides when to check past decisions)
- ✓ Classification decisions (contextual reasoning about deletion safety)

**Deterministic (Not Agentic)**:
- ✗ Fallback logic (pattern matching only when inference fails)
- ✗ Reflection rules (hardcoded safety checks)
- ✗ Orchestration plan (fixed workflow)
- ✗ Prompts are prescriptive (step-by-step instructions, not strategic goals)

👉 Refer to [Evolution Roadmap](#-evolution-roadmap) for planned implementation.

### Safety Guardrails

**Multi-layer protection**:
- **Reflection**: System path detection, size checks, directory protection, modification warnings
- **Validator**: System path blocking, permission verification, protected patterns (.git, .ssh)
- **HITL**: User approval required for all actions
- **MVP boundary**: No actual deletion (stops at approval)

---

## MVP Scope & Limitations

**What Has Been Implemented**:
- ✓ 2 LLM-driven agents (Scanner, Classifier) with ReAct reasoning loops
- ✓ Memory infrastructure: SQLite storage with pattern matching
- ✓ Multi-layer safety validation (Reflection + Validator + HITL)
- ✓ Learning capability: User decisions saved for future reference

**Intentional Boundaries**:
- ✗ No actual deletion (approval workflow only)
- ✗ Reflection uses rules (LLM-based self-critique in roadmap)
- ✗ Fixed orchestration (adaptive planning in roadmap)

**How Memory Works**:
- User approvals/rejections → saved to SQLite with path patterns
- Classifier can query past decisions during classification
- Learning effectiveness depends on LLM utilizing memory tool
- Enables improvement from human feedback over time

### 🚀 Evolution Roadmap

**1. Classification Using Language Model** ✅
- ~~Current State: Deterministic pattern matching (`if name == "node_modules"`)~~
- **New State**: Contextual reasoning about deletion safety

Changes Required:
- [x] Replace `_classify_item()` (*which currently uses pattern matching*) to use language model to classify as: SAFE/LIKELY_SAFE/UNCERTAIN/UNSAFE with reasoning
- [x] Convert classification from deterministic function to model-driven reasoning
- [x] Maintain pattern matching as fallback for error cases
- [x] Add session-based in-memory cache for LLM classifications (TTL 1hr) to avoid redundant LLM calls on repeated paths, thus reducing costs
- [] Add persistent cache for LLM classifications (TTL 24hr, stored in DB) to avoid redundant LLM calls across multiple CLI sessions, maximizing cost savings

**2. Autonomous Reflection**
- Current State: Rule-based safety checks (system paths, size thresholds)
- Target State: LLM self-critique and error detection

Changes Required:
- [ ] Implement reflection prompt to use an LLM to do the self-critique
- [ ] Replace `ReflectionAgent` rules with LLM self-critique
- [ ] Add iteration: Reflection → Re-classification if issues found
- [ ] Keep system path protection as non-negotiable validation (separate from reflection)

**3. Adaptive Orchestration**
- Current State: Fixed plan (Discovery → Classify → Reflect → Validate)
- Target State: LLM-generated adaptive plans

Changes Required:
- [ ] Implement dynamic planning in `OrchestratorAgent._create_plan()`
- [ ] Enable replanning on failures (*framework exists, needs to use an LLM*)
- [ ] Add plan optimisation based on past workflow performance

**4. Strategic Discovery**
- Current State: Prescriptive prompts (step-by-step instructions)
- Target State: Goal-oriented autonomous exploration

Changes Required:
- [ ] Rewrite Scanner prompt to be strategic, not prescriptive
- [ ] Remove numbered steps from prompts
- [ ] Let LLM develop its own discovery strategies

**5. Subjective Judgment**
- Current State: Binary decisions (safe/unsafe based on type)
- Target State: Context-aware subjective reasoning

Example Use Case: Photo deduplication
- Given N similar photos, which is the best?
- Learn user aesthetic preferences from past decisions
- Make recommendations: "Keep photo 3 - best captures emotional moment of birthday based on your preference for family photos over technical quality"

Changes Required:
- [ ] Multi-modal analysis integration (image, document content)
- [ ] Preference modeling from user feedback
- [ ] Subjective quality assessment beyond pattern matching
- [ ] Context-aware decision making (birthday photos vs landscape photos)

---

## Project Structure

```
filesystem-archaeologist-agent/
├── src/agentic_fs_archaeologist/
│   ├── agents/             # Agent implementations
│   │   ├── base.py                # Base agent class
│   │   ├── react_agent.py         # ReAct pattern base
│   │   ├── plan_execute_agent.py  # Plan-Execute pattern base
│   │   ├── scanner.py             # Discovery agent
│   │   ├── classifier.py          # Classification agent
│   │   ├── reflection.py          # Reflection agent (rule-based)
│   │   ├── validator.py           # Validator agent (safety)
│   │   ├── orchestrator.py        # Workflow coordinator
│   │   └── exceptions.py          # Agent exceptions
│   ├── memory/                    # Learning from user feedback
│   │   ├── store.py               # SQLite persistence
│   │   └── retrieval.py           # Pattern matching
│   ├── models/                    # Pydantic models (8 modules)
│   │   ├── agent.py
│   │   ├── base.py
│   │   ├── classification.py
│   │   ├── filesystem.py
│   │   ├── memory.py
│   │   ├── safety.py
│   │   ├── session.py
│   │   └── workflow.py
│   ├── tools/                     # Filesystem operations
│   │   └── filesystem.py          # Scan, analyze, git status
│   ├── hitl/                      # Human-in-the-loop
│   │   └── approval_gate.py       # CLI approval
│   ├── prompts/                   # Prompt management
│   │   ├── prompts.json           # Prompt templates
│   │   └── prompts.py             # Prompt loader
│   ├── safety/                    # Safety infrastructure
│   │   └── exceptions.py          # Safety exceptions
│   ├── utils/                     # Utilities
│   │   └── file_utils.py          # File operations
│   ├── app_logger.py              # Logging configuration
│   ├── cli.py                     # CLI interface
│   ├── config.py                  # Settings
│   └── exceptions.py              # Base exceptions
├── pyproject.toml                 # Project metadata
└── README.md
```

**Note**: MVP includes minimal implementations. Post-MVP roadmap includes expanded `hitl` (rich CLI), `memory` (vector embeddings), and `safety` (quarantine/recovery systems).


---

## Quick Start

### Installation

```bash
# Clone the Git repository, next
cd filesystem-archaeologist-agent

# Next, create a Python virtual environment
python -m venv .venv

# Next, activate the virtual environment:
- On Windows,
 .\.venv\Scripts\activate
- On macOS/Linux:
 source .venv/bin/activate

# Next, install dependencies
pip install -e .

# Next, set the OPENAI_API_KEY in the `filesystem-archaeologist-agent.env` file
```

### Basic Usage

```bash
# Scan a directory for cleanup opportunities
python -m agentic_fs_archaeologist scan ~/Downloads

# Run complete workflow (scan → classify → review → validate)
python -m agentic_fs_archaeologist cleanup ~/Downloads
```

---

## Example Usage

### Discover Cleanup Opportunities

```python
from agentic_fs_archaeologist.agents import ScannerAgent
from agentic_fs_archaeologist.models import AgentState

# Initialize scanner
scanner = ScannerAgent()

# Create state with target directory
state = AgentState(context={"target_path": "~/Downloads"})

# Execute discovery (LLM-driven ReAct loop)
result = await scanner.execute(state)

# View discoveries
for discovery in result.data["discoveries"]:
    print(f"Found: {discovery.path}")
    print(f"Reasoning: {discovery.reasoning}")
```

### Classify with Memory Learning

```python
from agentic_fs_archaeologist.agents import ClassifierAgent
from agentic_fs_archaeologist.memory import MemoryRetrieval

# Initialize classifier with memory
memory = MemoryRetrieval()
classifier = ClassifierAgent(memory)

# Classify items (learns from past decisions)
result = await classifier.execute(state)

# View classifications
for item in result.data["classifications"]:
    print(f"{item.path}: {item.category.value}")
    print(f"Confidence: {item.confidence.value}")
    print(f"Reasoning: {item.reasoning}")
    print(f"Based on {len(item.similar_decisions)} past decisions")
```

## Version History

- 0.2.1 (08 Jan 2026) : Add session-based in-memory cache for LLM classifications
- 0.2.0 (07 Jan 2026) : Implement classification using LLM
- 0.1.0 (04 Jan 2026) : Inital version of the Filesystem Archaeologist Agent
---
