$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$archive = Join-Path $projectRoot 'artifacts/chrome-stable.zip'
$destination = Join-Path $projectRoot 'artifacts/chrome-stable'
$expected = '4966D9DF2C8ED9BE606FF0FC8877B2E800DEF164FBAD63FED6A1D93222AD9DBF'
New-Item -ItemType Directory -Path (Split-Path -Parent $archive) -Force | Out-Null
if (-not (Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest 'https://storage.googleapis.com/chrome-for-testing-public/155.0.8059.79/win64/chrome-win64.zip' -OutFile $archive
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
    throw 'Chrome for Testing archive checksum mismatch.'
}
if (-not (Test-Path -LiteralPath (Join-Path $destination 'chrome-win64/chrome.exe'))) {
    Expand-Archive -LiteralPath $archive -DestinationPath $destination
}
Write-Output (Join-Path $destination 'chrome-win64/chrome.exe')
