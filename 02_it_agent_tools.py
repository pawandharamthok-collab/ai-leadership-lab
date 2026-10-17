import os
import sys
import ctypes
import subprocess
import json
import time

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY is missing in .env")
    exit(1)

client = genai.Client(api_key=api_key)

# =====================================================================
# ENTERPRISE TOOLS (Real Functions the AI Agent Can Autonomously Call)
# =====================================================================

def get_system_memory_status() -> str:
    """Queries real-time physical memory (RAM) usage on the host operating system."""
    print("\n   [TOOL EXECUTED] -> `get_system_memory_status()` called by Agent")
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    mem = MEMORYSTATUSEX()
    mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    
    total_gb = round(mem.ullTotalPhys / (1024**3), 2)
    avail_gb = round(mem.ullAvailPhys / (1024**3), 2)
    used_gb = round(total_gb - avail_gb, 2)
    usage_pct = mem.dwMemoryLoad
    
    data = {
        "total_ram_gb": total_gb,
        "used_ram_gb": used_gb,
        "available_ram_gb": avail_gb,
        "memory_load_percent": f"{usage_pct}%"
    }
    return json.dumps(data)


def get_top_memory_processes() -> str:
    """Lists the top 5 highest memory-consuming processes currently active on the host."""
    print("\n   [TOOL EXECUTED] -> `get_top_memory_processes()` called by Agent")
    ps_cmd = 'Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 ProcessName, @{N="RAM_MB";E={[math]::Round($_.WorkingSet64/1MB, 1)}} | ConvertTo-Json'
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return json.dumps({"error": str(e)})


# =====================================================================
# AGENT INITIALIZATION & ORCHESTRATION
# =====================================================================

print("\n" + "="*75)
print("[STEP 4] AUTONOMOUS IT OPERATIONS AGENT (TOOL CALLING)")
print("="*75)

tools = [get_system_memory_status, get_top_memory_processes]

system_instruction = (
    "You are an Autonomous Enterprise SRE / IT Operations Agent. "
    "You have access to live system diagnostics tools. "
    "When a user asks for a health check, systematically inspect system resources. "
    "If memory load exceeds 70%, drill down into the top memory-consuming processes. "
    "Provide a structured, executive incident assessment with recommendations."
)

chat = client.chats.create(
    model="gemini-3.1-flash-lite",
    config=types.GenerateContentConfig(
        tools=tools,
        system_instruction=system_instruction,
        temperature=0.1,
    )
)

user_objective = (
    "Conduct an automated health assessment of this host machine. "
    "Check our RAM status. If it exceeds 70%, analyze what processes are causing it "
    "and give me an executive remediation plan."
)

print(f"Agent Prompt: \"{user_objective}\"")
print("\nOrchestrating agent workflow (observing tool execution)...")

start_time = time.time()
response = chat.send_message(user_objective)
latency = round(time.time() - start_time, 2)

print("\n" + "-"*75)
print("[AGENT'S EXECUTIVE SYNTHESIS]")
print("-" * 75)
print(response.text)
print("-" * 75)
print(f"Turnaround Latency: {latency}s | Tools were autonomously invoked via AFC")
print("="*75 + "\n")
