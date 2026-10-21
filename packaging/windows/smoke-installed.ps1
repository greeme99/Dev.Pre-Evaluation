param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir,
    [string]$FixturePath = "tests/fixtures/dxf/missing-xref.dxf"
)

$ErrorActionPreference = "Stop"
$baseUrl = "http://127.0.0.1:17841"
$executable = Join-Path $InstallDir "DevPreReview.exe"

if (-not (Test-Path $executable)) {
    throw "Installed executable not found: $executable"
}
if (-not (Test-Path $FixturePath)) {
    throw "Workflow fixture not found: $FixturePath"
}

$env:DEV_PRE_REVIEW_DATA_DIR = Join-Path $env:RUNNER_TEMP "dev-pre-review-smoke-data"
$process = Start-Process -FilePath $executable -PassThru

try {
    $health = $null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 2
            if ($health.product -eq "dev-pre-review" -and $health.status -eq "ok") {
                break
            }
            $health = $null
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    if ($null -eq $health) {
        throw "Installed application did not report the expected health identity"
    }

    $ui = Invoke-WebRequest -Uri $baseUrl -TimeoutSec 10
    if ($ui.StatusCode -ne 200 -or $ui.Content -notmatch 'id="root"') {
        throw "Bundled web UI did not load"
    }
    $assetPaths = [regex]::Matches(
        $ui.Content,
        '(?:src|href)="(?<path>/assets/[^"]+)"'
    ) | ForEach-Object { $_.Groups["path"].Value } | Sort-Object -Unique
    if ($assetPaths.Count -lt 2) {
        throw "Bundled UI did not reference both JavaScript and CSS assets"
    }
    foreach ($assetPath in $assetPaths) {
        $asset = Invoke-WebRequest -Uri "$baseUrl$assetPath" -TimeoutSec 10
        if ($asset.StatusCode -ne 200 -or $asset.RawContentLength -le 0) {
            throw "Bundled UI asset failed to load: $assetPath"
        }
    }

    $edgeCandidates = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
    $edge = $edgeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($null -eq $edge) {
        throw "Microsoft Edge was not found for the rendered UI smoke check"
    }
    $renderedDom = & $edge --headless --disable-gpu --no-first-run --dump-dom $baseUrl
    if ($LASTEXITCODE -ne 0 -or ($renderedDom -join "`n") -notmatch 'class="app-shell"') {
        throw "React UI did not render in headless Edge"
    }

    $project = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/projects" `
        -ContentType "application/json" -Body '{"name":"Windows release smoke"}'
    $drawing = Invoke-RestMethod -Method Post `
        -Uri "$baseUrl/api/projects/$($project.id)/drawings" `
        -Form @{ file = Get-Item $FixturePath }
    $job = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/analyses" `
        -ContentType "application/json" `
        -Body (@{ project_id = $project.id; drawing_id = $drawing.id } | ConvertTo-Json)

    for ($attempt = 0; $attempt -lt 60 -and $job.state -notin @("completed", "failed", "cancelled"); $attempt++) {
        Start-Sleep -Seconds 1
        $job = Invoke-RestMethod -Uri "$baseUrl/api/analyses/$($job.id)"
    }
    if ($job.state -ne "completed") {
        throw "Minimal analysis workflow ended in state '$($job.state)'"
    }

    $findings = Invoke-RestMethod -Uri "$baseUrl/api/analyses/$($job.id)/findings"
    if ($findings.job_id -ne $job.id) {
        throw "Findings response did not match the analysis job"
    }
    $export = Invoke-WebRequest -Uri "$baseUrl/api/analyses/$($job.id)/export.csv"
    if ($export.StatusCode -ne 200 -or $export.Headers["Content-Type"] -notmatch "text/csv") {
        throw "CSV export smoke check failed"
    }
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
