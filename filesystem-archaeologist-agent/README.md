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

ℹ️ **Personal Computer Only**: This multi-agent system is intended to be used for single user personal computers.

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
   │  (@@)   │  │    (@@)    │  │    (@@) ─  │
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

**🚀 Reflection Agent (Phase 2 Approved)**
- **Current State**: Rule-based safety checks (4 hardcoded validations) - stable MVP baseline
- **Target State**: ✅ LLM-driven self-critique with 9 specialized tools + ReAct pattern (~65% agentic)
- **Evolution Strategy**: Autonomous Reflection with contextual reasoning and learning
- **Agentic Capabilities**: Tool orchestration + iterative improvement + performance learning

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
- [ ] Add session-based in-memory cache for ReAct reasoning LLM calls in ReActAgent base class (*currently low priority since it is not safely cacheable due to conversation state dynamics*)
- [ ] Add persistent cache for LLM classifications (TTL 24hr, stored in DB) to avoid redundant LLM calls across multiple CLI sessions, maximizing cost savings

**2. Autonomous Reflection**
- Current State: Rule-based safety checks (system paths, size thresholds)
- Target State: LLM self-critique and error detection

Changes Required:
- [x] Implement new information gathering tools (in `tools/reflection_tools.py`) to be used by the `ReflectionAgent`:
  - `check_file_dependencies(path)` - Analyze runtime/process dependencies ✓
  - `get_file_metadata(path)` - Extended attributes (ownership, versions, content type) ✓
  - `search_related_patterns(criteria)` - Query past classification decisions) ✓
- [x] Implement new action tools (in `tools/reflection_tools.py`) to be used by the `ReflectionAgent`:
  - `downgrade_confidence(path, level, reasoning)` - Apply confidence adjustments ✓
  - `add_safety_risk(path, description, severity)` - Flag novel risks ✓
  - `trigger_reclassification(path, context)` - Queue items for re-classification ✓
- [ ] Implement new learning tools (in `tools/reflection_tools.py`) to be used by the `ReflectionAgent`:
  - `query_reflection_history(path_pattern)` - Learn from past reflection decisions
  - `store_reflection_outcome(path, decision, accuracy_later_confirmed)` - Record reflection performance
  - `analyze_reflection_accuracy_metrics()` - Continuous improvement tracking
- [ ] Implement reflection prompt to use an LLM to do the self-critique
- [ ] Replace `ReflectionAgent` rules with LLM self-critique
- [ ] Add iteration: Reflection → Re-classification → Reflection² workflow
- [ ] Add safety mechanisms: max iteration limits (2-3 rounds), convergence criteria, escalation path
- [ ] Keep system path protection as non-negotiable validation (separate from reflection)

**3. Adaptive Orchestration**
- Current State: Fixed plan (Discovery → Classify → Reflect → Validate)
- Target State: LLM-generated adaptive plans

Changes Required:
- [ ] Implement dynamic planning in `OrchestratorAgent._create_plan()`
- [ ] Enable replanning on failures (*framework exists, needs to use an LLM*)
- [ ] Add plan optimisation based on past workflow performance

**4. Strategic Discovery**
- Current State: Prescriptive prompts (step-by-step instructions), ~~required `target_path`~~
- Target State: Goal-oriented autonomous exploration with optional `target_path` and hierarchical scanning

Changes Required:
- [x] Make `target_path` optional in CLI for autonomous directory selection
- [ ] Implement hierarchical scanning: baseline scan → priority determination → focused scanning
- [x] Add filesystem monitoring capabilities:
  - `get_disk_usage()` tool for tracking free space trends ✓
  - `get_recycle_bin_stats()` tool for monitoring garbage accumulation ✓
  - `check_directory_changes()` tool for detecting growth patterns ✓
- [ ] Implement proactive trigger system using regression analysis:
  - Monitor free space trends to predict when cleanup is needed
  - Track recycle bin size as feedback on cleanup effectiveness
  - Use simple regression or thresholds to determine scan timing
- [ ] Add background monitoring mode: `fs-archaeologist monitor --background`
- [ ] LLM integration for trigger decisions: "*Free space dropped 15% this month, suggesting cleanup of high-priority directories*"
- [ ] Add LLM-driven directory prioritization using past cleanup patterns and filesystem metadata
- [ ] Rewrite Scanner prompt to be strategic, not prescriptive
  ```python
  # Current (prescriptive)
  "1. Scan directory 2. Find large items (>50MB) 3. ..."

  # Target (strategic)
  "Goal: Find high-value cleanup opportunities
   Strategy is up to you. Consider efficiency vs thoroughness..."
  ```
- [ ] Add personal directory constants: `~/Desktop`, `~/Downloads`, `~/Documents`, `~/Pictures`, etc.
- [ ] Implement learning from directory success rates and user preferences
- [ ] Remove numbered steps from prompts

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
│   │   ├── reflection.py
│   │   ├── safety.py
│   │   ├── session.py
│   │   └── workflow.py
│   ├── tools/                     # Filesystem operations
│   │   └── filesystem.py          # Scan, analyse, git status
│   │   └── reflection_tools.py    # For autonomous reflection
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

# Autonomous scan (no target directory specified)
python -m agentic_fs_archaeologist scan

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

- 0.2.4 (18 Jan 2026) : Add tools to be used for autonomous reflection
- 0.2.3 (15 Jan 2026) : Make target_path optional in CLI for autonomous directory selection
- 0.2.2 (14 Jan 2026) : Add filesystem monitoring capabilities
- 0.2.1 (08 Jan 2026) : Add session-based in-memory cache for LLM classifications
- 0.2.0 (07 Jan 2026) : Implement classification using LLM
- 0.1.0 (04 Jan 2026) : Inital version of the Filesystem Archaeologist Agent
---
