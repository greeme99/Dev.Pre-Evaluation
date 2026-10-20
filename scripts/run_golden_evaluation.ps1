<#
.SYNOPSIS
    Runs golden set quality benchmark on local Windows environment (TC-101, TC-102).

.DESCRIPTION
    Executes the golden set evaluation pipeline against specified manifest and
    enforces quality gate thresholds (Precision >= 90%, Recall >= 80%, Top-5 >= 80%, P95 <= 180s).

.PARAMETER ManifestPath
    Path to golden set manifest JSON file.

.PARAMETER Split
    Dataset split to evaluate ('tuning' or 'final'). Default: 'final'.

.PARAMETER OutputReport
    Output path for report file. Default: 'artifacts\golden_report.md'.

.PARAMETER Format
    Report format ('markdown' or 'json'). Default: 'markdown'.
#>

param(
    [string]$ManifestPath = "tests\golden\manifest.json",
    [string]$Split = "final",
    [string]$OutputReport = "artifacts\golden_report.md",
    [string]$Format = "markdown"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Dev.Pre-Evaluation Golden Set Quality Benchmark (TC-102) " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Manifest: $ManifestPath"
Write-Host "Split:    $Split"
Write-Host "Output:   $OutputReport"
Write-Host "Format:   $Format"
Write-Host ""

if (-not (Test-Path $ManifestPath)) {
    Write-Error "Manifest file not found: $ManifestPath"
    exit 2
}

$env:PYTHONPATH = "apps\api\src"

# Run via uv python runner
uv run python -m dev_pre_review.evaluation.cli `
    --manifest $ManifestPath `
    --split $Split `
    --output $OutputReport `
    --format $Format

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "[PASS] Quality gates satisfied." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[FAIL] Quality gates violated or benchmark failed (Exit Code: $exitCode)." -ForegroundColor Red
}

exit $exitCode
