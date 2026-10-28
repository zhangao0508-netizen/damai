param([string]$Tag='', [switch]$SkipBuild)
. "$PSScriptRoot/common.ps1"
if(!$Tag){$Tag=((& git -C $RepoRoot rev-parse --short=12 HEAD).Trim())+'-'+(Get-Date -Format yyyyMMddHHmmss)}
Push-Location $RepoRoot
try {
  if($Tag -notmatch '^[A-Za-z0-9_.-]+$'){throw 'Invalid image tag'}
  Invoke-Checked kubectl @('--context','kind-demo-lab','cluster-info')
  if(!$SkipBuild){
    $jdk=if($env:DAMAI_JAVA_HOME){$env:DAMAI_JAVA_HOME}else{'D:/dev/jdk/jdk17'}
    $env:JAVA_HOME=$jdk; $env:PATH="$jdk/bin;$env:PATH"
    Invoke-Checked mvn @('-B','-DskipTests','package')
    foreach($service in @('gateway','base-data','user','program','order','pay','customize','admin')){
      Invoke-Checked docker @('build','--provenance=false','-f','ops/Dockerfile','--build-arg',"SERVICE=$service",'-t',"damai/${service}:$Tag",'.')
    }
    Invoke-Checked docker @('build','--provenance=false','-f','ops/Dockerfile.web','-t',"damai/web:$Tag",'.')
  }
  Invoke-Checked (Get-LabPython) @('ops/render.py',$Tag)
  # Only this project's explicitly named Docker stack; never existing MySQL containers.
  Invoke-Checked docker @('compose','--env-file',"$LocalRoot/compose.env",'-f','ops/.generated/compose.json','up','-d')
  $attached=& docker inspect demo-lab-control-plane --format '{{json .NetworkSettings.Networks}}'
  if($LASTEXITCODE -ne 0){throw 'Local kind node missing'}
  if(!$attached.Contains('damai-lab')){Invoke-Checked docker @('network','connect','damai-lab','demo-lab-control-plane')}
  Invoke-Checked kubectl @('--context','kind-demo-lab','apply','--server-side','-f','ops/.generated/infra.json')
  $images=@('gateway','base-data','user','program','order','pay','customize','admin','web') | ForEach-Object {"damai/${_}:$Tag"}
  Invoke-Checked kind (@('load','docker-image','--name','demo-lab')+$images)
  Invoke-Checked kubectl @('--context','kind-demo-lab','apply','--server-side','-f','ops/.generated/apps.json')
  foreach($service in @('base-data','user','program','order','pay','customize','gateway','admin')){
    Invoke-Checked kubectl @('--context','kind-demo-lab','-n','damai-dev','rollout','status',"deployment/damai-$service-service",'--timeout=600s')
  }
  Invoke-Checked kubectl @('--context','kind-demo-lab','-n','damai-dev','rollout','status','deployment/damai-web','--timeout=180s')
  & "$PSScriptRoot/smoke.ps1"
} finally {Pop-Location}

