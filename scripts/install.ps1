[CmdletBinding()]
param(
    [string]$Python = 'python',
    [switch]$Dev
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $runtime)) {
    & $Python -c 'import struct, sys; assert sys.platform == "win32" and struct.calcsize("P") == 8 and (3, 10) <= sys.version_info[:2] < (3, 14), "Use Windows Python 3.10-3.13 x64"'
    if ($LASTEXITCODE -ne 0) { throw 'Python runtime check failed.' }
    & $Python -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}

$package = $projectRoot
if ($Dev) { $package = "$projectRoot[dev]" }
& $runtime -m pip install -e $package
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
& $runtime -m spirit_computer_use doctor
if ($LASTEXITCODE -ne 0) { throw 'Desktop diagnostics failed.' }

$outputDirectory = Join-Path $projectRoot 'artifacts/integrations'
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$utf8 = [System.Text.UTF8Encoding]::new($false)
foreach ($client in @('codex', 'claude', 'opencode', 'antigravity', 'cursor', 'vscode', 'generic')) {
    $content = & $runtime -m spirit_computer_use config $client
    if ($LASTEXITCODE -ne 0) { throw "Configuration generation failed for $client." }
    $extension = if ($client -eq 'codex') { 'toml' } else { 'json' }
    $destination = Join-Path $outputDirectory "$client.$extension"
    [System.IO.File]::WriteAllText($destination, ($content -join "`n") + "`n", $utf8)
}
Write-Host "SPIRIT installed. Client configuration snippets: $outputDirectory"
Write-Host 'See docs/clients.md for client-specific setup. Existing client settings were not edited.'
