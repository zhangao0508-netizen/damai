$ErrorActionPreference='Stop'
$RepoRoot=Split-Path $PSScriptRoot -Parent
$LocalRoot=if($env:DAMAI_LAB_HOME){$env:DAMAI_LAB_HOME}else{Join-Path $RepoRoot '.local'}
$env:DAMAI_LAB_HOME=$LocalRoot
$env:KUBECONFIG=Join-Path $LocalRoot 'kubeconfig'
$env:PATH="$LocalRoot/bin;$env:PATH"
function Invoke-Checked {
  param([string]$File,[string[]]$Arguments)
  & $File @Arguments
  if($LASTEXITCODE -ne 0){throw "$File failed with exit $LASTEXITCODE"}
}
function Get-LabPython {
  if($env:DAMAI_PYTHON){return $env:DAMAI_PYTHON}
  $bundled=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
  if(Test-Path $bundled){return $bundled}
  return 'python'
}
