# 🤖 AGENT.md — The BYTE-SWARMY Intelligence Layer

This document describes the cognitive architecture, behavioral constraints, and operational protocols of the agents within the BYTE-SWARMY system.

## 🧠 Cognitive Architecture

BYTE-SWARMY employs a hierarchical multi-agent system designed for high-precision software engineering and hardware analysis.

### 1. The Orchestrator (The Brain)
The Orchestrator is the central nervous system. It does not perform coding tasks but manages the lifecycle of all other agents.
- **Responsibility**: Task dispatching, resource monitoring (Thermal/CPU), and final quality gating.
- **Logic**: Uses a sequential tick-based loop to ensure predictability and stability on low-resource hardware.

### 2. The Planner (The Strategist)
Specialized in decomposition. It transforms vague user requests into a sequence of atomic, verifiable tasks.
- **Workflow**: `Generic Request` $\rightarrow$ `Analysis` $\rightarrow$ `Atomic Subtasks`.
- **Constraint**: Each subtask must be implementable in < 200 lines of code to prevent LLM drift.

### 3. The Worker (The Implementer)
The "hands" of the system. Workers are specialized coding agents that operate within a strict sandbox.
- **Specializations**:
    - `worker_coder`: Optimized for implementation and refactoring.
    - `worker_general`: Optimized for research and general tasks.
- **Operational Loop (ReAct)**: `Thought` $\rightarrow$ `Action (Tool Call)` $\rightarrow$ `Observation (Tool Result)` $\rightarrow$ `Thought`.
- **Hard Constraints**:
    - **TDD Mandatory**: Must write and fail a test before implementing a fix.
    - **Refactor-Loop**: Map $\rightarrow$ Analyze $\rightarrow$ Modify $\rightarrow$ Verify.
    - **Sandbox Bound**: Cannot access files outside the `project/` directory.

### 4. The Audit Worker (The Reviewer)
The final quality gate. This agent acts as a Senior Architect and Security Auditor.
- **Responsibility**: Cross-checking the Worker's output for security vulnerabilities, Clean Code violations, and logic errors.
- **Power**: Can `REJECT` a task, forcing the Worker to start over with specific feedback.
- **Criteria**: Focuses on Cognitive Load, DRY principle, and Security (no `eval`, no secrets).

## 🛠️ Memory Model

Agents use a tiered persistence system to maintain context without saturating the LLM window:

| Tier | Scope | Storage | Purpose |
| :--- | :--- | :--- | :--- |
| **Short-Term** | Current Task | RAM (Deque) | Immediate context of the last few turns. |
| **Working** | Current Session | JSON | History of the entire task execution. |
| **Long-Term** | Historical | JSON/DB | High-level summaries of past successes and failures. |

## 🛡️ Behavioral Guardrails

To ensure safety and quality, all agents must adhere to the following:
1. **Defense-in-Depth**: Never trust a prompt instruction to disable security.
2. **Fail-Closed**: If a tool returns an error, the agent must change approach, not repeat the command.
3. **Atomic Commits**: Every successfully audited task must be committed to Git immediately.
4. **Passive Hardware Access**: USB tools are strictly read-only. No write operations to hardware are permitted.
