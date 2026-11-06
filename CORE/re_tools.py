#!/usr/bin/env python3
"""
CORE/re_tools.py — Reverse Engineering tools for byte-swarmy worker

Integrates:
  - Ghidra (headless decompilation via subprocess + analyzeHeadless)
  - radare2 (via r2pipe Python binding)
  - Wireshark/tshark (via pyshark or subprocess)
  - capstone (pure Python disassembler)
  - binutils (file, readelf, nm, strings, objdump)

Tools exposed (call_re_tool):
  - binary_info(path)                         -> file type, arch, symbols, hash
  - extract_strings(path, min_len=4)          -> printable strings
  - disassemble_radare2(path, address, count) -> r2 disassembly
  - disassemble_capstone(path, arch, mode)    -> capstone disassembly
  - decompile_ghidra(path, function_name)     -> Ghidra C pseudocode
  - list_functions_radare2(path)              -> r2 function list
  - analyze_pcap(pcap_path, filter, count)    -> packet capture analysis
  - protocol_stats_pcap(pcap_path)            -> protocol hierarchy stats

Uso diretto:
  from CORE.re_tools import call_re_tool, check_re_environment

  env = check_re_environment()
  print(env)

  result = call_re_tool("binary_info", ["/bin/ls"])
  print(result)

Integrazione nel worker:
  Aggiungi in CORE/tools.py:
    from CORE.re_tools import RE_TOOLS, call_re_tool
    # poi registra RE_TOOLS nel worker tool registry

Autore: byte-swarmy RE module
Versione: 1.0
"""
import subprocess
import shutil
import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Optional, Union, List, Dict
import logging
_OUT = sys.stdout

log = logging.getLogger("byte-swarmy.re_tools")


# === ANSI Colors (for CLI output) ===
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

# === OPTIONAL IMPORTS (degrade gracefully) ===

try:
    import r2pipe
    HAS_R2 = True
except ImportError:
    HAS_R2 = False

try:
    import capstone
    HAS_CAPSTONE = True
except ImportError:
    HAS_CAPSTONE = False

try:
    import pyshark
    HAS_PYSHARK = True
except ImportError:
    HAS_PYSHARK = False


# === UTILITY ===

def _check_tool(name: str) -> bool:
    """True se il tool è nel PATH."""
    return shutil.which(name) is not None


def _file_exists(path: str) -> bool:
    if not Path(path).exists():
        log.error(f"ERROR: file not found: {path}")
        return False
    return True


# === BINARY ANALYSIS (binutils) ===

def binary_info(path: str) -> str:
    """Basic info about a binary: file type, ELF header, symbols, hash.

    Uses: file, readelf, nm, sha256sum (binutils + coreutils)
    """
    if not _file_exists(path):
        return f"ERROR: file not found: {path}"

    parts = []

    if _check_tool("file"):
        r = subprocess.run(["file", path], capture_output=True, text=True, timeout=10)
        parts.append(f"=== File type ===\n{r.stdout.strip()}")

    if _check_tool("readelf"):
        r = subprocess.run(["readelf", "-h", path], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            parts.append(f"=== ELF header ===\n{r.stdout.strip()}")

    if _check_tool("nm"):
        r = subprocess.run(["nm", path], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            lines = r.stdout.strip().split("\n")
            parts.append(f"=== Symbols ({len(lines)} total, first 30) ===\n" + "\n".join(lines[:30]))

    if _check_tool("sha256sum"):
        r = subprocess.run(["sha256sum", path], capture_output=True, text=True, timeout=10)
        parts.append(f"=== Hash ===\n{r.stdout.strip()}")

    if _check_tool("stat"):
        r = subprocess.run(["stat", path], capture_output=True, text=True, timeout=10)
        parts.append(f"=== Stat ===\n{r.stdout.strip()}")

    return "\n\n".join(parts) if parts else "ERROR: no tools available (install binutils: sudo apt install binutils file coreutils)"


def extract_strings(path: str, min_len: int = 4, max_strings: int = 200) -> str:
    """Extract printable strings from binary.

    Uses `strings` if available, fallback to pure Python.
    """
    if not _file_exists(path):
        return f"ERROR: file not found: {path}"

    if _check_tool("strings"):
        r = subprocess.run(
            ["strings", "-n", str(min_len), path],
            capture_output=True, text=True, timeout=60
        )
        all_strings = r.stdout.split("\n")
        shown = all_strings[:max_strings]
        return f"=== Strings (total {len(all_strings)}, showing {len(shown)}) ===\n\n" + "\n".join(shown)

    # Pure Python fallback
    with open(path, "rb") as f:
        data = f.read()

    result = []
    current = bytearray()
    for byte in data:
        if 32 <= byte <= 126:  # printable ASCII
            current.append(byte)
        else:
            if len(current) >= min_len:
                result.append(current.decode("ascii"))
                if len(result) >= max_strings:
                    break
            current = bytearray()

    return f"=== Strings (pure Python fallback, {len(result)} found) ===\n\n" + "\n".join(result)


# === DISASSEMBLY ===

def disassemble_radare2(path: str, address: Optional[str] = None, count: int = 50) -> str:
    """Disassemble using radare2 via r2pipe.

    Args:
        path: binary path
        address: hex address (e.g. "0x401000"). If None, starts at entry point.
        count: number of instructions to show
    """
    if not HAS_R2:
        return "ERROR: r2pipe not installed. Run: pip install r2pipe"
    if not _check_tool("r2"):
        return "ERROR: radare2 binary not found. Install: sudo apt install radare2"
    if not _file_exists(path):
        return f"ERROR: file not found: {path}"

    try:
        r2 = r2pipe.open(str(path))
        r2.cmd("aaa")  # analyze all

        if address:
            r2.cmd(f"s {address}")
        else:
            r2.cmd("s entry0")  # entry point

        disasm = r2.cmd(f"pd {count}")
        funcs = r2.cmd("aflj")  # functions as JSON

        r2.quit()

        # Parse functions count
        try:
            func_list = json.loads(funcs) if funcs else []
            func_summary = f"Functions found: {len(func_list)}\n"
            if func_list:
                func_summary += "First 10: " + ", ".join(f["name"] for f in func_list[:10])
        except Exception:
            func_summary = "Functions list (raw):\n" + funcs[:500]

        return f"=== {func_summary} ===\n\n=== Disassembly ({count} instructions from {address or 'entry0'}) ===\n\n{disasm}"
    except Exception as e:
        return f"ERROR radare2: {e}"


def disassemble_capstone(path: str, arch: str = "x86", mode: str = "64",
                          offset: int = 0, count: int = 50) -> str:
    """Disassemble using capstone (pure Python, no external tool needed).

    Args:
        path: binary path
        arch: x86, arm, arm64, mips
        mode: 32, 64, arm, thumb
        offset: byte offset in file to start disassembly
        count: number of instructions
    """
    if not HAS_CAPSTONE:
        return "ERROR: capstone not installed. Run: pip install capstone"
    if not _file_exists(path):
        return f"ERROR: file not found: {path}"

    arch_map = {
        "x86": capstone.CS_ARCH_X86,
        "arm": capstone.CS_ARCH_ARM,
        "arm64": capstone.CS_ARCH_ARM64,
        "mips": capstone.CS_ARCH_MIPS,
    }
    mode_map = {
        "32": capstone.CS_MODE_32,
        "64": capstone.CS_MODE_64,
        "arm": capstone.CS_MODE_ARM,
        "thumb": capstone.CS_MODE_THUMB,
    }

    if arch not in arch_map:
        return f"ERROR: unsupported arch '{arch}'. Supported: {list(arch_map.keys())}"
    if mode not in mode_map:
        return f"ERROR: unsupported mode '{mode}'. Supported: {list(mode_map.keys())}"

    try:
        with open(path, "rb") as f:
            f.seek(offset)
            code = f.read(count * 16)  # ~16 bytes per instruction

        md = capstone.Cs(arch_map[arch], mode_map[mode])
        lines = []
        for ins in md.disasm(code, offset):
            lines.append(f"0x{ins.address:x}:\t{ins.mnemonic}\t{ins.op_str}")
            if len(lines) >= count:
                break

        if not lines:
            return f"No valid instructions found at offset {offset} (arch={arch}, mode={mode})"

        return f"=== Disassembly ({len(lines)} instructions, {arch} {mode}) ===\n\n" + "\n".join(lines)
    except Exception as e:
        return f"ERROR capstone: {e}"


def list_functions_radare2(path: str) -> str:
    """List functions found in binary using radare2."""
    if not HAS_R2:
        return "ERROR: r2pipe not installed. Run: pip install r2pipe"
    if not _check_tool("r2"):
        return "ERROR: radare2 binary not found. Install: sudo apt install radare2"
    if not _file_exists(path):
        return f"ERROR: file not found: {path}"

    try:
        r2 = r2pipe.open(str(path))
        r2.cmd("aaa")
        funcs = r2.cmd("afl")
        r2.quit()
        return f"=== Functions in {path} ===\n\n{funcs}"
    except Exception as e:
        return f"ERROR: {e}"


# === DECOMPILATION (Ghidra) ===

def decompile_ghidra(path: str, function_name: Optional[str] = None,
                     timeout: int = 120) -> str:
    """Decompile binary to C pseudocode using Ghidra headless mode.

    Args:
        path: binary path
        function_name: if specified, decompile only this function. None = all (limited to 30).
        timeout: seconds before killing Ghidra
    """
    if not _check_tool("analyzeHeadless"):
        return ("ERROR: Ghidra not installed.\n"
                "Download from https://ghidra-sre.org/\n"
                "Extract and add 'analyzeHeadless' to PATH:\n"
                "  export PATH=$PATH:/opt/ghidra/support")
    if not _file_exists(path):
        return f"ERROR: file not found: {path}"

    proj_dir = tempfile.mkdtemp(prefix="ghidra_proj_")
    proj_name = "byte_swarm_re"

    # Write Ghidra script
    script_path = Path(proj_dir) / "decompile.py"
    if function_name:
        script_content = f"""
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

decomp = DecompInterface()
decomp.openProgram(currentProgram)
monitor = ConsoleTaskMonitor()

fm = currentProgram.getFunctionManager()
for func in fm.getFunctions(True):
    if func.getName() == "{function_name}":
        result = decomp.decompileFunction(func, 60, monitor)
        if result.decompileCompleted():
            print("===DECOMPILE_START===")
            print(result.getDecompiledFunction().getC())
            print("===DECOMPILE_END===")
        else:
            print("ERROR: decompile failed for " + func.getName())
        break
else:
    print("ERROR: function '{function_name}' not found")
"""
    else:
        script_content = """
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

decomp = DecompInterface()
decomp.openProgram(currentProgram)
monitor = ConsoleTaskMonitor()

fm = currentProgram.getFunctionManager()
count = 0
for func in fm.getFunctions(True):
    result = decomp.decompileFunction(func, 60, monitor)
    if result.decompileCompleted():
        print("===DECOMPILE_START===")
        print("=== " + func.getName() + " ===")
        print(result.getDecompiledFunction().getC())
        print("===DECOMPILE_END===")
        count += 1
        if count >= 30:
            print("... truncated, more functions available")
            break

print("Decompiled " + str(count) + " functions")
"""

    script_path.write_text(script_content)

    try:
        cmd = [
            "analyzeHeadless",
            proj_dir, proj_name,
            "-import", str(path),
            "-overwrite",
            "-postScript", "decompile.py",
            "-scriptPath", proj_dir,
            "-deleteProject",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        output = r.stdout
        # Extract decompilation sections
        if "===DECOMPILE_START===" in output:
            parts = output.split("===DECOMPILE_START===")
            result_parts = []
            for part in parts[1:]:  # skip first (pre-first-marker)
                if "===DECOMPILE_END===" in part:
                    decomp_text = part.split("===DECOMPILE_END===")[0].strip()
                    result_parts.append(decomp_text)
            return f"=== Ghidra Decompilation ({len(result_parts)} functions) ===\n\n" + "\n\n---\n\n".join(result_parts)

        # No decompilation markers — show tail of output
        return f"=== Ghidra output (no decompilation markers found) ===\n\n{output[-2000:]}\n\n--- stderr ---\n{r.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        return f"ERROR: Ghidra timeout ({timeout}s). Binary might be too large."
    except Exception as e:
        return f"ERROR Ghidra: {e}"
    finally:
        # Cleanup
        try:
            shutil.rmtree(proj_dir, ignore_errors=True)
        except Exception:
            pass


# === PCAP ANALYSIS (Wireshark/tshark) ===

def analyze_pcap(pcap_path: str, display_filter: Optional[str] = None,
                  packet_count: int = 20) -> str:
    """Analyze packet capture (pcap/pcapng).

    Args:
        pcap_path: .pcap or .pcapng file
        display_filter: Wireshark display filter (e.g. "tcp.port == 80")
        packet_count: max packets to show
    """
    if not _file_exists(pcap_path):
        return f"ERROR: file not found: {pcap_path}"

    if HAS_PYSHARK and _check_tool("tshark"):
        try:
            cap = pyshark.FileCapture(pcap_path, display_filter=display_filter)
            lines = []
            for i, pkt in enumerate(cap):
                if i >= packet_count:
                    break
                try:
                    proto = pkt.transport_layer if hasattr(pkt, "transport_layer") else "?"
                    src = pkt.ip.src if hasattr(pkt, "ip") else "?"
                    dst = pkt.ip.dst if hasattr(pkt, "ip") else "?"
                    if proto and proto != "?":
                        sport = pkt[pkt.transport_layer].srcport if hasattr(pkt, pkt.transport_layer) else "?"
                        dport = pkt[pkt.transport_layer].dstport if hasattr(pkt, pkt.transport_layer) else "?"
                        lines.append(f"#{i+1} {proto} {src}:{sport} -> {dst}:{dport}")
                    else:
                        lines.append(f"#{i+1} {pkt.highest_layer} {src} -> {dst}")
                except Exception:
                    lines.append(f"#{i+1} (parse error)")
            cap.close()
            return f"=== First {len(lines)} packets ===\n\n" + "\n".join(lines)
        except Exception as e:
            return f"ERROR pyshark: {e}\n(falling back to tshark CLI if available)"

    # Fallback: tshark CLI
    if _check_tool("tshark"):
        cmd = ["tshark", "-r", pcap_path, "-c", str(packet_count)]
        if display_filter:
            cmd.extend(["-Y", display_filter])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return f"=== tshark output (first {packet_count} packets) ===\n\n{r.stdout}"
        except Exception as e:
            return f"ERROR tshark: {e}"

    return ("ERROR: neither pyshark nor tshark available.\n"
            "Install: sudo apt install tshark && pip install pyshark")


def protocol_stats_pcap(pcap_path: str) -> str:
    """Protocol hierarchy statistics from pcap."""
    if not _check_tool("tshark"):
        return "ERROR: tshark not installed. Run: sudo apt install tshark"
    if not _file_exists(pcap_path):
        return f"ERROR: file not found: {pcap_path}"

    try:
        r = subprocess.run(
            ["tshark", "-r", pcap_path, "-q", "io,phs"],
            capture_output=True, text=True, timeout=60
        )
        return f"=== Protocol hierarchy stats ===\n\n{r.stdout}"
    except Exception as e:
        return f"ERROR: {e}"


def pcap_conversations(pcap_path: str) -> str:
    """List TCP/UDP conversations in pcap."""
    if not _check_tool("tshark"):
        return "ERROR: tshark not installed"
    if not _file_exists(pcap_path):
        return f"ERROR: file not found: {pcap_path}"

    try:
        r = subprocess.run(
            ["tshark", "-r", pcap_path, "-q", "conv,tcp"],
            capture_output=True, text=True, timeout=60
        )
        udp_r = subprocess.run(
            ["tshark", "-r", pcap_path, "-q", "conv,udp"],
            capture_output=True, text=True, timeout=60
        )
        return f"=== TCP conversations ===\n{r.stdout}\n\n=== UDP conversations ===\n{udp_r.stdout}"
    except Exception as e:
        return f"ERROR: {e}"


# === TOOL REGISTRY ===

RE_TOOLS: Dict[str, Dict] = {
    "binary_info": {
        "fn": binary_info,
        "signature": "binary_info(path) -> str",
        "desc": "File type, ELF header, symbols, hash. Uses binutils.",
        "deps": "binutils, file, coreutils",
    },
    "extract_strings": {
        "fn": extract_strings,
        "signature": "extract_strings(path, min_len=4, max_strings=200) -> str",
        "desc": "Printable strings from binary (strings command or Python fallback)",
        "deps": "binutils (optional, has fallback)",
    },
    "disassemble_radare2": {
        "fn": disassemble_radare2,
        "signature": "disassemble_radare2(path, address=None, count=50) -> str",
        "desc": "Disassemble binary using radare2 (r2pipe). address ex: '0x401000'",
        "deps": "radare2, r2pipe (pip)",
    },
    "disassemble_capstone": {
        "fn": disassemble_capstone,
        "signature": "disassemble_capstone(path, arch='x86', mode='64', offset=0, count=50) -> str",
        "desc": "Pure Python disassembly. arch: x86/arm/arm64/mips, mode: 32/64/arm/thumb",
        "deps": "capstone (pip)",
    },
    "decompile_ghidra": {
        "fn": decompile_ghidra,
        "signature": "decompile_ghidra(path, function_name=None, timeout=120) -> str",
        "desc": "Decompile binary to C pseudocode using Ghidra headless",
        "deps": "ghidra (analyzeHeadless in PATH)",
    },
    "list_functions_radare2": {
        "fn": list_functions_radare2,
        "signature": "list_functions_radare2(path) -> str",
        "desc": "List functions found in binary using radare2",
        "deps": "radare2, r2pipe (pip)",
    },
    "analyze_pcap": {
        "fn": analyze_pcap,
        "signature": "analyze_pcap(pcap_path, display_filter=None, packet_count=20) -> str",
        "desc": "Analyze pcap/pcapng — first N packets with protocol info",
        "deps": "tshark (pyshark optional)",
    },
    "protocol_stats_pcap": {
        "fn": protocol_stats_pcap,
        "signature": "protocol_stats_pcap(pcap_path) -> str",
        "desc": "Protocol hierarchy statistics from pcap",
        "deps": "tshark",
    },
    "pcap_conversations": {
        "fn": pcap_conversations,
        "signature": "pcap_conversations(pcap_path) -> str",
        "desc": "TCP/UDP conversations in pcap",
        "deps": "tshark",
    },
}


def get_re_tool_descriptions() -> str:
    """Tool list for worker prompt."""
    lines = []
    for name, info in RE_TOOLS.items():
        lines.append(f"  - {info['signature']}")
        lines.append(f"    {info['desc']}")
        lines.append(f"    deps: {info['deps']}")
        lines.append("")
    return "\n".join(lines)


def call_re_tool(name: str, args) -> str:
    """Call an RE tool by name with positional or keyword args.

    Args:
        name: tool name (e.g. "binary_info")
        args: list (positional) or dict (kwargs) or single value

    Returns:
        Tool output as string (or ERROR message)
    """
    if name not in RE_TOOLS:
        available = ", ".join(RE_TOOLS.keys())
        return f"ERROR: unknown RE tool '{name}'. Available: {available}"

    fn = RE_TOOLS[name]["fn"]
    try:
        if isinstance(args, dict):
            return fn(**args)
        elif isinstance(args, list):
            return fn(*args)
        else:
            # Single value (string path, etc.)
            return fn(args)
    except Exception as e:
        return f"ERROR calling {name}: {type(e).__name__}: {e}"


def check_re_environment() -> Dict[str, bool]:
    """Check which RE tools are available in the environment."""
    return {
        # System tools
        "radare2_binary": _check_tool("r2"),
        "ghidra_analyzeHeadless": _check_tool("analyzeHeadless"),
        "tshark": _check_tool("tshark"),
        "file_cmd": _check_tool("file"),
        "readelf": _check_tool("readelf"),
        "nm": _check_tool("nm"),
        "strings": _check_tool("strings"),
        "objdump": _check_tool("objdump"),
        # Python libraries
        "r2pipe_python": HAS_R2,
        "capstone_python": HAS_CAPSTONE,
        "pyshark_python": HAS_PYSHARK,
    }


# === CLI (self-test) ===

if __name__ == "__main__":
    logging.basicConfig(stream=_OUT, format="%(message)s", level=logging.INFO)
    import argparse

    parser = argparse.ArgumentParser(description="byte-swarmy RE tools")
    parser.add_argument("--check", action="store_true", help="Check environment and exit")
    parser.add_argument("--list", action="store_true", help="List available tools")
    parser.add_argument("--call", nargs=2, metavar=("TOOL", "PATH"),
                        help="Call a tool on a file (e.g. --call binary_info /bin/ls)")
    args = parser.parse_args()

    if args.check or (not args.list and not args.call):
        log.info("=" * 60)
        log.info("  RE tools environment check")
        log.info("=" * 60)
        env = check_re_environment()
        for k, v in env.items():
            status = f"{GREEN}✓{RESET}" if v else f"{RED}✗{RESET}"
            log.info(f"  {status} {k}")
        available = sum(1 for v in env.values() if v)
        total = len(env)
        log.info(f"\n  {available}/{total} tools available")

    if args.list:
        log.info("\n=== Available RE tools ===\n")
        log.info(get_re_tool_descriptions())

    if args.call:
        tool_name, file_path = args.call
        log.info(f"\n=== Calling {tool_name}({file_path!r}) ===\n")
        result = call_re_tool(tool_name, [file_path])
        log.info(result)
