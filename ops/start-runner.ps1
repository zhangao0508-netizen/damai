. "$PSScriptRoot/common.ps1"
$proxy=& git -C $RepoRoot config --get-urlmatch http.proxy https://github.com
if($proxy){$env:https_proxy=$proxy.Trim();$env:http_proxy=$proxy.Trim();$env:no_proxy='localhost,127.0.0.1,::1'}
if(!(Test-Path "$LocalRoot/runner/.runner")){throw 'Run ops/setup-runner.ps1 first'}
Push-Location "$LocalRoot/runner"
try{& ./run.cmd}finally{Pop-Location}
