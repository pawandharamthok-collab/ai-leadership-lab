$target = "C:\Users\Pawan Dharamthok\Desktop\ai-leadership-lab"
Set-Location $target

if (-not (Test-Path "$target\.venv")) {
    Write-Host "Creating virtual environment (.venv)..."
    python -m venv .venv
}

Write-Host "Installing google-genai and python-dotenv..."
& "$target\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& "$target\.venv\Scripts\python.exe" -m pip install --quiet google-genai python-dotenv

Write-Host "Verification:"
& "$target\.venv\Scripts\python.exe" -c "import google.genai, dotenv; print('Dependencies successfully verified!')"
