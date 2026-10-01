# Gera .\config\* a partir de .\templates\*.tmpl usando as variaveis do .env
#
# Uso (na pasta voip\livekit-local):
#   .\scripts\render-config.ps1            # renderiza
#   .\scripts\render-config.ps1 -GenKeys   # preenche chaves vazias no .env e renderiza
#
# Se o PowerShell bloquear scripts:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
param([switch]$GenKeys)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env'
$utf8 = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path $envFile)) {
    throw ".env nao encontrado. Rode: Copy-Item .env.example .env"
}

function New-Secret([int]$bytes) {
    $b = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return $b
}

function Read-EnvFile {
    $vars = [ordered]@{}
    foreach ($line in [System.IO.File]::ReadAllLines($envFile)) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $k, $v = $line -split '=', 2
        $vars[$k.Trim()] = $v.Trim()
    }
    return $vars
}

if ($GenKeys) {
    $lines = [System.IO.File]::ReadAllLines($envFile)
    $gen = @{
        'LIVEKIT_API_KEY'    = 'API' + (-join ((New-Secret 6) | ForEach-Object { $_.ToString('x2') }))
        'LIVEKIT_API_SECRET' = ([Convert]::ToBase64String((New-Secret 48)) -replace '[/+=]', '').Substring(0, 48)
        'REDIS_PASSWORD'     = -join ((New-Secret 24) | ForEach-Object { $_.ToString('x2') })
        'AMI_SECRET'         = -join ((New-Secret 24) | ForEach-Object { $_.ToString('x2') })
    }
    for ($i = 0; $i -lt $lines.Length; $i++) {
        foreach ($k in $gen.Keys) {
            if ($lines[$i] -eq "$k=") { $lines[$i] = "$k=$($gen[$k])"; Write-Host "  $k gerado" }
        }
    }
    [System.IO.File]::WriteAllText($envFile, (($lines -join "`n") + "`n"), $utf8)
}

$vars = Read-EnvFile

# usuario de autenticacao cai para o usuario da conta quando nao informado
if (-not $vars['SIP_AUTH_USERNAME']) { $vars['SIP_AUTH_USERNAME'] = $vars['SIP_USERNAME'] }

# o painel do provedor costuma mostrar o usuario como "numero@dominio", mas o
# PJSIP quer so a parte do usuario (o dominio vem de SIP_PROVIDER_HOST)
foreach ($k in 'SIP_USERNAME', 'SIP_AUTH_USERNAME') {
    if ($vars[$k] -like '*@*') {
        $vars[$k] = $vars[$k].Split('@')[0]
        Write-Host "  aviso: $k tinha dominio junto; usando apenas '$($vars[$k])'" -ForegroundColor Yellow
    }
}
# prefixo de saida pode ser vazio de proposito
if (-not $vars.Contains('SIP_OUT_PREFIX')) { $vars['SIP_OUT_PREFIX'] = '' }
# URA pausada por padrao (M2.5, ver TODO): so' "1" liga a URA na entrada
if (-not $vars['URA_ATIVA']) { $vars['URA_ATIVA'] = '0' }

# ---- validacoes --------------------------------------------------------------
$obrig = 'PUBLIC_IP', 'LAN_IP', 'LAN_CIDR', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET', 'REDIS_PASSWORD',
         'SIP_PORT', 'SIP_RTP_START', 'SIP_RTP_END', 'SIP_MAX_ACTIVE_CALLS', 'LOG_LEVEL',
         'SIP_PROVIDER_HOST', 'SIP_PROVIDER_PORT', 'SIP_USERNAME', 'SIP_AUTH_USERNAME', 'SIP_PASSWORD',
         'SIP_REG_EXPIRY', 'SIP_DID', 'AST_RTP_START', 'AST_RTP_END',
         'AMI_PORT', 'AMI_USER', 'AMI_SECRET'
$erros = @()
foreach ($k in $obrig) { if (-not $vars[$k]) { $erros += "variavel $k vazia no .env" } }
if ($vars['SIP_DID'] -and $vars['SIP_DID'] -notmatch '^\+\d{8,15}$') {
    $erros += "SIP_DID deve estar em E.164, ex.: +558431901994 (valor atual: $($vars['SIP_DID']))"
}
if ($vars['LIVEKIT_API_SECRET'] -and $vars['LIVEKIT_API_SECRET'].Length -lt 32) {
    $erros += 'LIVEKIT_API_SECRET precisa ter 32+ caracteres'
}
foreach ($k in 'PUBLIC_IP', 'LAN_IP') {
    if ($vars[$k] -and $vars[$k] -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { $erros += "$k invalido: $($vars[$k])" }
}
if ($erros) { $erros | ForEach-Object { Write-Host "ERRO: $_" -ForegroundColor Red }; exit 1 }

# ---- bloco de webhook opcional ----------------------------------------------
if ($vars['LIVEKIT_WEBHOOK_URL']) {
    $vars['WEBHOOK_BLOCK'] = "webhook:`n  api_key: $($vars['LIVEKIT_API_KEY'])`n  urls:`n    - $($vars['LIVEKIT_WEBHOOK_URL'])"
} else {
    $vars['WEBHOOK_BLOCK'] = '# webhook desabilitado (LIVEKIT_WEBHOOK_URL vazio)'
}

# ---- render ------------------------------------------------------------------
$tmplDir = Join-Path $root 'templates'
$cfgDir = Join-Path $root 'config'
New-Item -ItemType Directory -Force $cfgDir | Out-Null
foreach ($tmpl in Get-ChildItem $tmplDir -Filter '*.tmpl' -Recurse) {
    $txt = [System.IO.File]::ReadAllText($tmpl.FullName)
    # Substitui apenas as chaves do .env. O que sobra e' variavel do proprio
    # destino (ex.: ${EXTEN} e ${CALLERID(num)} no dialplan do Asterisk).
    $naoResolvidas = New-Object System.Collections.Generic.HashSet[string]
    $txt = [regex]::Replace($txt, '\$\{([A-Za-z0-9_]+)\}', {
        param($m)
        $k = $m.Groups[1].Value
        if ($vars.Contains($k)) { return $vars[$k] }
        [void]$naoResolvidas.Add($k)
        return $m.Value
    })
    # preserva a subpasta (ex.: templates\asterisk\pjsip.conf.tmpl -> config\asterisk\pjsip.conf)
    $rel = $tmpl.FullName.Substring($tmplDir.Length + 1) -replace '\.tmpl$', ''
    $out = Join-Path $cfgDir $rel
    New-Item -ItemType Directory -Force (Split-Path -Parent $out) | Out-Null
    [System.IO.File]::WriteAllText($out, ($txt -replace "`r`n", "`n"), $utf8)
    Write-Host "  -> config\$rel"
    # Nos .yaml/.conf do LiveKit nao deve sobrar nada por resolver
    if ($naoResolvidas.Count -and $rel -notlike 'asterisk\*') {
        Write-Host ("     aviso: nao veio do .env -> " + ($naoResolvidas -join ', ')) -ForegroundColor Yellow
    }
}

Write-Host 'Configs geradas. Suba com: docker compose up -d' -ForegroundColor Green
