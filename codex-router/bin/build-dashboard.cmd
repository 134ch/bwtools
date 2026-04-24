@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-dashboard.ps1" %*
