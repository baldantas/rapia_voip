# Exporta LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET na sessao atual,
# para usar a CLI "lk" contra o LiveKit local. Rode com ponto na frente:
#
#   . .\scripts\lk-env.ps1
#   lk room list
$root = Split-Path -Parent $PSScriptRoot
foreach ($l in Get-Content (Join-Path $root '.env')) {
    if ($l -match '^(LIVEKIT_API_KEY|LIVEKIT_API_SECRET)=(.+)$') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim()
    }
}
$env:LIVEKIT_URL = 'http://localhost:7880'
Write-Host "LIVEKIT_URL=$env:LIVEKIT_URL  LIVEKIT_API_KEY=$env:LIVEKIT_API_KEY"
