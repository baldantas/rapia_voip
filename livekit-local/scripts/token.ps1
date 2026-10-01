# Gera um token de acesso (JWT HS256) do LiveKit para testes, usando a key/secret do .env.
# E o mesmo formato que o Laravel vai gerar no modulo de voz.
#
#   .\scripts\token.ps1 -Room teste-sip -Identity atendente1
#   .\scripts\token.ps1 -Room teste-sip -Identity supervisor -SomenteOuvir
param(
    [Parameter(Mandatory = $true)][string]$Room,
    [string]$Identity = 'atendente1',
    [int]$ValidadeHoras = 4,
    [switch]$SomenteOuvir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$vars = @{}
foreach ($l in Get-Content (Join-Path $root '.env')) {
    if ($l -match '^(LIVEKIT_API_KEY|LIVEKIT_API_SECRET)=(.+)$') { $vars[$Matches[1]] = $Matches[2].Trim() }
}
if (-not $vars.LIVEKIT_API_KEY -or -not $vars.LIVEKIT_API_SECRET) { throw 'LIVEKIT_API_KEY/SECRET ausentes no .env' }

function ConvertTo-B64Url([byte[]]$b) { [Convert]::ToBase64String($b).TrimEnd('=').Replace('+', '-').Replace('/', '_') }

$agora = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$header = @{ alg = 'HS256'; typ = 'JWT' } | ConvertTo-Json -Compress
$payload = [ordered]@{
    iss   = $vars.LIVEKIT_API_KEY
    sub   = $Identity
    name  = $Identity
    nbf   = $agora - 10
    exp   = $agora + ($ValidadeHoras * 3600)
    video = [ordered]@{
        room         = $Room
        roomJoin     = $true
        canPublish   = (-not $SomenteOuvir)
        canSubscribe = $true
    }
} | ConvertTo-Json -Compress -Depth 5

$enc = [System.Text.Encoding]::UTF8
$unsigned = (ConvertTo-B64Url $enc.GetBytes($header)) + '.' + (ConvertTo-B64Url $enc.GetBytes($payload))
$hmac = New-Object System.Security.Cryptography.HMACSHA256 (, $enc.GetBytes($vars.LIVEKIT_API_SECRET))
$token = $unsigned + '.' + (ConvertTo-B64Url $hmac.ComputeHash($enc.GetBytes($unsigned)))

Write-Output $token
