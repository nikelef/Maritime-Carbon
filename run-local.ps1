param([switch]$Install)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
    $Install = $true
}
if ($Install) {
    python -m pip --python $taskPython install -r requirements-web.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$env:DJANGO_DEBUG = '1'
& $taskPython manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
Write-Host 'Customer application: http://127.0.0.1:8000/'
Write-Host 'Illustrative preview: http://127.0.0.1:8000/demo/'
Write-Host 'Create your first account using the provision_company command in README.md.'
& $taskPython manage.py runserver 127.0.0.1:8000
