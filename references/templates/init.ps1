param(
  [string]$HarnessDir = (Get-Location).Path
)
$ErrorActionPreference = 'Stop'
$HarnessDir = (Resolve-Path -LiteralPath $HarnessDir).Path
$tasksPath = Join-Path $HarnessDir 'tasks.json'
if(-not (Test-Path -LiteralPath $tasksPath -PathType Leaf)){
  Write-Output 'tasks.json 不存在，先进入相 1 设计。'
  exit 0
}

$json = Get-Content -LiteralPath $tasksPath -Raw -Encoding UTF8 | ConvertFrom-Json
if($null -eq $json.tasks){ throw 'tasks.json 缺少 tasks 数组。' }
$tasks = @($json.tasks)
$ids = @{}
foreach($t in $tasks){
  if([string]::IsNullOrWhiteSpace([string]$t.id)){ throw '存在缺少 id 的任务。' }
  if($ids.ContainsKey([string]$t.id)){ throw "重复任务 id: $($t.id)" }
  $ids[[string]$t.id] = $t
  if($null -eq $t.status){ throw "任务 $($t.id) 缺少 status。" }
}
$passed = @($tasks | Where-Object status -eq 'passed')
$ready = @($tasks | Where-Object status -eq 'evidence_ready')
$blocked = @($tasks | Where-Object status -eq 'blocked')
$rev = 1
if($null -ne $json.rev){ $rev = [int]$json.rev }
Write-Output "PROGRESS: $($passed.Count)/$($tasks.Count)  rev=$rev"
if($ready.Count -gt 0){ Write-Output "待独立评审: $((@($ready | ForEach-Object id)) -join ', ')" }
if($blocked.Count -gt 0){ Write-Output "阻塞: $((@($blocked | ForEach-Object id)) -join ', ')" }

$eligible = @($tasks | Where-Object {
  $stateOk = ($_.status -eq 'pending' -or $_.status -eq 'regressed')
  $deps = @($_.depends_on | Where-Object { $null -ne $_ -and -not [string]::IsNullOrWhiteSpace([string]$_) })
  $depsOk = $true
  foreach($dep in $deps){
    if(-not $ids.ContainsKey([string]$dep) -or $ids[[string]$dep].status -ne 'passed') { $depsOk = $false; break }
  }
  $stateOk -and $depsOk
} | Sort-Object {[int]$_.priority})
if($tasks.Count -gt 0 -and $passed.Count -eq $tasks.Count){
  Write-Output 'EXIT_SIGNAL: true  — 全部任务已通过。'
}elseif($eligible.Count -gt 0){
  $t = $eligible[0]
  Write-Output "`n下一个任务 (置 active):"
  Write-Output "  [$($t.id)] P$($t.priority): $($t.desc)"
  Write-Output "  verify: $($t.verify)"
  if(@($t.depends_on).Count -gt 0){ Write-Output "  depends_on: $((@($t.depends_on)) -join ', ') (已满足)" }
}else{
  Write-Output "`n无 eligible 任务：均处于评审中/阻塞/依赖未满足。先处理上面列出的项。"
}
Write-Output ''
Write-Output '提醒: 只推进这一个任务；完成后追加 evidence.jsonl、置 evidence_ready，并输出 HARNESS_STATUS。'

