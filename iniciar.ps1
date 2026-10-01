<#
.SYNOPSIS
  Sobe todo o ambiente de testes de voz: Asterisk + LiveKit + SIP + Redis,
  ajusta a regra de despacho e inicia o agente de IA em uma janela nova.

.EXEMPLOS
  .\iniciar.ps1                  # sobe tudo no modo agente (IA atende)
  .\iniciar.ps1 -Modo teste      # sobe tudo sem IA (sala fixa teste-sip)
  .\iniciar.ps1 -SemAgente       # só a infraestrutura
  .\iniciar.ps1 -Parar           # derruba o agente e os containers

  Se o PowerShell bloquear: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#>
[CmdletBinding()]
param(
    [ValidateSet('agente', 'teste')][string]$Modo = 'agente',
    [switch]$SemAgente,
    [switch]$Parar
)

$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$dirLiveKit = Join-Path $raiz 'livekit-local'
$dirAgente = Join-Path $raiz 'voice-agent'
$pidAgente = Join-Path $raiz '.agente.pid'
$python = Join-Path $dirAgente '.venv\Scripts\python.exe'

function Passo($texto) { Write-Host "`n>> $texto" -ForegroundColor Cyan }
function Ok($texto) { Write-Host "   OK  $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "   !   $texto" -ForegroundColor Yellow }
function Erro($texto) { Write-Host "   X   $texto" -ForegroundColor Red }

# a janela do worker cria processos filhos (python + jobs); matar só o pai deixaria
# o agente rodando e atendendo ligações sem ninguém ver
function Para-Arvore([int]$processoId) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$processoId" -ErrorAction SilentlyContinue |
        ForEach-Object { Para-Arvore $_.ProcessId }
    Stop-Process -Id $processoId -Force -ErrorAction SilentlyContinue
}

function Para-Agente {
    if (Test-Path $pidAgente) {
        $processoId = [int](Get-Content $pidAgente)
        if (Get-Process -Id $processoId -ErrorAction SilentlyContinue) {
            Para-Arvore $processoId
            Ok "agente encerrado (PID $processoId e filhos)"
        }
        Remove-Item $pidAgente -Force
    }
    # varredura de sobras (ex.: worker fechado no X da janela ou queda anterior)
    $sobras = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$dirAgente*" -or $_.CommandLine -like '*agent.py*' }
    foreach ($sobra in $sobras) {
        Stop-Process -Id $sobra.ProcessId -Force -ErrorAction SilentlyContinue
        Ok "processo órfão do agente encerrado (PID $($sobra.ProcessId))"
    }
}

# ---------------------------------------------------------------- parar
if ($Parar) {
    Passo 'Encerrando o agente'
    Para-Agente
    Passo 'Derrubando os containers'
    Push-Location $dirLiveKit
    docker compose down | Out-Null
    Pop-Location
    Ok 'ambiente parado'
    return
}

# ------------------------------------------------------------ pré-checagens
Passo 'Verificando pré-requisitos'
docker info --format '{{.ServerVersion}}' > $null 2> $null
if ($LASTEXITCODE -ne 0) {
    Erro 'Docker não respondeu. Abra o Docker Desktop e rode de novo.'
    return
}
Ok 'Docker respondendo'

foreach ($arquivo in @((Join-Path $dirLiveKit '.env'), (Join-Path $dirLiveKit 'config\asterisk\pjsip.conf'))) {
    if (-not (Test-Path $arquivo)) {
        Erro "Faltando: $arquivo"
        Aviso 'Rode em livekit-local:  .\scripts\render-config.ps1'
        return
    }
}
Ok 'configuração do LiveKit gerada'

# o IP público muda de vez em quando e quebra o áudio sem aviso
$ipConfigurado = (Select-String -Path (Join-Path $dirLiveKit '.env') -Pattern '^PUBLIC_IP=(.+)$').Matches.Groups[1].Value
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $ipAtual = (Invoke-RestMethod -Uri 'https://api.ipify.org?format=json' -TimeoutSec 6).ip
    if ($ipAtual -ne $ipConfigurado) {
        Aviso "PUBLIC_IP no .env = $ipConfigurado, mas o IP atual é $ipAtual"
        Aviso 'Atualize o .env, rode render-config.ps1 e recrie os containers, senão a chamada fica sem áudio.'
    } else {
        Ok "IP público confere ($ipAtual)"
    }
} catch {
    Aviso 'não consegui checar o IP público (sem internet?); seguindo assim mesmo'
}

# ------------------------------------------------------------ infraestrutura
Passo 'Subindo a stack do LiveKit'
Push-Location $dirLiveKit
docker compose up -d | Out-Null
$servicos = docker compose ps --format '{{.Service}} {{.State}}'
Pop-Location
$servicos | ForEach-Object { Write-Host "   $_" }
if (($servicos | Where-Object { $_ -notmatch 'running' }).Count -gt 0) {
    Erro 'algum container não subiu; veja: docker compose logs'
    return
}

Passo 'Aguardando o LiveKit responder'
$pronto = $false
foreach ($tentativa in 1..15) {
    try {
        if ((Invoke-WebRequest -Uri 'http://localhost:7880' -TimeoutSec 3 -UseBasicParsing).Content -match 'OK') {
            $pronto = $true; break
        }
    } catch { Start-Sleep -Seconds 2 }
}
if ($pronto) { Ok 'LiveKit no ar (http://localhost:7880)' } else { Erro 'LiveKit não respondeu'; return }

Passo 'Conferindo o registro no provedor'
$registro = ''
foreach ($tentativa in 1..15) {
    Push-Location $dirLiveKit
    $registro = docker compose exec -T asterisk asterisk -rx 'pjsip show registrations' | Out-String
    Pop-Location
    if ($registro -match 'Registered') { break }
    Start-Sleep -Seconds 3
}
if ($registro -match 'Registered') {
    Ok 'Asterisk registrado no provedor'
} else {
    Aviso 'registro ainda não confirmado. Veja com:'
    Aviso '  cd livekit-local ; .\scripts\asterisk.ps1 registro   (e .\scripts\asterisk.ps1 trace)'
}

# ------------------------------------------------------------ regra de despacho
Passo "Aplicando a regra de despacho: modo $Modo"
if (-not (Test-Path $python)) {
    Erro "venv do agente não encontrado em $python"
    Aviso 'Veja voice-agent\README.md (item 1) para criar o ambiente Python.'
    return
}
& $python (Join-Path $dirAgente 'scripts\dispatch.py') $Modo | ForEach-Object { Write-Host "   $_" }
if ($LASTEXITCODE -ne 0) {
    Erro 'não consegui aplicar a regra de despacho (veja a mensagem acima)'
    return
}

# ------------------------------------------------------------ agente de IA
$agenteRodando = $false
if ($SemAgente -or $Modo -eq 'teste') {
    if ($Modo -eq 'teste') { Aviso 'modo teste: a IA não atende; entre pelo navegador' }
    if ($SemAgente -and $Modo -eq 'agente') { Aviso '-SemAgente: a regra manda para a IA, mas o worker não foi iniciado' }
} else {
    Passo 'Iniciando o agente de IA'
    $chave = Select-String -Path (Join-Path $dirAgente '.env') -Pattern '^GOOGLE_API_KEY=.+$' -ErrorAction SilentlyContinue
    if (-not $chave) {
        Erro 'GOOGLE_API_KEY vazia em voice-agent\.env — o agente não vai conseguir falar.'
        return
    }
    Para-Agente
    $processo = Start-Process -FilePath 'powershell.exe' -PassThru -WorkingDirectory $dirAgente `
        -ArgumentList '-NoExit', '-Command', "& '$python' agent.py dev"
    $processo.Id | Set-Content $pidAgente
    $agenteRodando = $true
    Ok "agente iniciado em outra janela (PID $($processo.Id)) — a conversa aparece lá"
}

# ------------------------------------------------------------ resumo
$did = (Select-String -Path (Join-Path $dirLiveKit '.env') -Pattern '^SIP_DID=(.+)$').Matches.Groups[1].Value
Write-Host "`n--------------------------------------------------------------"
Write-Host " Ambiente no ar. Ligue para: $did" -ForegroundColor Green
if ($agenteRodando) {
    Write-Host " Quem atende: agente de IA, sala call-* por chamada (janela do worker)"
} elseif ($Modo -eq 'agente') {
    Write-Host " Atenção: a regra manda para a IA, mas o worker NÃO está rodando." -ForegroundColor Yellow
    Write-Host "          Suba com: cd voice-agent ; .\.venv\Scripts\python.exe agent.py dev"
} else {
    Write-Host " Quem atende: ninguém (sala fixa teste-sip) - entre pelo navegador"
}
Write-Host " Softphone:   http://localhost/Infoprime/rapia/voip/livekit-local/test/atendente.html"
Write-Host " Token:       cd livekit-local ; .\scripts\token.ps1 -Room <sala> -Identity atendente1"
Write-Host " Parar tudo:  .\iniciar.ps1 -Parar"
Write-Host "--------------------------------------------------------------"
