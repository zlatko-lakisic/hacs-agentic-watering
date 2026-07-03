# Install Agentic Watering into a Home Assistant config folder.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/install-to-ha.ps1 -ConfigRoot '\\your-ha-host\config'

param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$srcIntegration = Join-Path $repoRoot 'custom_components\agentic_watering'
$dstIntegration = Join-Path $ConfigRoot 'custom_components\agentic_watering'
$srcBlueprint = Join-Path $repoRoot 'blueprints\automation\zlatko-lakisic\smart_sequential_watering.yaml'
$dstBlueprintDir = Join-Path $ConfigRoot 'blueprints\automation\zlatko-lakisic'
$dstBlueprint = Join-Path $dstBlueprintDir 'smart_sequential_watering.yaml'

if (-not (Test-Path $srcIntegration)) {
    throw "Integration source not found: $srcIntegration"
}
if (-not (Test-Path $ConfigRoot)) {
    throw "Home Assistant config path not reachable: $ConfigRoot"
}

New-Item -ItemType Directory -Force -Path $dstIntegration | Out-Null
Copy-Item -Path (Join-Path $srcIntegration '*') -Destination $dstIntegration -Recurse -Force

New-Item -ItemType Directory -Force -Path $dstBlueprintDir | Out-Null
Copy-Item -Path $srcBlueprint -Destination $dstBlueprint -Force

Write-Host "Installed integration to $dstIntegration"
Write-Host "Installed blueprint to $dstBlueprint"
Write-Host "Add package includes from docs/INSTALL.md to configuration.yaml, then restart Home Assistant."
