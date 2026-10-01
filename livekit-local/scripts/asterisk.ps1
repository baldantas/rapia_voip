# Atalhos para o console do Asterisk (CLI) dentro do container.
#
#   .\scripts\asterisk.ps1 registro      # estado do registro no provedor
#   .\scripts\asterisk.ps1 endpoints     # estado dos endpoints (provedor / livekit)
#   .\scripts\asterisk.ps1 canais        # chamadas em andamento
#   .\scripts\asterisk.ps1 trace         # liga o log detalhado de SIP (pjsip set logger on)
#   .\scripts\asterisk.ps1 notrace
#   .\scripts\asterisk.ps1 teste         # chamada de teste: Asterisk -> LiveKit SIP
#   .\scripts\asterisk.ps1 cli "pjsip show aors"   # qualquer comando
param(
    [Parameter(Position = 0)][string]$Acao = 'registro',
    [Parameter(Position = 1)][string]$Comando = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$did = '+558431901994'
foreach ($l in Get-Content (Join-Path $root '.env') -ErrorAction SilentlyContinue) {
    if ($l -match '^SIP_DID=(.+)$') { $did = $Matches[1].Trim() }
}

$mapa = @{
    registro  = 'pjsip show registrations'
    endpoints = 'pjsip show endpoints'
    canais    = 'core show channels'
    trace     = 'pjsip set logger on'
    notrace   = 'pjsip set logger off'
    teste     = "channel originate PJSIP/$did@livekit application Milliwatt"
    cli       = $Comando
}

if (-not $mapa.ContainsKey($Acao)) {
    Write-Host "Acao invalida. Use: $($mapa.Keys -join ', ')" -ForegroundColor Red
    exit 1
}
$cmd = $mapa[$Acao]
if (-not $cmd) { Write-Host 'Informe o comando: .\scripts\asterisk.ps1 cli "pjsip show aors"' -ForegroundColor Red; exit 1 }

docker compose exec -T asterisk asterisk -rx "$cmd"
