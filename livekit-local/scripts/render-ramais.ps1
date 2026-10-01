<#
.SYNOPSIS
  Gera config\asterisk\pjsip_ramais.conf a partir de ramais\ramais.json.

  M2.5 (23/09/2026): decisão foi template + reload em vez de Realtime PJSIP
  (imagem do Asterisk tem os módulos de Realtime compilados, mas nenhum driver
  ODBC de MySQL instalado, e instalar via apt não sobrevive a um
  --force-recreate). Quando o backend tiver voice_extensions de verdade, este
  script passa a ler do banco em vez do JSON - o pjsip.conf.tmpl que dá
  #include no arquivo gerado não muda.

.USO
  cd voip\livekit-local
  .\scripts\render-ramais.ps1                    # gera o .conf
  .\scripts\render-ramais.ps1 -Recarregar        # gera e manda o Asterisk recarregar (pjsip reload)
#>
param([switch]$Recarregar)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$fonte = Join-Path $root 'ramais\ramais.json'
$destino = Join-Path $root 'config\asterisk\pjsip_ramais.conf'
$utf8 = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path $fonte)) { throw "Não encontrei $fonte" }

$dados = Get-Content $fonte -Raw -Encoding UTF8 | ConvertFrom-Json
$linhas = New-Object System.Collections.Generic.List[string]
$linhas.Add('; Gerado por scripts/render-ramais.ps1 a partir de ramais/ramais.json - edite lá, não aqui.')
$linhas.Add('; Contexto "ramais" (dialplan) e endpoints SIP dos ramais internos - ver TODO seção 7, bloco M2.5.')

foreach ($r in $dados.ramais) {
    $ramal = $r.ramal
    $linhas.Add('')
    $linhas.Add("; --- Ramal $ramal ($($r.descricao)) ---")
    $linhas.Add("[$ramal]")
    $linhas.Add('type=auth')
    $linhas.Add('auth_type=userpass')
    $linhas.Add("username=$ramal")
    $linhas.Add("password=$($r.senha)")
    $linhas.Add('')
    $linhas.Add("[$ramal]")
    $linhas.Add('type=aor')
    $linhas.Add('max_contacts=1')
    $linhas.Add('remove_existing=yes')
    $linhas.Add('qualify_frequency=30')
    $linhas.Add('')
    $linhas.Add("[$ramal]")
    $linhas.Add('type=endpoint')
    $linhas.Add('transport=transport-udp')
    $linhas.Add('context=ramais')
    $linhas.Add("auth=$ramal")
    $linhas.Add("aors=$ramal")
    $linhas.Add('disallow=all')
    $linhas.Add('allow=alaw,ulaw')
    $linhas.Add('dtmf_mode=rfc4733')
    $linhas.Add('direct_media=no')
    $linhas.Add('rtp_symmetric=yes')
    $linhas.Add('force_rport=yes')
    $linhas.Add('rewrite_contact=yes')
    $linhas.Add("callerid=""Ramal $ramal"" <$ramal>")
}

New-Item -ItemType Directory -Force (Split-Path -Parent $destino) | Out-Null
[System.IO.File]::WriteAllText($destino, (($linhas -join "`n") + "`n"), $utf8)
Write-Host "  -> config\asterisk\pjsip_ramais.conf ($($dados.ramais.Count) ramal(is))"

if ($Recarregar) {
    Push-Location $root
    docker compose exec -T asterisk asterisk -rx 'pjsip reload' | Write-Host
    Pop-Location
}
