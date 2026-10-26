@echo off
where node >nul 2>nul
if errorlevel 1 (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" "%~dp0launch.mjs" --update-only %*
) else (
  node "%~dp0launch.mjs" --update-only %*
)
if errorlevel 1 pause
