param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$taskNode = (Get-Command node -ErrorAction Stop).Source
$taskArguments = @((Join-Path $PSScriptRoot 'launch.mjs'))
if ($NoBrowser) { $taskArguments += '--no-browser' }
& $taskNode @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Launch Quest could not start; inspect the reported dependency.' }