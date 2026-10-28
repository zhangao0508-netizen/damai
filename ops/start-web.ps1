. "$PSScriptRoot/common.ps1"
Push-Location $RepoRoot
try {
  Invoke-Checked docker @('compose','--env-file',"$LocalRoot/compose.env",'-f','ops/.generated/compose.json','up','-d','entry')
  Write-Host 'Open http://127.0.0.1:18090 . The Docker entry stays running in the background.'
} finally {Pop-Location}
