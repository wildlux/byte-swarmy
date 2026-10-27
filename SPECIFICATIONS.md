# 📜 SPECIFICATIONS.md — System Technical Specifications

This document provides the comprehensive technical specifications for BYTE-SWARMY, detailing the architectural requirements, security boundaries, and functional capabilities.

## 1. System Overview
BYTE-SWARMY is an autonomous multi-agent system designed for enterprise-grade software development and passive USB reverse engineering, optimized for execution on resource-constrained Linux environments (e.g., 4GB RAM).

## 2. Technical Stack
- **Language**: Python 3.11+
- **Interface**: PyQt6 (GUI), CLI
- **Inference**: Ollama (Local LLMs: Phi-3, Mistral, etc.)
- **Persistence**: SQLite (Task Queue), JSON (Agent Memory)
- **Isolation**: Bubblewrap (Unprivileged Sandbox)
- **Monitoring**: Custom thermal/resource manager (Timestral)

## 3. Architectural Requirements

### 3.1 Execution Model
- **Sequential Loop**: The system operates on a single-threaded tick-based orchestrator to avoid race conditions and ensure stability.
- **Stateless Workers**: Workers are instantiated on-demand and their state is persisted to disk, allowing for crash recovery.
- **ACID Compliance**: The task queue must use a transactional database (SQLite) to ensure no tasks are lost during power failure or crashes.

### 3.2 Sandbox Specification
Every worker process must be encapsulated in a `bubblewrap` container with the following properties:
- **Filesystem**: Only `/usr`, `/etc`, and the project venv are mounted read-only. Only `project/` is mounted read-write.
- **Network**: Fully isolated network namespace (No internet/LAN access).
- **Namespaces**: Isolated PID, IPC, UTS, and User namespaces.
- **Privileges**: `--cap-drop ALL`, `no_new_privs`, and `--disable-userns`.

## 4. Security Specifications (The "Rule 0")
Security is enforced at the **Tool Layer**, not the Prompt Layer.

### 4.1 Command Validation
- **No-Shell Policy**: All bash commands are tokenized and executed with `shell=False`.
- **Whitelist/Blacklist**: Commands are validated against a strict set of allowed patterns (e.g., `gcc`, `python`, `git status`).
- **Path Confinement**: All file operations are restricted to the `project/` directory. Path traversal (`..`) and absolute paths are blocked.

### 4.2 Hardware Access (USB)
- **Passive Only**: Tools must only use read-only interfaces (`lsusb`, `tshark` via `usbmon`).
- **No Write**: Any attempt to send packets to the USB bus must be blocked at the tool level.

## 5. Functional Capabilities

### 5.1 Refactoring Suite
The system must provide high-level tools for code restructuring:
- **Symbol Renaming**: Global consistency across the project.
- **Method Extraction**: Automatic decomposition of complex functions.
- **Call Graph Analysis**: Impact analysis of changes.
- **Complexity Metrics**: Identification of technical debt via cyclomatic complexity.

### 5.2 Quality Assurance (QA)
- **Mandatory TDD**: Implementation tasks must follow: `Write Test` $\rightarrow$ `Run & Fail` $\rightarrow$ `Implement` $\rightarrow$ `Run & Pass`.
- **Audit Cycle**: Every piece of code must be reviewed by a separate `AuditWorker` before being committed.
- **Static Analysis**: Integration with `Bandit` for SAST (Static Application Security Testing).

## 6. Performance Constraints
- **Memory Ceiling**: Total system footprint must not exceed 4GB RAM.
- **Thermal Throttling**: The system must monitor CPU temperature and adjust the orchestrator tick rate or pause execution to prevent overheating.
- **Disk Quota**: The project directory should be limited to prevent disk saturation attacks.

## 7. Error Handling
- **Fail-Closed**: Any security violation or sandbox failure must result in immediate task termination.
- **Instructive Errors**: Tool errors must be explicit, explaining the reason for the failure and suggesting the safe alternative.
