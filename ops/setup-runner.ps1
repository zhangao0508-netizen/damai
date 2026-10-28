param([string]$Repository = 'zhangao0508-netizen/damai')
. "$PSScriptRoot/common.ps1"
$runner = Join-Path $LocalRoot 'runner'
New-Item -ItemType Directory -Force $runner | Out-Null
if (Test-Path "$runner/.runner") { Write-Host 'Runner already registered.'; exit 0 }
# Reuse Git Credential Manager in memory; never print or persist the credential.
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'never'
$credential = @{}
"protocol=https`nhost=github.com`n`n" | & git credential fill | ForEach-Object {
    $parts = $_ -split '=',2
    if ($parts.Count -eq 2) { $credential[$parts[0]] = $parts[1] }
}
if (!$credential.password) { throw 'No GitHub credential available. Sign in with Git Credential Manager, then retry.' }
$headers = @{Authorization="Bearer $($credential.password)"; Accept='application/vnd.github+json'; 'X-GitHub-Api-Version'='2022-11-28'}
try {
    $registration = Invoke-RestMethod "https://api.github.com/repos/$Repository/actions/runners/registration-token" -Method Post -Headers $headers
    $downloads = Invoke-RestMethod "https://api.github.com/repos/$Repository/actions/runners/downloads" -Headers $headers
    $package = $downloads | Where-Object { $_.os -eq 'win' -and $_.architecture -eq 'x64' } | Select-Object -First 1
    if (!$package.download_url -or !$package.sha256_checksum) { throw 'Runner download metadata missing' }
    $zip = Join-Path $LocalRoot 'runner.zip'
    if (!(Test-Path $zip) -or (Get-FileHash $zip -Algorithm SHA256).Hash -ne $package.sha256_checksum) { Invoke-WebRequest $package.download_url -OutFile $zip -UseBasicParsing }
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $package.sha256_checksum) { throw 'Runner checksum mismatch' }
    Expand-Archive $zip -DestinationPath $runner -Force
    Push-Location $runner
    try {
        Invoke-Checked ./config.cmd @('--unattended','--url',"https://github.com/$Repository",'--token',$registration.token,'--name',"damai-local-$env:COMPUTERNAME",'--labels','damai-local','--work','_work')
    } finally { Pop-Location }
    Write-Host 'Registered. Start with: powershell -ExecutionPolicy Bypass -File ops/start-runner.ps1'
} finally {
    $headers.Clear(); $credential.Clear(); $registration = $null
    Remove-Item Env:GIT_TERMINAL_PROMPT,Env:GCM_INTERACTIVE -ErrorAction SilentlyContinue
}

