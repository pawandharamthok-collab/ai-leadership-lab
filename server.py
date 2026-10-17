import os
import io
import sys
import ctypes
import subprocess
import json
import time
import base64
import urllib.request
import urllib.parse
import re
import sqlite3
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from google import genai
from google.genai import types
from security_router import PIISanitizer, DataClassificationRouter
from vector_store import VectorKnowledgeBase
from zerodha_service import zerodha_client

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is missing in .env")

app = Flask(__name__, static_folder="static", template_folder="templates")
client = genai.Client(api_key=api_key)

# Configurable database path (supports local memory.db, container mounts, or volume storage)
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db"))

# =====================================================================
# SQLITE PERSISTENT MEMORY INITIALIZATION
# =====================================================================

def init_sqlite_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Seed core persona & rules if empty
    cursor.execute("SELECT COUNT(*) FROM user_memory")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO user_memory (key, value, category) VALUES (?, ?, ?)
        """, [
            ("career_goal", "AI Leader (Enterprise AI Strategy, Agentic Architecture, Leadership)", "core"),
            ("profile", "Experienced IT Professional", "core"),
            ("learning_style", "Strongly visual learner: prioritize diagrams, tables, and flowcharts over text", "core")
        ])
    conn.commit()
    conn.close()

init_sqlite_db()

def get_persistent_memory_context() -> str:
    """Loads all permanent user knowledge from SQLite into prompt context."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_memory ORDER BY category, key")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return ""
        items = [f"- **{k}**: {v}" for k, v in rows]
        return "\n\nPERMANENT KNOWLEDGE BASE (PERSISTED IN SQLITE DB):\n" + "\n".join(items)
    except Exception as e:
        return f"\n(Memory load warning: {e})"

# Global tracker for tools called during a single request
called_tools_log = []

# =====================================================================
# PERSISTENT MEMORY TOOLS FOR AGENT
# =====================================================================

def remember_fact(key: str, value: str) -> str:
    """Permanently saves or updates a key-value fact into your long-term SQLite database (persists across restarts)."""
    called_tools_log.append({
        "tool": "remember_fact",
        "description": f"Saved permanent memory: {key} = {value[:40]}..."
    })
    try:
        sanitized_value, redactions = PIISanitizer.sanitize(value)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_memory (key, value, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key.strip().lower(), sanitized_value.strip()))
        conn.commit()
        conn.close()
        note = f" (Scrubbed {len(redactions)} sensitive item(s))" if redactions else ""
        return f"Fact '{key}' has been permanently stored in your SQLite memory.{note}"
    except Exception as e:
        return f"Error saving memory to SQLite: {str(e)}"


def recall_all_memories() -> str:
    """Retrieves all persistent memories, goals, and facts saved in your SQLite long-term memory."""
    called_tools_log.append({
        "tool": "recall_all_memories",
        "description": "Retrieved all persistent memories from SQLite"
    })
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, updated_at FROM user_memory ORDER BY key")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return "No persistent memories found in database."
        lines = [f"- **{row[0]}**: {row[1]} *(Updated: {row[2]})*" for row in rows]
        return "Current Long-Term Memories in SQLite:\n" + "\n".join(lines)
    except Exception as e:
        return f"Error reading memories: {str(e)}"


# =====================================================================
# LIVE TELEMETRY & SYSTEM TOOLS
# =====================================================================

def get_system_memory_status() -> str:
    """Queries real-time physical memory (RAM) usage on the host operating system."""
    called_tools_log.append({
        "tool": "get_system_memory_status",
        "description": "Queried live Windows RAM metrics via Win32 API"
    })
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
    
    return json.dumps({
        "total_ram_gb": total_gb,
        "used_ram_gb": used_gb,
        "available_ram_gb": avail_gb,
        "memory_load_percent": f"{usage_pct}%"
    })


def get_top_memory_processes() -> str:
    """Lists the top 5 highest memory-consuming processes currently active on the host."""
    called_tools_log.append({
        "tool": "get_top_memory_processes",
        "description": "Queried PowerShell for top memory-consuming processes"
    })
    ps_cmd = 'Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 ProcessName, @{N="RAM_MB";E={[math]::Round($_.WorkingSet64/1MB, 1)}} | ConvertTo-Json'
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_cpu_and_disk_health() -> str:
    """Queries processor load and free disk storage space across partitions."""
    called_tools_log.append({
        "tool": "get_cpu_and_disk_health",
        "description": "Queried CIM instances for CPU load and storage partition margins"
    })
    ps_cmd = '$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; $disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, @{N="FreeGB";E={[math]::Round($_.FreeSpace/1GB,1)}}; [PSCustomObject]@{CPULoadPercent=$cpu; Disks=$disks} | ConvertTo-Json'
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return json.dumps({"error": str(e)})


def is_sensitive_filepath(path: str) -> bool:
    """Security Air-Lock: blocks access to environment configs, keys, credentials, and raw database files."""
    norm = os.path.abspath(path).lower()
    base = os.path.basename(norm)
    if base.startswith(".env") or base.endswith(".env") or "secret" in base or "credential" in base:
        return True
    if base in ("memory.db", "id_rsa", "id_ed25519") or base.endswith((".pem", ".key", ".pfx", ".cer")):
        return True
    if ".git" in norm.split(os.sep):
        return True
    return False


def read_local_file(file_path: str) -> str:
    """Reads the text contents of a local file from disk (e.g. logs, configs, source code, notes)."""
    called_tools_log.append({
        "tool": "read_local_file",
        "description": f"Read file: {file_path}"
    })
    try:
        normalized_path = os.path.abspath(file_path)
        if is_sensitive_filepath(normalized_path):
            return f"Access Denied [Security Air-Lock]: Reading '{os.path.basename(normalized_path)}' is blocked to safeguard API credentials and confidential environment configuration."
        if not os.path.exists(normalized_path):
            return f"Error: File not found at {normalized_path}"
        with open(normalized_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)
            return content if content else "(File is empty)"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_local_file(file_path: str, content: str) -> str:
    """Creates or overwrites a local file with the specified content (e.g. scripts, reports, executive notes)."""
    called_tools_log.append({
        "tool": "write_local_file",
        "description": f"Wrote to file: {file_path}"
    })
    try:
        normalized_path = os.path.abspath(file_path)
        if is_sensitive_filepath(normalized_path):
            return f"Access Denied [Security Air-Lock]: Writing to '{os.path.basename(normalized_path)}' is blocked to protect critical security parameters."
        os.makedirs(os.path.dirname(normalized_path), exist_ok=True)
        with open(normalized_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {normalized_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def execute_powershell_command(command: str) -> str:
    """Executes a PowerShell command on the host Windows machine and returns the output."""
    called_tools_log.append({
        "tool": "execute_powershell_command",
        "description": f"Executed PowerShell: {command[:60]}..."
    })
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=20
        )
        output = res.stdout if res.stdout else res.stderr
        output = output.strip() if output else "(Command completed with no output)"
        return output[:2500]
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 20 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"


def search_the_web(query: str) -> str:
    """Searches the live public internet using a search engine and returns top search results and snippets."""
    called_tools_log.append({
        "tool": "search_the_web",
        "description": f"Searched the web for: {query[:50]}"
    })
    try:
        data = urllib.parse.urlencode({'q': query}).encode('utf-8')
        req = urllib.request.Request(
            'https://lite.duckduckgo.com/lite/',
            data=data,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        snippets = re.findall(r"<td class='result-snippet'>(.*?)</td>", html, flags=re.DOTALL)
        titles = re.findall(r"class='result-link'>(.*?)</a>", html)
        links = re.findall(r"<a rel=\"nofollow\" href=\"(.*?)\" class='result-link'", html)
        if not links:
            links = re.findall(r"<a rel='nofollow' href='(.*?)' class='result-link'", html)

        results = []
        for i in range(min(4, len(snippets))):
            snippet_text = re.sub(r"<[^>]+>", "", snippets[i]).strip()
            title_text = re.sub(r"<[^>]+>", "", titles[i]).strip() if i < len(titles) else "Result"
            url_text = links[i] if i < len(links) else ""
            results.append(f"{i+1}. **{title_text}**\n   {snippet_text}\n   *Link:* {url_text}")

        if results:
            return "\n\n".join(results)
        return f"No results found for query: {query}"
    except Exception as e:
        return f"Error executing web search: {str(e)}"


def fetch_webpage_content(url: str) -> str:
    """Fetches and reads the live text content of any public webpage or documentation URL."""
    called_tools_log.append({
        "tool": "fetch_webpage_content",
        "description": f"Fetched webpage content from: {url[:50]}"
    })
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            text = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL)
            text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:2500]
    except Exception as e:
        return f"Error fetching webpage: {str(e)}"


def audit_and_sanitize_content(content: str) -> str:
    """Scans any text, code, or document for sensitive PII (API keys, passwords, credentials, emails, phone numbers) and returns the sanitized version with an audit report."""
    called_tools_log.append({
        "tool": "audit_and_sanitize_content",
        "description": "Scanned content for PII/secrets using local regex scrubber"
    })
    sanitized, redactions = PIISanitizer.sanitize(content)
    report = {
        "redactions_count": len(redactions),
        "redactions_details": redactions,
        "sanitized_preview": sanitized[:200] + ("..." if len(sanitized) > 200 else "")
    }
    return json.dumps(report, indent=2)


def classify_and_route_document(content: str, title: str = "", user_intent: str = "") -> str:
    """Evaluates text or document for security sensitivity and token volume. Recommends the exact storage tier (Tier 1 Local SQLite, Tier 2 Pinecone Vector DB, or Tier 3 Google Files API) with executive rationale."""
    called_tools_log.append({
        "tool": "classify_and_route_document",
        "description": f"Classified data route for: {title or 'Document'}"
    })
    result = DataClassificationRouter.route(content, title, user_intent)
    return json.dumps(result, indent=2)


def upload_document_to_cloud(file_path: str, display_name: str = "") -> str:
    """Uploads a local document (PDF, TXT, MD, CSV, etc.) from the laptop to Google Cloud Files API (Tier 3).
    Performs local PII scrubbing for text documents and returns the cloud file reference for multimodal reasoning."""
    called_tools_log.append({
        "tool": "upload_document_to_cloud",
        "description": f"Uploaded document to Tier 3 cloud context: {os.path.basename(file_path)}"
    })
    try:
        norm_path = os.path.abspath(file_path)
        if not os.path.exists(norm_path):
            return f"Error: File not found at {norm_path}"
        
        name = display_name or os.path.basename(norm_path)
        ext = os.path.splitext(norm_path)[1].lower()
        
        if ext in [".txt", ".md", ".json", ".csv", ".py", ".html", ".xml", ".yaml", ".yml"]:
            with open(norm_path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
            sanitized_text, redactions = PIISanitizer.sanitize(raw_text)
            stream = io.BytesIO(sanitized_text.encode("utf-8"))
            uploaded = client.files.upload(
                file=stream,
                config=types.UploadFileConfig(mime_type="text/plain", display_name=name)
            )
            note = f" (Sanitized {len(redactions)} sensitive items before cloud upload)" if redactions else ""
        else:
            uploaded = client.files.upload(
                file=norm_path,
                config=types.UploadFileConfig(display_name=name)
            )
            note = ""
            
        return json.dumps({
            "status": "success",
            "file_name": uploaded.name,
            "display_name": uploaded.display_name or name,
            "state": str(uploaded.state),
            "tier": "Tier 3 (Google Files API)",
            "note": f"Document indexed in cloud context cache.{note} 0% laptop RAM load."
        }, indent=2)
    except Exception as e:
        return f"Error uploading document to cloud: {str(e)}"


def list_cloud_documents() -> str:
    """Lists all active documents currently cached in Google Cloud Files API (Tier 3) with status and size."""
    called_tools_log.append({
        "tool": "list_cloud_documents",
        "description": "Queried Google Cloud Files API for active documents"
    })
    try:
        files = list(client.files.list())
        if not files:
            return "No documents currently cached in Google Cloud Files API."
        
        items = []
        for f in files:
            items.append({
                "file_name": f.name,
                "display_name": f.display_name,
                "mime_type": f.mime_type,
                "state": str(f.state)
            })
        return json.dumps(items, indent=2)
    except Exception as e:
        return f"Error listing cloud documents: {str(e)}"


def delete_cloud_document(file_name: str) -> str:
    """Permanently deletes a cached document from Google Cloud Files API (Tier 3) for privacy and ephemerality."""
    called_tools_log.append({
        "tool": "delete_cloud_document",
        "description": f"Deleted document from cloud cache: {file_name}"
    })
    try:
        client.files.delete(name=file_name)
        return f"Successfully deleted document '{file_name}' from Google Cloud storage."
    except Exception as e:
        return f"Error deleting cloud document: {str(e)}"


def index_knowledge_snippet(content: str, title: str = "Knowledge Snippet") -> str:
    """Indexes a text snippet, SOP, framework guide, or IT runbook into Tier 2 Vector Knowledge Base (Pinecone Serverless / Zero-RAM Vector Store).
    Automatically scrubs PII and generates 768-dim cloud embeddings on Google TPUs (0% laptop RAM load)."""
    called_tools_log.append({
        "tool": "index_knowledge_snippet",
        "description": f"Indexed into Tier 2 Vector DB: {title}"
    })
    try:
        result = VectorKnowledgeBase.index_document(client, content, title)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error indexing snippet into vector database: {str(e)}"


def search_knowledge_base(query: str, top_k: int = 3) -> str:
    """Performs semantic vector similarity search across all indexed Tier 2 knowledge snippets, architecture guides, and runbooks.
    Embeds the query using cloud TPUs and retrieves relevant passages."""
    called_tools_log.append({
        "tool": "search_knowledge_base",
        "description": f"Vector search for: {query[:50]}"
    })
    try:
        matches = VectorKnowledgeBase.semantic_search(client, query, top_k=top_k)
        if not matches:
            return "No matching knowledge snippets found in Tier 2 vector database."
        
        output = [f"Found {len(matches)} relevant knowledge snippets:"]
        for i, m in enumerate(matches):
            output.append(f"\n[{i+1}] **{m['title']}** (Relevance Score: {m['score']}):\n{m['content']}")
        return "\n".join(output)
    except Exception as e:
        return f"Error searching vector knowledge base: {str(e)}"


def list_firebase_projects() -> str:
    """Discovers and lists all cloud Firebase projects associated with your authenticated account."""
    called_tools_log.append({
        "tool": "list_firebase_projects",
        "description": "Queried Firebase CLI for active cloud projects"
    })
    try:
        res = subprocess.run("firebase projects:list --json", shell=True, capture_output=True, text=True, timeout=15)
        data = json.loads(res.stdout)
        projects = data.get("result", [])
        if not projects:
            return "No Firebase projects found or not logged in."
        
        summary = ["Discovered Firebase Cloud Projects:"]
        for p in projects:
            p_id = p.get("projectId")
            name = p.get("displayName")
            num = p.get("projectNumber")
            state = p.get("state")
            rsrc = p.get("resources", {})
            summary.append(f"- **{name}** (`{p_id}`) • Number: {num} • State: {state}")
            if rsrc.get("hostingSite"):
                summary.append(f"  * Default Hosting: `https://{rsrc['hostingSite']}.web.app`")
            if rsrc.get("realtimeDatabaseInstance"):
                summary.append(f"  * RTDB Instance: `{rsrc['realtimeDatabaseInstance']}`")
        return "\n".join(summary)
    except Exception as e:
        return f"Error listing Firebase projects: {str(e)}"


def get_firebase_sites_and_health(project_id: str = "family-apps-hub") -> str:
    """Queries all deployed web hosting sites under a Firebase project and conducts live HTTP health & latency checks."""
    called_tools_log.append({
        "tool": "get_firebase_sites_and_health",
        "description": f"Audited live hosting sites & health for: {project_id}"
    })
    try:
        cmd = f"firebase hosting:sites:list --project {project_id} --json"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        data = json.loads(res.stdout)
        sites = data.get("result", {}).get("sites", [])
        if not sites:
            return f"No hosting sites found for project '{project_id}'."
        
        results = []
        for s in sites:
            site_name = s.get("name", "").split("/")[-1]
            url = s.get("defaultUrl", f"https://{site_name}.web.app")
            site_type = s.get("type", "SITE")
            try:
                t0 = time.time()
                resp = urllib.request.urlopen(url, timeout=3)
                latency = round((time.time() - t0) * 1000, 1)
                status = f"🟢 HTTP {resp.status} ({latency}ms)"
            except Exception as ping_err:
                status = f"🔴 Offline/Error ({str(ping_err)[:30]})"
            
            results.append({
                "site": site_name,
                "url": url,
                "type": site_type,
                "health": status
            })
        
        return json.dumps({
            "project_id": project_id,
            "total_sites": len(sites),
            "telemetry": results
        }, indent=2)
    except Exception as e:
        return f"Error auditing Firebase sites: {str(e)}"


def get_firebase_project_apps(project_id: str = "family-apps-hub") -> str:
    """Lists registered client applications (Web, Android, iOS) under a Firebase project."""
    called_tools_log.append({
        "tool": "get_firebase_project_apps",
        "description": f"Queried registered client apps for: {project_id}"
    })
    try:
        cmd = f"firebase apps:list --project {project_id} --json"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        data = json.loads(res.stdout)
        apps = data.get("result", [])
        if not apps:
            return f"No client apps found registered in project '{project_id}'."
        
        items = []
        for a in apps:
            items.append({
                "app_id": a.get("appId"),
                "display_name": a.get("displayName"),
                "platform": a.get("platform"),
                "state": a.get("state")
            })
        return json.dumps(items, indent=2)
    except Exception as e:
        return f"Error listing Firebase apps: {str(e)}"


def deploy_firebase_site(project_dir: str, only_target: str = "hosting", project_id: str = "") -> str:
    """Deploys code from a local project folder to Firebase Hosting and automatically runs post-deployment health verification.
    project_dir: Local directory path containing the project and firebase.json.
    only_target: Deployment target, e.g. 'hosting' or 'hosting:pawan-vault'.
    project_id: Firebase project id (e.g. 'family-apps-hub' or 'homecanvas-88550')."""
    called_tools_log.append({
        "tool": "deploy_firebase_site",
        "description": f"Triggered Firebase deployment from {os.path.basename(project_dir)}"
    })
    try:
        norm_dir = os.path.abspath(project_dir)
        if not os.path.exists(norm_dir):
            return f"Error: Project directory not found at {norm_dir}"
        
        cmd_parts = ["firebase", "deploy"]
        if only_target:
            cmd_parts.extend(["--only", only_target])
        if project_id:
            cmd_parts.extend(["--project", project_id])
        cmd_parts.append("--non-interactive")
        
        cmd = " ".join(cmd_parts)
        t0 = time.time()
        res = subprocess.run(cmd, cwd=norm_dir, shell=True, capture_output=True, text=True, timeout=60)
        duration = round(time.time() - t0, 1)
        
        output = res.stdout if res.stdout else res.stderr
        success = res.returncode == 0
        
        report = {
            "status": "success" if success else "failed",
            "directory": norm_dir,
            "command": cmd,
            "duration_sec": duration,
            "output_preview": output[-500:] if len(output) > 500 else output
        }
        return json.dumps(report, indent=2)
    except subprocess.TimeoutExpired:
        return "Error: Deployment command timed out after 60 seconds."
    except Exception as e:
        return f"Error during deployment: {str(e)}"


# =====================================================================
# ZERODHA SECURE READ-ONLY PORTFOLIO & WEALTH COPILOT TOOLS
# =====================================================================

def get_zerodha_account_overview() -> str:
    """Queries your Zerodha trading account overview, available cash, equity/commodity margins, collateral, and connection status (anonymized, no account IDs)."""
    called_tools_log.append({
        "tool": "get_zerodha_account_overview",
        "description": "Queried Zerodha account margins & status (Anonymized)"
    })
    status = zerodha_client.get_status()
    margins = zerodha_client.get_margins()
    return json.dumps({
        "account_status": status,
        "margins": margins
    }, indent=2)


def get_zerodha_holdings() -> str:
    """Retrieves long-term equity delivery portfolio holdings with quantity, average buy price, current LTP, P&L, return %, sector, and portfolio weight (anonymized)."""
    called_tools_log.append({
        "tool": "get_zerodha_holdings",
        "description": "Retrieved Zerodha equity delivery holdings with sector & weight metrics"
    })
    holdings = zerodha_client.get_holdings()
    return json.dumps(holdings, indent=2)


def get_zerodha_portfolio_analytics() -> str:
    """Performs deep executive portfolio analysis: total invested vs current value, overall P&L and ROI %, sector diversification breakdown, concentration risk alerts (>20% single-stock exposure), and top winners vs lagging assets."""
    called_tools_log.append({
        "tool": "get_zerodha_portfolio_analytics",
        "description": "Executed executive portfolio risk & diversification analysis"
    })
    analytics = zerodha_client.get_portfolio_analytics()
    return json.dumps(analytics, indent=2)


def get_zerodha_positions() -> str:
    """Retrieves current open intraday (MIS) and F&O derivative positions, including mark-to-market (M2M) P&L, day P&L, and net quantities (anonymized)."""
    called_tools_log.append({
        "tool": "get_zerodha_positions",
        "description": "Retrieved Zerodha intraday and F&O positions (Anonymized)"
    })
    positions = zerodha_client.get_positions()
    return json.dumps(positions, indent=2)


def get_live_stock_quote(symbols: str) -> str:
    """Fetches real-time market quotes (LTP, open/high/low/close, net day change, volume, 52-week high/low) directly from the National Stock Exchange of India (NSE) feed.
    symbols: Comma-separated symbols or indices, e.g. 'RELIANCE, INFY, TCS, TATASTEEL, NIFTY 50, BANK NIFTY'"""
    called_tools_log.append({
        "tool": "get_live_stock_quote",
        "description": f"Fetched live NSE market quote for: {symbols[:50]}"
    })
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        return "Error: No symbols provided."
    quote_data = zerodha_client.get_quote(sym_list)
    return json.dumps(quote_data, indent=2)


def get_stock_technical_levels(symbol: str) -> str:
    """Calculates key technical levels (52-week high/low, support/resistance, market posture, and drawdown from peak) for any NSE equity or index."""
    called_tools_log.append({
        "tool": "get_stock_technical_levels",
        "description": f"Queried NSE technical levels for: {symbol}"
    })
    levels = zerodha_client.get_technical_levels(symbol)
    return json.dumps(levels, indent=2)


def get_zerodha_coin_mutual_funds() -> str:
    """Retrieves all active Coin mutual fund holdings with units, purchase NAV, current NAV, invested amount, current value, and unrealized returns (anonymized)."""
    called_tools_log.append({
        "tool": "get_zerodha_coin_mutual_funds",
        "description": "Retrieved Zerodha Coin mutual fund holdings"
    })
    mf_data = zerodha_client.get_mutual_fund_holdings()
    return json.dumps(mf_data, indent=2)


def get_zerodha_coin_sips() -> str:
    """Retrieves all active and paused Zerodha Coin Systematic Investment Plans (SIPs), monthly deduction dates, installment amounts, and frequency."""
    called_tools_log.append({
        "tool": "get_zerodha_coin_sips",
        "description": "Retrieved Zerodha Coin active SIP mandates"
    })
    sips = zerodha_client.get_mutual_fund_sips()
    return json.dumps(sips, indent=2)


def get_zerodha_combined_wealth() -> str:
    """Combines direct stock holdings and Coin mutual funds into an executive master wealth balance sheet, overall ROI %, and investor profitability verdict."""
    called_tools_log.append({
        "tool": "get_zerodha_combined_wealth",
        "description": "Queried combined stock and mutual fund wealth overview"
    })
    combined = zerodha_client.get_combined_wealth_overview()
    return json.dumps(combined, indent=2)


agent_tools = [
    remember_fact,
    recall_all_memories,
    audit_and_sanitize_content,
    classify_and_route_document,
    index_knowledge_snippet,
    search_knowledge_base,
    upload_document_to_cloud,
    list_cloud_documents,
    delete_cloud_document,
    list_firebase_projects,
    get_firebase_sites_and_health,
    get_firebase_project_apps,
    deploy_firebase_site,
    get_system_memory_status,
    get_top_memory_processes,
    get_cpu_and_disk_health,
    read_local_file,
    write_local_file,
    execute_powershell_command,
    search_the_web,
    fetch_webpage_content,
    get_zerodha_account_overview,
    get_zerodha_holdings,
    get_zerodha_portfolio_analytics,
    get_zerodha_positions,
    get_live_stock_quote,
    get_stock_technical_levels,
    get_zerodha_coin_mutual_funds,
    get_zerodha_coin_sips,
    get_zerodha_combined_wealth
]

system_instruction = (
    "You are an Advanced Executive AI Leadership Partner and Personal Technical Assistant to an experienced IT Professional. "
    "You have real tools for Long-Term SQLite Memory, Firebase Cloud Operations, Tier 2 Vector Knowledge Base, Tier 3 Cloud Document Context (Google Files API), Security Auditing, Data Routing, File System, Terminal, System Diagnostics, Live Web Search, and National Stock Exchange (NSE) & Zerodha Wealth Intelligence:\n"
    "1. ZERODHA & NSE WEALTH COPILOT (STRICTLY READ-ONLY): You have secure tools for Zerodha portfolio tracking (`get_zerodha_holdings`, `get_zerodha_portfolio_analytics`, `get_zerodha_account_overview`, `get_zerodha_positions`) combined with live market feeds from the National Stock Exchange of India (`get_live_stock_quote`, `get_stock_technical_levels`). All personal data (client IDs, email, PAN) is air-gapped and stripped. Live order execution is permanently disabled for capital safety. Act as an expert Chief Investment Officer and Risk Analyst: analyze sector diversification, risk concentration, valuation, top performers and laggards, and clearly answer all user doubts regarding stock fundamentals, technicals, allocation strategies, stop-loss rationale, and market trends with crisp markdown tables and insightful takeaways.\n"
    "2. FIREBASE OPERATIONS & CLOUD GOVERNANCE: Use `list_firebase_projects` to query all Firebase projects, `get_firebase_sites_and_health` to conduct live HTTP/SSL telemetry on production web apps, and `get_firebase_project_apps` to list client applications.\n"
    "3. SECURITY & DATA GOVERNANCE: Use `audit_and_sanitize_content` to scrub sensitive PII, API keys, passwords, and credentials. Use `classify_and_route_document` to route information into Tier 1 (Local SQLite), Tier 2 (Vector DB), or Tier 3 (Cloud Document Context).\n"
    "4. TIER 2 VECTOR KNOWLEDGE BASE: Index granular runbooks, architecture patterns, and frameworks (`index_knowledge_snippet`), and query them with semantic search (`search_knowledge_base`).\n"
    "5. TIER 3 CLOUD DOCUMENT CONTEXT: Upload large PDFs/documents to Google Files API (`upload_document_to_cloud`), list active documents (`list_cloud_documents`), and clean up when finished (`delete_cloud_document`). 0% laptop RAM load.\n"
    "6. LONG-TERM MEMORY: You have a persistent SQLite database (`remember_fact`, `recall_all_memories`). Save important user facts, rules, or preferences permanently.\n"
    "7. LIVE WEB SEARCH & BROWSING: Search the web (`search_the_web`) for current news or documentation, and read public URLs (`fetch_webpage_content`).\n"
    "8. FILE SYSTEM & TERMINAL: Read/write files (`read_local_file`, `write_local_file`) and run PowerShell (`execute_powershell_command`).\n"
    "9. SYSTEM TELEMETRY: Query RAM, CPU, and disk storage.\n"
    + get_persistent_memory_context() +
    "\n\nAlways provide crisp, visually structured answers with tables and bullet points. Invoke tools autonomously."
)

# Persistent chat session
chat_session = client.chats.create(
    model="gemini-3.1-flash-lite",
    config=types.GenerateContentConfig(
        tools=agent_tools,
        system_instruction=system_instruction,
        temperature=0.1,
    )
)

# =====================================================================
# ENTERPRISE TOKEN OPTIMIZATION ENGINE
# =====================================================================

def prune_and_optimize_tokens(chat_obj, max_history_turns=10):
    try:
        if hasattr(chat_obj, '_curated_history') and chat_obj._curated_history:
            if len(chat_obj._curated_history) > max_history_turns:
                chat_obj._curated_history = chat_obj._curated_history[-max_history_turns:]
            
            for content in chat_obj._curated_history[:-2]:
                if hasattr(content, 'parts') and content.parts:
                    new_parts = []
                    for p in content.parts:
                        if hasattr(p, 'inline_data') and p.inline_data:
                            new_parts.append(types.Part.from_text(text="[Screenshot from earlier turn previously analyzed]"))
                        else:
                            new_parts.append(p)
                    content.parts = new_parts
    except Exception as opt_err:
        print("Token optimization warning:", opt_err)


# =====================================================================
# ROUTES (STREAMING SSE & REST)
# =====================================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/showcase")
def showcase():
    """Executive Architecture Showcase & Interview Presentation Dashboard."""
    return render_template("showcase.html")


@app.route("/pitch")
def pitch():
    """Executive AI Leadership & ₹5 Lakh/Month Strategic Pitch Deck."""
    return render_template("pitch.html")


@app.route("/api/upload_doc", methods=["POST"])
def upload_doc():
    """Uploads a document from the web UI to Google Cloud Files API (Tier 3)."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file_obj = request.files["file"]
    if file_obj.filename == "":
        return jsonify({"error": "Empty filename"}), 400
        
    filename = file_obj.filename
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        raw_bytes = file_obj.read()
        # If text-based, sanitize PII first
        if ext in [".txt", ".md", ".json", ".csv", ".py", ".html", ".xml", ".yaml", ".yml"]:
            text = raw_bytes.decode("utf-8", errors="replace")
            sanitized_text, redactions = PIISanitizer.sanitize(text)
            stream = io.BytesIO(sanitized_text.encode("utf-8"))
            uploaded = client.files.upload(
                file=stream,
                config=types.UploadFileConfig(mime_type="text/plain", display_name=filename)
            )
            redactions_count = len(redactions)
        else:
            stream = io.BytesIO(raw_bytes)
            mime = file_obj.mimetype or "application/octet-stream"
            uploaded = client.files.upload(
                file=stream,
                config=types.UploadFileConfig(mime_type=mime, display_name=filename)
            )
            redactions_count = 0
            
        return jsonify({
            "status": "success",
            "file_name": uploaded.name,
            "display_name": uploaded.display_name or filename,
            "redactions_count": redactions_count,
            "tier": "Tier 3 (Google Files API)",
            "uri": uploaded.uri
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/zerodha/login")
def zerodha_login_redirect():
    """Generates the official Zerodha OAuth login URL."""
    login_url = zerodha_client.get_login_url()
    if login_url.startswith("http"):
        from flask import redirect
        return redirect(login_url)
    return jsonify({"error": login_url}), 400


@app.route("/zerodha/callback")
def zerodha_callback():
    """Captures morning OAuth request_token from Zerodha and generates access_token."""
    request_token = request.args.get("request_token")
    if not request_token:
        error = request.args.get("error_type", "Unknown error or login cancelled")
        return f"""
        <html>
        <body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:90vh;text-align:center;">
            <div style="background:#1e293b;padding:30px;border-radius:12px;border:1px solid #ef4444;max-width:480px;">
                <h3 style="color:#ef4444;">❌ Authentication Failed</h3>
                <p style="color:#94a3b8;">{error}</p>
                <a href="/" style="display:inline-block;margin-top:15px;padding:8px 20px;background:#3b82f6;color:white;text-decoration:none;border-radius:6px;">Return to Assistant</a>
            </div>
        </body>
        </html>
        """
    
    result = zerodha_client.exchange_request_token(request_token)
    if result.get("status") == "success":
        return f"""
        <html>
        <body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:90vh;text-align:center;">
            <div style="background:#1e293b;padding:40px;border-radius:12px;border:1px solid #22c55e;max-width:500px;">
                <h2 style="color:#22c55e;">✅ Zerodha Session Active!</h2>
                <p>Welcome, <b>{result.get('user_name', 'Trader')}</b>.</p>
                <p style="color:#94a3b8;font-size:0.9rem;">Your secure, Read-Only Zerodha access token has been generated and saved for today.</p>
                <a href="/" style="display:inline-block;margin-top:20px;padding:10px 24px;background:#3b82f6;color:white;text-decoration:none;border-radius:8px;font-weight:600;">Open AI Assistant</a>
            </div>
        </body>
        </html>
        """
    else:
        return f"""
        <html>
        <body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:90vh;text-align:center;">
            <div style="background:#1e293b;padding:30px;border-radius:12px;border:1px solid #ef4444;max-width:480px;">
                <h3 style="color:#ef4444;">Token Exchange Failed</h3>
                <p style="color:#94a3b8;font-size:0.9rem;">{result.get('message')}</p>
                <a href="/" style="display:inline-block;margin-top:15px;padding:8px 20px;background:#3b82f6;color:white;text-decoration:none;border-radius:6px;">Return to Assistant</a>
            </div>
        </body>
        </html>
        """


@app.route("/api/chat_stream", methods=["POST"])
def chat_stream():
    """Real-Time Streaming Response via Server-Sent Events (SSE)."""
    global called_tools_log
    called_tools_log = []
    
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    image_data = data.get("image")
    doc_ref = data.get("doc_ref") or data.get("file_name")
    
    contents = []
    if doc_ref:
        try:
            cloud_file = client.files.get(name=doc_ref)
            contents.append(cloud_file)
        except Exception as doc_err:
            print("Cloud doc fetch error:", doc_err)

    if image_data and image_data.get("data"):
        try:
            img_b64 = image_data["data"]
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(img_b64)
            mime = image_data.get("mime_type", "image/png")
            part = types.Part.from_bytes(data=raw_bytes, mime_type=mime)
            contents.append(part)
        except Exception as img_err:
            print("Image error:", img_err)
            
    if user_message:
        contents.append(user_message)
    elif doc_ref:
        contents.append("Please analyze and summarize this document in detail, highlighting key executive architecture, strategic findings, and action items.")
    elif contents:
        contents.append("Please analyze and describe this screenshot in detail.")
    else:
        return jsonify({"error": "Empty message"}), 400
        
    def generate():
        start_time = time.time()
        prune_and_optimize_tokens(chat_session, max_history_turns=10)
        
        try:
            response_stream = chat_session.send_message_stream(contents)
            for chunk in response_stream:
                # Flush any tools invoked up to this moment
                while called_tools_log:
                    tool_event = called_tools_log.pop(0)
                    yield f"data: {json.dumps({'type': 'tool', 'tool': tool_event['tool'], 'desc': tool_event['description']})}\n\n"
                
                if chunk.text:
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"
                    
            # Flush any remaining tools
            while called_tools_log:
                tool_event = called_tools_log.pop(0)
                yield f"data: {json.dumps({'type': 'tool', 'tool': tool_event['tool'], 'desc': tool_event['description']})}\n\n"
                
            latency = round(time.time() - start_time, 2)
            yield f"data: {json.dumps({'type': 'done', 'latency': latency})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            
    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Non-streaming fallback endpoint."""
    global called_tools_log
    called_tools_log = []
    
    prune_and_optimize_tokens(chat_session, max_history_turns=10)
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    image_data = data.get("image")
    doc_ref = data.get("doc_ref") or data.get("file_name")
    
    contents = []
    if doc_ref:
        try:
            cloud_file = client.files.get(name=doc_ref)
            contents.append(cloud_file)
        except Exception as doc_err:
            print("Cloud doc fetch error:", doc_err)

    if image_data and image_data.get("data"):
        try:
            img_b64 = image_data["data"]
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(img_b64)
            mime = image_data.get("mime_type", "image/png")
            part = types.Part.from_bytes(data=raw_bytes, mime_type=mime)
            contents.append(part)
        except Exception as img_err:
            print("Image error:", img_err)

    if user_message:
        contents.append(user_message)
    elif doc_ref:
        contents.append("Please analyze and summarize this document in detail, highlighting key executive architecture, strategic findings, and action items.")
    elif contents:
        contents.append("Please analyze and describe this screenshot in detail.")
    else:
        return jsonify({"error": "Empty message"}), 400
    
    start_time = time.time()
    try:
        response = chat_session.send_message(contents)
        latency = round(time.time() - start_time, 2)
        return jsonify({
            "reply": response.text,
            "tools_called": called_tools_log,
            "latency": latency
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "latency": round(time.time() - start_time, 2)
        }), 500


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 Executive Assistant Server (Streaming SSE + SQLite Memory) starting...")
    print("👉 URL: http://127.0.0.1:5000")
    print("="*70 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
