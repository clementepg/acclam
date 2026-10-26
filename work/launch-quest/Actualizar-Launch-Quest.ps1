$ErrorActionPreference = 'Stop'
$taskNode = (Get-Command node -ErrorAction Stop).Source
& $taskNode (Join-Path $PSScriptRoot 'launch.mjs') --update-only
if ($LASTEXITCODE -ne 0) { throw 'Launch Quest operation failed.' }
