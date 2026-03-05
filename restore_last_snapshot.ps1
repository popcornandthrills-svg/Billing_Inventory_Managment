param(
  [string]$SnapshotPath = ""
)
$project = "C:\Users\bhara\OneDrive\Desktop\Projects\BS5.6 - Edited v2"
$rollbackRoot = Join-Path $project "_rollback"
if([string]::IsNullOrWhiteSpace($SnapshotPath)){
  $latestFile = Join-Path $rollbackRoot "LATEST.txt"
  if(!(Test-Path $latestFile)){ throw "LATEST snapshot pointer not found." }
  $SnapshotPath = (Get-Content $latestFile -Raw).Trim()
}
if(!(Test-Path $SnapshotPath)){ throw "Snapshot not found: $SnapshotPath" }
robocopy $SnapshotPath $project /E /XD _rollback /XF restore_last_snapshot.ps1 *.pyc > $null
if($LASTEXITCODE -ge 8){ throw "Restore failed with robocopy exit code $LASTEXITCODE" }
Write-Host "Restore completed from: $SnapshotPath"
