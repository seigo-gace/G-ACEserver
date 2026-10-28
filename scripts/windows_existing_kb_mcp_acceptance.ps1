# Gserver F04: run the EXISTING Windows Dev KB MCP regression probes.
# Explicit owner action only. No new MCP engine, service, task, or KB index.
# This source invokes the official tests already installed under F:\G-ACE-KB.
$ErrorActionPreference = 'Stop'
$root = 'F:\G-ACE-KB'
$runtime = Join-Path $root 'runtime\mcp-vector-search\Scripts\python.exe'
$project = Join-Path $root 'data\knowledge-search'
$metadata = Join-Path $root 'data\knowledge-sources\accepted\modulecatalog-reusable-current\knowledge-metadata.jsonl'
$history = Join-Path $root 'repo\tests\mcp_knowledge_client_e2e.py'
$reusable = Join-Path $root 'repo\tests\mcp_reusable_asset_e2e.py'
$phase = 'PRECHECK'
$ok = $false
$priorWatch = [Environment]::GetEnvironmentVariable('MCP_ENABLE_FILE_WATCHING','Process')
$priorPy = [Environment]::GetEnvironmentVariable('PYTHONDONTWRITEBYTECODE','Process')
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=EXISTING_DEV_KB_WINDOWS_MCP_E2E'
try {
    foreach ($file in @($runtime, $metadata, $history, $reusable)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw 'DEV_KB_RUNTIME_FILE_MISSING'
        }
    }
    if (-not (Test-Path -LiteralPath $project -PathType Container)) {
        throw 'DEV_KB_SEARCH_INDEX_MISSING'
    }
    $marker = Join-Path $root 'data\knowledge-records\modulecatalog-reusable-active.json'
    $state = Join-Path $root 'data\knowledge-sources\accepted\modulecatalog-reusable-current\runtime-state.json'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf) -or
        -not (Test-Path -LiteralPath $state -PathType Leaf)) {
        throw 'DEV_KB_CURRENT_NOT_PRESENT'
    }
    $active = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
    $current = Get-Content -LiteralPath $state -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($active.status -ne 'ACTIVE' -or $current.status -ne 'ACTIVE' -or
        $active.catalogCommit -ne $current.catalogCommit -or
        [int]$active.knowledgeUnitCount -ne [int]$current.knowledgeUnitCount -or
        [int]$active.knowledgeUnitCount -lt 1) {
        throw 'DEV_KB_CURRENT_AUTHORITY_INVALID'
    }
    $count = [int]$active.knowledgeUnitCount
    [Environment]::SetEnvironmentVariable('MCP_ENABLE_FILE_WATCHING','false','Process')
    [Environment]::SetEnvironmentVariable('PYTHONDONTWRITEBYTECODE','1','Process')
    $phase = 'EXISTING_HISTORY_MCP'
    & $runtime -B $history --python $runtime --project-root $project --timeout 180 *> $null
    if ($LASTEXITCODE -ne 0) { throw 'DEV_KB_HISTORY_MCP_E2E_FAILED' }
    Write-Output 'KB_MCP_HISTORY=PASS'
    $phase = 'EXISTING_REUSABLE_MCP'
    & $runtime -B $reusable --python $runtime --project-root $project --metadata $metadata --expected-count $count --timeout 180 *> $null
    if ($LASTEXITCODE -ne 0) { throw 'DEV_KB_REUSABLE_MCP_E2E_FAILED' }
    Write-Output 'KB_MCP_REUSABLE_BM25_VECTOR_HYBRID_KG=PASS'
    Write-Output ('KB_MCP_EXPECTED_REUSABLE=' + $count)
    $ok = $true
} catch {
    Write-Output ('FAILED_PHASE=' + $phase)
    Write-Output ('ERROR_CODE=' + [string]$_.Exception.Message)
} finally {
    [Environment]::SetEnvironmentVariable('MCP_ENABLE_FILE_WATCHING',$priorWatch,'Process')
    [Environment]::SetEnvironmentVariable('PYTHONDONTWRITEBYTECODE',$priorPy,'Process')
    Write-Output 'KB_SOURCE_CONTENTS_INTENTIONALLY_CHANGED=NONE'
    Write-Output 'GSERVER_DOCKER_CHANGED=False'
    Write-Output 'VERIFY=' + $(if ($ok) { 'PASS' } else { 'FAIL' })
    Write-Output 'PROJECT_END=Gserver'
    Write-Output '========== GACE_RESULT_END =========='
}
if (-not $ok) { exit 1 }
