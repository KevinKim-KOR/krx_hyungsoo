<#
  Nightly GPU Backtest Runner (Windows PowerShell)
  - Pre-req: Anaconda Prompt(권장) 또는 conda 초기화 완료된 PowerShell
  - Env   : krxbt311 (Python 3.11), repo root는 E:\AI Study\krx_alertor_modular
  - Do    : (옵션)캐시→백테스트→재현성검사→패키징→NAS 업로드→웹훅 호출
#>

param(
  [string]$RepoRoot = "E:\AI Study\krx_alertor_modular",
  [string]$EnvName  = "krxbt311",
  [string]$NasHost  = "192.168.0.10",   # ← NAS IP/호스트명
  [string]$NasUser  = "Hyungsoo",
  [string]$NasRepo  = "/volume2/homes/Hyungsoo/krx/krx_alertor_modular",
  [switch]$DoBootstrap = $false         # 캐시 부트스트랩 수행 여부
)

# --- Helper
function Die($msg){ Write-Error $msg; exit 1 }
function Run($cmd){ Write-Host ">> $cmd" -ForegroundColor Cyan; iex $cmd; if($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0){ Die "Command failed: $cmd" } }

# --- Check paths
if(-not (Test-Path $RepoRoot)){ Die "RepoRoot not found: $RepoRoot" }
Set-Location $RepoRoot

# --- Activate conda env
# Anaconda Prompt 권장. PowerShell에서도 conda 초기화된 상태여야 함.
Write-Host "Activating conda env: $EnvName"
conda activate $EnvName | Out-Null

# --- Timestamp & Out dirs
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$pkgRoot = Join-Path $RepoRoot "reports\backtests\$ts`_v1"
$inboxLocal = $pkgRoot
$newItem = New-Item -ItemType Directory -Path $inboxLocal -Force

# --- (옵션) 캐시 부트스트랩
if($DoBootstrap){
  Run "python tools/bootstrap_cache_pc.py --tickers KRALL --since 2018-01-01"
}

# --- Backtest (베이스라인 1회 + 재현성 검사용 2회 더)
$bt1 = Join-Path $pkgRoot "equity1.csv"
$bt2 = Join-Path $pkgRoot "equity2.csv"
$bt3 = Join-Path $pkgRoot "equity3.csv"

# NOTE: backtest_cli.py는 v1 기준(score_abs, Top5, 주간 리밸런스) 구현 전제
Run "python backtest_cli.py --start 2018-01-02 --end (Get-Date).AddDays(-1).ToString('yyyy-MM-dd') --mode score_abs --wl 1 --top 5 --out `"$bt1`""
Run "python backtest_cli.py --start 2018-01-02 --end (Get-Date).AddDays(-1).ToString('yyyy-MM-dd') --mode score_abs --wl 1 --top 5 --out `"$bt2`""
Run "python backtest_cli.py --start 2018-01-02 --end (Get-Date).AddDays(-1).ToString('yyyy-MM-dd') --mode score_abs --wl 1 --top 5 --out `"$bt3`""

# --- 재현성 검사
Run "python tools/hash_compare.py `"$bt1`" `"$bt2`" `"$bt3`""

# --- 요약/메타(예시) 생성
$summaryJson = Join-Path $pkgRoot "summary.json"
$manifest    = Join-Path $pkgRoot "manifest.json"

# 간단 요약 생성(필요 시 backtest_cli가 JSON도 직접 생성하도록 향후 변경)
@"
{
  "strategy_id": "v1_score_abs_top5",
  "params": {"lookbacks":[21,63,126],"weights":[1,2,3],"top":5,"regime":"KODEX200_SMA200","cap":"vol20_top15pct_half"},
  "created_at": "$((Get-Date).ToString("s"))",
  "timezone": "Asia/Seoul",
  "files": ["equity1.csv","equity2.csv","equity3.csv"]
}
"@ | Out-File -FilePath $summaryJson -Encoding UTF8

# git 커밋 해시
$gitrev = (git rev-parse HEAD) 2>$null
if(-not $gitrev){ $gitrev = "unknown" }

@"
{
  "repo":  "krx_alertor_modular",
  "commit": "$gitrev",
  "package_ts": "$ts",
  "producer": "pc-nightly",
  "schema": "btpkg/1.0",
  "entrypoints": {"equity":"equity1.csv","summary":"summary.json"}
}
"@ | Out-File -FilePath $manifest -Encoding UTF8

# --- SHA256SUMS
$shaFile = Join-Path $pkgRoot "SHA256SUMS"
Remove-Item $shaFile -ErrorAction Ignore
Get-ChildItem $pkgRoot -File | ForEach-Object {
  $h = Get-FileHash $_.FullName -Algorithm SHA256
  "$($h.Hash)  $($_.Name)" | Out-File -FilePath $shaFile -Append -Encoding ascii
}

# --- 업로드(scp) → NAS inbox
$nasInbox = "$NasRepo/reports/backtests/inbox/$ts`_v1"
Run "scp -r `"$pkgRoot`" ${NasUser}@${NasHost}:$nasInbox"

# --- NAS 웹훅 호출
$payload = @{ path = "$nasInbox"; strategy_id = "v1_score_abs_top5"; ts = "$ts" } | ConvertTo-Json -Depth 4
Run "curl -s -X POST http://$NasHost:8899/bt/inbox/notify -H `"Content-Type: application/json`" -d '$payload'"

Write-Host "Nightly backtest package uploaded & notified." -ForegroundColor Green
