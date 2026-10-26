$ErrorActionPreference = 'Stop'
$taskNode = (Get-Command node -ErrorAction Stop).Source
& $taskNode (Join-Path $PSScriptRoot 'launch.mjs') --close
if ($LASTEXITCODE -ne 0) { throw 'Launch Quest operation failed.' }
