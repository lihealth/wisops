param(
  [string]$LogHubRepo = "C:\Users\lijian22\loghub",
  [string]$OutputDir = "C:\Users\lijian22\wisops\data\loghub\raw"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $LogHubRepo)) {
  throw "LogHub repo path not found: $LogHubRepo"
}

if (-not (Test-Path -LiteralPath $OutputDir)) {
  New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$allowedExt = @(".log", ".txt", ".out")

Write-Host "Source: $LogHubRepo"
Write-Host "Target: $OutputDir"
Write-Host "Extensions: $($allowedExt -join ', ')"

$files = Get-ChildItem -Path $LogHubRepo -Recurse -File |
  Where-Object { $allowedExt -contains $_.Extension.ToLower() }

if (($null -eq $files) -or ($files.Count -eq 0)) {
  Write-Warning "No .log/.txt/.out files found."
  exit 0
}

$copied = 0
$skipped = 0
$root = $LogHubRepo.TrimEnd('\')

foreach ($file in $files) {
  $relative = $file.FullName.Substring($root.Length).TrimStart('\')
  $targetFile = Join-Path $OutputDir $relative
  $targetDir = Split-Path -Parent $targetFile

  if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
  }

  if (Test-Path -LiteralPath $targetFile) {
    $srcInfo = Get-Item -LiteralPath $file.FullName
    $dstInfo = Get-Item -LiteralPath $targetFile
    if (($srcInfo.Length -eq $dstInfo.Length) -and ($srcInfo.LastWriteTimeUtc -eq $dstInfo.LastWriteTimeUtc)) {
      $skipped++
      continue
    }
  }

  Copy-Item -LiteralPath $file.FullName -Destination $targetFile -Force
  $copied++
}

Write-Host "----------------------------------------"
Write-Host "Scanned files: $($files.Count)"
Write-Host "Copied/Updated: $copied"
Write-Host "Skipped (unchanged): $skipped"
Write-Host "Done."

