param(
    [switch]$AllowOcr
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pdfDirectory = Join-Path $projectRoot 'data/raw/bank_analytics'
$manifestPath = Join-Path $projectRoot 'data/ocr_cache/bank_materials.json'
New-Item -ItemType Directory -Path $pdfDirectory -Force | Out-Null
$pdfs = @(Get-ChildItem -LiteralPath $pdfDirectory -File -Filter '*.pdf')
if ($pdfs.Count -eq 0) {
    throw "В $pdfDirectory нет PDF. Сначала положите туда согласованные материалы Альфа-Банка."
}

Push-Location $projectRoot
try {
    $configuredManifest = (& docker compose exec -T backend python -c 'from app.settings import Settings; print(Settings().bank_materials_path)' | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Backend недоступен. Запустите docker compose up -d.' }
    if ($configuredManifest) { throw 'В Backend задан BANK_MATERIALS_PATH. Уберите DOCKER_BANK_MATERIALS_PATH из окружения, чтобы использовать манифест индексатора.' }
    $dockerArguments = @('compose', 'exec', '-T', 'backend', 'python', '-m', 'app.services.rag', '--limit', '100')
    if ($AllowOcr) { $dockerArguments += '--allow-ocr' }
    $output = & docker @dockerArguments
    if ($LASTEXITCODE -ne 0) { throw 'Индексация не завершилась. Проверьте сообщения Docker и состояние backend.' }
    $result = $output | Select-Object -Last 1 | ConvertFrom-Json
    $pending = @($result.pending | Where-Object { $_ })
    if ($pending.Count -gt 0) {
        throw "Есть PDF без распознанных страниц: $($pending -join ', '). Если это сканы, повторите запуск с -AllowOcr после согласования затрат."
    }
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Индексатор не создал манифест материалов банка.' }
    $documents = @(Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json)
    if ($documents.Count -eq 0) { throw 'Манифест пуст: проверьте, что PDF содержат извлекаемый текст.' }
    $indexed = @($result.indexed | Where-Object { $_ })
    "Готово: PDF=$($pdfs.Count), документов в манифесте=$($documents.Count), новых в индексе=$($indexed.Count)."
    'Следующий разбор новости сможет использовать эти материалы; существующие completed-разборы сами не обновятся.'
} finally {
    Pop-Location
}
