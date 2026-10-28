. "$PSScriptRoot/common.ps1"
# Validate from inside Kubernetes so CI does not rely on a desktop port-forward.
$pod=(& kubectl --context kind-demo-lab -n damai-dev get pod -l app=damai-web -o 'jsonpath={.items[0].metadata.name}')
if($LASTEXITCODE -ne 0 -or !$pod){throw 'Web pod missing'}
foreach($service in @(@('base-data','6083'),@('user','6082'),@('program','6086'),@('order','6081'),@('pay','6087'),@('customize','6084'),@('gateway','6085'),@('admin','6080'))){
  $name=$service[0];$port=$service[1]
  $result=& kubectl --context kind-demo-lab -n damai-dev exec $pod -- wget -qO- "http://damai-$name-service`:$port/actuator/health/readiness"
  if($LASTEXITCODE -ne 0 -or ($result|ConvertFrom-Json).status -ne 'UP'){throw "$name readiness failed"}
}
Write-Host 'All eight application readiness checks passed.'
function Invoke-BusinessQuery {
  param([string]$Path,[string]$Body)
  $text=& kubectl --context kind-demo-lab -n damai-dev exec $pod -- wget -qO- --header 'Content-Type: application/json' --header 'no_verify: true' --post-data $Body "http://127.0.0.1/api/$Path"
  if($LASTEXITCODE -ne 0){throw "Business query HTTP failed: $Path"}
  $result=($text -join "`n")|ConvertFrom-Json
  if($result.code -ne 0){throw "Business query failed: $Path code=$($result.code)"}
  return $result.data
}
$cities=@(Invoke-BusinessQuery 'damai/basedata/area/selectCityData' '{}')
if($cities.Count -lt 1){throw 'City data is empty'}
$categories=@(Invoke-BusinessQuery 'damai/program/program/category/selectByType' '{"type":1}')
if($categories.Count -lt 4){throw 'Program categories missing'}
$expected=([string][char]0x6f14)+[char]0x5531+[char]0x4f1a
if(@($categories|Where-Object name -EQ $expected).Count -ne 1){throw 'Chinese text encoding check failed'}
$ids=@($categories|Select-Object -First 4|ForEach-Object{$_.id})
$body=@{areaId=$null;parentProgramCategoryIds=$ids}|ConvertTo-Json -Compress
$programs=@(Invoke-BusinessQuery 'damai/program/program/home/list' $body)
if($programs.Count -lt 1){throw 'Program home data is empty'}
Write-Host "Business checks passed: $($cities.Count) cities, $($categories.Count) categories, $($programs.Count) program groups."
