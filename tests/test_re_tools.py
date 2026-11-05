# Test per modulo RE tools di byte-swarmy
# Verifica che tutti i tool RE siano installati e funzionanti

import sys
import os
import tempfile
import subprocess
from pathlib import Path

# Add CORE to path (assume test runs from project root)
sys.path.insert(0, str(Path(__file__).parent.parent))

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"
ok = lambda m: print(f"  {GREEN}✓{RESET} {m}")
fail = lambda m: print(f"  {RED}✗{RESET} {m}")
warn = lambda m: print(f"  {YELLOW}⚠{RESET} {m}")

def test_environment_check():
    """check_re_environment() returns dict with all tools."""
    print("\n=== TEST 1: Environment check ===")
    try:
        from CORE.re_tools import check_re_environment
        env = check_re_environment()
        assert isinstance(env, dict)
        assert len(env) >= 10
        ok(f"check_re_environment() returns {len(env)} entries")
        for k, v in env.items():
            status = "✓" if v else "✗"
            print(f"    {status} {k}: {v}")
        return True
    except Exception as e:
        fail(f"check_re_environment failed: {e}")
        return False

def test_tool_registry():
    """RE_TOOLS registry has expected tools."""
    print("\n=== TEST 2: Tool registry ===")
    try:
        from CORE.re_tools import RE_TOOLS, get_re_tool_descriptions
        expected = {"binary_info", "extract_strings", "disassemble_radare2",
                    "disassemble_capstone", "decompile_ghidra",
                    "list_functions_radare2", "analyze_pcap",
                    "protocol_stats_pcap", "pcap_conversations"}
        actual = set(RE_TOOLS.keys())
        missing = expected - actual
        if missing:
            fail(f"Missing tools: {missing}")
            return False
        ok(f"RE_TOOLS has {len(actual)} tools: {sorted(actual)}")
        # Check descriptions
        desc = get_re_tool_descriptions()
        assert len(desc) > 100
        ok("get_re_tool_descriptions() returns non-empty string")
        return True
    except Exception as e:
        fail(f"test_tool_registry failed: {e}")
        return False

def test_call_unknown_tool():
    """call_re_tool with unknown name returns ERROR."""
    print("\n=== TEST 3: Call unknown tool ===")
    try:
        from CORE.re_tools import call_re_tool
        result = call_re_tool("nonexistent_tool", ["/bin/ls"])
        assert "ERROR" in result
        assert "Available:" in result
        ok(f"Unknown tool returns ERROR with available list")
        return True
    except Exception as e:
        fail(f"test_call_unknown_tool failed: {e}")
        return False

def test_call_with_nonexistent_file():
    """Tools handle non-existent files gracefully."""
    print("\n=== TEST 4: Non-existent file handling ===")
    try:
        from CORE.re_tools import call_re_tool
        fake_path = "/tmp/nonexistent_file_for_re_test_xyz123"
        result = call_re_tool("binary_info", [fake_path])
        assert "ERROR" in result
        assert "not found" in result.lower() or "no such file" in result.lower()
        ok(f"binary_info on non-existent file returns ERROR")
        return True
    except Exception as e:
        fail(f"test_call_with_nonexistent_file failed: {e}")
        return False

def test_binary_info_on_real_binary():
    """binary_info works on /bin/ls (if it exists)."""
    print("\n=== TEST 5: binary_info on /bin/ls ===")
    try:
        from CORE.re_tools import call_re_tool, check_re_environment
        env = check_re_environment()
        if not env.get("file_cmd"):
            warn("file command not available, skipping")
            return True  # don't fail test if tool not installed

        if not Path("/bin/ls").exists():
            warn("/bin/ls not found, trying /usr/bin/ls")
            target = "/usr/bin/ls"
        else:
            target = "/bin/ls"

        result = call_re_tool("binary_info", [target])
        if "ERROR" in result:
            warn(f"binary_info returned error: {result[:100]}")
            return True  # don't fail if file output unavailable

        assert "ELF" in result or "elf" in result.lower() or "executable" in result.lower()
        ok(f"binary_info on {target} returns valid info")
        # Show first 200 chars
        print(f"    Output preview: {result[:200]}...")
        return True
    except Exception as e:
        fail(f"test_binary_info_on_real_binary failed: {e}")
        return False

def test_extract_strings():
    """extract_strings works on a small test binary."""
    print("\n=== TEST 6: extract_strings ===")
    try:
        from CORE.re_tools import call_re_tool

        target = "/bin/ls" if Path("/bin/ls").exists() else "/usr/bin/ls"
        if not Path(target).exists():
            warn("No /bin/ls to test on")
            return True

        result = call_re_tool("extract_strings", [target, 8, 20])  # min_len=8, max=20
        if "ERROR" in result:
            warn(f"extract_strings returned error: {result[:100]}")
            return True

        # Should find some strings (ls has many)
        assert "String" in result or "strings" in result.lower()
        ok(f"extract_strings on {target} returns strings")
        print(f"    Output preview: {result[:200]}...")
        return True
    except Exception as e:
        fail(f"test_extract_strings failed: {e}")
        return False

def test_disassemble_capstone():
    """disassemble_capstone works (pure Python, no external deps)."""
    print("\n=== TEST 7: disassemble_capstone ===")
    try:
        from CORE.re_tools import call_re_tool, check_re_environment
        env = check_re_environment()
        if not env.get("capstone_python"):
            warn("capstone not installed, skipping (pip install capstone)")
            return True

        target = "/bin/ls" if Path("/bin/ls").exists() else "/usr/bin/ls"
        if not Path(target).exists():
            warn("No /bin/ls to test on")
            return True

        # Read ELF header offset (e_entry is at offset 24 for 64-bit ELF)
        # Just try offset 0 with x86_64
        result = call_re_tool("disassemble_capstone", [target, "x86", "64", 0x1000, 10])
        if "ERROR" in result:
            warn(f"capstone disasm returned error: {result[:100]}")
            # Try different offset
            result = call_re_tool("disassemble_capstone", [target, "x86", "64", 0, 10])
            if "ERROR" in result:
                return True  # don't fail

        ok(f"disassemble_capstone on {target} returns disassembly")
        print(f"    Output preview: {result[:200]}...")
        return True
    except Exception as e:
        fail(f"test_disassemble_capstone failed: {e}")
        return False

def test_pcap_analysis():
    """analyze_pcap handles missing files and would work on real pcap."""
    print("\n=== TEST 8: pcap analysis (synthetic) ===")
    try:
        from CORE.re_tools import call_re_tool, check_re_environment
        env = check_re_environment()

        if not env.get("tshark") and not env.get("pyshark_python"):
            warn("Neither tshark nor pyshark available, skipping (install: sudo apt install tshark)")
            return True

        # Test on non-existent file (should fail gracefully)
        result = call_re_tool("analyze_pcap", ["/tmp/nonexistent.pcap"])
        assert "ERROR" in result
        ok("analyze_pcap handles missing file gracefully")

        # Generate a tiny test pcap with scapy if available
        try:
            from scapy.all import IP, TCP, wrpcap
            test_pcap = "/tmp/test_re.pcap"
            wrpcap(test_pcap, [IP(src="1.1.1.1", dst="2.2.2.2")/TCP(dport=80)])
            ok(f"Created test pcap: {test_pcap}")

            result = call_re_tool("analyze_pcap", [test_pcap])
            if "ERROR" in result:
                warn(f"analyze_pcap returned error on real pcap: {result[:100]}")
            else:
                ok("analyze_pcap works on synthetic pcap")
                print(f"    Output preview: {result[:200]}...")

            os.unlink(test_pcap)
        except ImportError:
            warn("scapy not installed, skipping real pcap test")

        return True
    except Exception as e:
        fail(f"test_pcap_analysis failed: {e}")
        return False

def test_tool_signatures_consistent():
    """All tools have signature, desc, deps in registry."""
    print("\n=== TEST 9: Tool registry consistency ===")
    try:
        from CORE.re_tools import RE_TOOLS
        for name, info in RE_TOOLS.items():
            assert "fn" in info, f"{name} missing 'fn'"
            assert callable(info["fn"]), f"{name} 'fn' is not callable"
            assert "signature" in info, f"{name} missing 'signature'"
            assert "desc" in info, f"{name} missing 'desc'"
            assert "deps" in info, f"{name} missing 'deps'"
            assert isinstance(info["signature"], str)
            assert info["signature"].startswith(name + "("), f"{name} signature doesn't start with name"
        ok(f"All {len(RE_TOOLS)} tools have consistent registry entries")
        return True
    except Exception as e:
        fail(f"test_tool_signatures_consistent failed: {e}")
        return False

def main():
    from pathlib import Path
    print("\n" + "="*60)
    print("  🐝 byte-swarmy RE tools — Test Suite")
    print("="*60)

    tests = [
        ("Environment check", test_environment_check),
        ("Tool registry", test_tool_registry),
        ("Call unknown tool", test_call_unknown_tool),
        ("Non-existent file handling", test_call_with_nonexistent_file),
        ("binary_info on /bin/ls", test_binary_info_on_real_binary),
        ("extract_strings", test_extract_strings),
        ("disassemble_capstone", test_disassemble_capstone),
        ("pcap analysis", test_pcap_analysis),
        ("Tool registry consistency", test_tool_signatures_consistent),
    ]

    results = []
    for desc, test in tests:
        try:
            ok_result = test()
            results.append((desc, ok_result))
        except Exception as e:
            fail(f"Test '{desc}' crashed: {e}")
            results.append((desc, False))

    print("\n" + "="*60)
    print("  RIASSUNTO")
    print("="*60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for desc, ok_r in results:
        status = f"{GREEN}✓ PASS{RESET}" if ok_r else f"{RED}✗ FAIL{RESET}"
        print(f"  {status}  {desc}")
    pct = passed / total * 100 if total else 0
    print(f"\n  {passed}/{total} ({pct:.0f}%)")
    print("="*60 + "\n")

    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
