import os
import sys
import time

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from google import genai
from google.genai import errors

# Load secret environment variables
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "YOUR_API_KEY_HERE":
    print("ERROR: GEMINI_API_KEY is missing or not set in .env")
    exit(1)

client = genai.Client(api_key=api_key)

prompt = (
    "As an Enterprise Cloud Architect, explain the business and operational "
    "trade-offs of deploying a Self-Hosted LLM (like Llama 3 on private GPUs) "
    "vs. using a Managed Serverless LLM API (like Gemini Flash) for an IT support ticketing system. "
    "Keep it concise, high-level, and formatted in 3 key bullet points."
)

print("\n" + "="*75)
print("[STEP 3] ENTERPRISE INFERENCE & TOKEN ECONOMICS")
print("="*75)

# AI Leader Principle: Resilience & Fallback Routing
models_to_try = ["gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-3.8-flash"]
response = None
chosen_model = None
latency = 0.0

for model_name in models_to_try:
    print(f"Attempting inference on: {model_name} ...")
    start_time = time.time()
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        latency = round(time.time() - start_time, 2)
        chosen_model = model_name
        print(f"-> Connected successfully to {model_name} in {latency}s!\n")
        break
    except errors.APIError as e:
        print(f"-> Model {model_name} busy or unavailable (Status {e.code}). Failing over to next model...")

if not response:
    print("All candidate models currently unreachable.")
    exit(1)

print("-" * 75)
print("[ARCHITECTURAL RESPONSE]")
print("-" * 75)
print(response.text)
print("-" * 75)

# Extract Token & Financial Metrics
usage = response.usage_metadata
prompt_tokens = usage.prompt_token_count
completion_tokens = usage.candidates_token_count
total_tokens = usage.total_token_count

# Standard Enterprise Pricing Reference ($0.075 / 1M input, $0.30 / 1M output)
est_enterprise_cost = (prompt_tokens * 0.000000075) + (completion_tokens * 0.00000030)

print("\n[AI LEADERSHIP SCORECARD: TOKEN ECONOMICS & EFFICIENCY]")
print(f"* Model Utilized           : {chosen_model}")
print(f"* End-to-End Latency       : {latency} seconds")
print(f"* Input (Prompt) Tokens    : {prompt_tokens}")
print(f"* Output (Response) Tokens : {completion_tokens}")
print(f"* Total Tokens Consumed    : {total_tokens}")
print(f"* Your Actual Cost         : $0.00 (100% Free Tier)")
print(f"* Enterprise Production Est: ${est_enterprise_cost:.8f} (Only ~$0.00007 for this analysis)")
print("="*75 + "\n")
