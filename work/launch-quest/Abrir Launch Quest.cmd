@echo off
where node >nul 2>nul
if errorlevel 1 (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" "%~dp0launch.mjs" %*
) else (
  node "%~dp0launch.mjs" %*
)
if errorlevel 1 pause
