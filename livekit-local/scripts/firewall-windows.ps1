# Cria regras de entrada no Firewall do Windows para a stack LiveKit local.
# Execute em um PowerShell COMO ADMINISTRADOR, na pasta voip\livekit-local:
#
#   .\scripts\firewall-windows.ps1
#   .\scripts\firewall-windows.ps1 -OperadoraIPs 200.200.200.10,200.200.200.11   # restringe o SIP
#   .\scripts\firewall-windows.ps1 -Remover
param(
    [string[]]$OperadoraIPs = @(),
    [switch]$Remover
)

$ErrorActionPreference = 'Stop'
$grupo = 'RAPIA LiveKit Local'

if ($Remover) {
    Get-NetFirewallRule -Group $grupo -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Write-Host "Regras do grupo '$grupo' removidas."
    exit 0
}

# Le portas do .env (com valores padrao)
$root = Split-Path -Parent $PSScriptRoot
$cfg = @{ SIP_PORT = '5060'; AST_RTP_START = '20000'; AST_RTP_END = '20099' }
$envFile = Join-Path $root '.env'
if (Test-Path $envFile) {
    foreach ($l in Get-Content $envFile) {
        if ($l -match '^(SIP_PORT|AST_RTP_START|AST_RTP_END)=(\d+)') { $cfg[$Matches[1]] = $Matches[2] }
    }
}
# Faixa RTP do Asterisk (o RTP do LiveKit SIP nao sai da rede docker)
$rtp = "$($cfg.AST_RTP_START)-$($cfg.AST_RTP_END)"
$sipOrigem = if ($OperadoraIPs.Count) { $OperadoraIPs } else { @('Any') }

Get-NetFirewallRule -Group $grupo -ErrorAction SilentlyContinue | Remove-NetFirewallRule

$regras = @(
    @{ n = 'SIP sinalizacao UDP'; p = 'UDP'; port = $cfg.SIP_PORT; r = $sipOrigem },
    @{ n = 'SIP sinalizacao TCP'; p = 'TCP'; port = $cfg.SIP_PORT; r = $sipOrigem },
    @{ n = 'SIP midia RTP';       p = 'UDP'; port = $rtp;          r = @('Any') },
    @{ n = 'LiveKit API/WS (LAN)';   p = 'TCP'; port = '7880,7881'; r = @('LocalSubnet') },
    @{ n = 'LiveKit WebRTC UDP (LAN)'; p = 'UDP'; port = '7882';    r = @('LocalSubnet') }
)

foreach ($r in $regras) {
    New-NetFirewallRule -DisplayName "$grupo - $($r.n)" -Group $grupo -Direction Inbound -Action Allow `
        -Protocol $r.p -LocalPort ($r.port -split ',') -RemoteAddress $r.r -Profile Any | Out-Null
    Write-Host ("  + {0,-26} {1} {2,-12} origem: {3}" -f $r.n, $r.p, $r.port, ($r.r -join ','))
}
Write-Host "Regras criadas no grupo '$grupo'." -ForegroundColor Green
