$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$PythonCommand = "python"
$PythonPrefix = @()
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
    $PythonPrefix = @("-3.12")
}

Write-Host "=== Environment ==="
Write-Host "Repository: $RepoRoot"
Write-Host "OS: $([Environment]::OSVersion.VersionString)"
& $PythonCommand @PythonPrefix -c "import sys, sqlite3; assert sys.version_info[:2] == (3, 12), 'Expected Python 3.12.x'; print('Python:', sys.version.replace(chr(10), ' ')); print('SQLite:', sqlite3.sqlite_version)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12 is unavailable or failed to start."
}

Write-Host ""
Write-Host "=== Compile check ==="
& $PythonCommand @PythonPrefix -m compileall -q core tests
if ($LASTEXITCODE -ne 0) {
    throw "compileall failed."
}
Write-Host "compileall passed."

Write-Host ""
Write-Host "=== Full test suite ==="
& $PythonCommand @PythonPrefix -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    throw "The full test suite failed."
}

Write-Host ""
Write-Host "All local Windows verification steps passed."
