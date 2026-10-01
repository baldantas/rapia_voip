# Comandos do dia a dia — ambiente de voz local

Referência rápida. Instalação completa e explicações: `livekit-local\README.md`
e `voice-agent\README.md`.

## Subir tudo (1 comando)

```powershell
cd C:\wamp64\www\Infoprime\rapia\voip
.\iniciar.ps1                 # sobe a stack, confere o registro, aplica a regra
                              # da IA e abre o worker em outra janela
.\iniciar.ps1 -Modo teste     # sobe sem IA (sala fixa teste-sip)
.\iniciar.ps1 -SemAgente      # só a infraestrutura
.\iniciar.ps1 -Parar          # derruba o worker (e filhos) e os containers
```

O script também avisa se o seu IP público mudou, o que derruba o áudio das chamadas.

## Subir na mão (2 terminais)

**Terminal 1 — infraestrutura** (Asterisk + LiveKit + SIP + Redis):

```powershell
cd C:\wamp64\www\Infoprime\rapia\voip\livekit-local
docker compose up -d
.\scripts\asterisk.ps1 registro        # precisa mostrar "Registered"
```

**Terminal 2 — agente de IA** (deixe rodando; é aqui que aparece a conversa):

```powershell
cd C:\wamp64\www\Infoprime\rapia\voip\voice-agent
.\.venv\Scripts\python.exe agent.py dev
```

Com o worker no ar, ligue para **+55 84 3190-1994**.

## Alternar quem atende a ligação

```powershell
cd C:\wamp64\www\Infoprime\rapia\voip\voice-agent
.\.venv\Scripts\python.exe scripts\dispatch.py agente   # IA atende (sala call-* por chamada)
.\.venv\Scripts\python.exe scripts\dispatch.py teste    # sem IA (sala fixa teste-sip)
.\.venv\Scripts\python.exe scripts\dispatch.py listar   # ver trunk e regra atuais
```

No modo `agente`, suba o worker **antes** de ligar.

## Entrar na ligação pelo navegador

O nome da sala (`call-...`) aparece no log do worker; no modo `teste` é `teste-sip`.

```powershell
cd C:\wamp64\www\Infoprime\rapia\voip\livekit-local
.\scripts\token.ps1 -Room call-xxxxxxxx -Identity atendente1 | Set-Clipboard
```

Abra `http://localhost/Infoprime/rapia/voip/livekit-local/test/atendente.html`,
cole o token e clique em Conectar.

## Parar

```powershell
# terminal do agente: Ctrl+C
cd C:\wamp64\www\Infoprime\rapia\voip\livekit-local
docker compose down
```

## Depois de editar arquivos

| Arquivo alterado | O que fazer |
|---|---|
| `voice-agent\prompt.md` | Ctrl+C no worker e subir de novo |
| `voice-agent\.env` (voz, modelo) | idem |
| `livekit-local\.env` | `.\scripts\render-config.ps1` e `docker compose up -d --force-recreate` |
| `livekit-local\templates\*` | idem |

## Diagnóstico rápido

```powershell
cd C:\wamp64\www\Infoprime\rapia\voip\livekit-local
docker compose ps                      # os 4 containers "running"
.\scripts\asterisk.ps1 registro        # registro no provedor
.\scripts\asterisk.ps1 endpoints       # provedor e livekit devem estar "Avail"
.\scripts\asterisk.ps1 canais          # chamadas em andamento
.\scripts\asterisk.ps1 trace           # liga o log SIP detalhado (notrace desliga)
.\scripts\asterisk.ps1 teste           # tom de teste do Asterisk para dentro do LiveKit
docker compose logs -f asterisk sip    # logs ao vivo
```

| Sintoma | Primeiro a verificar |
|---|---|
| Ligação não entra | `asterisk.ps1 registro`; se caiu, `docker compose restart asterisk` |
| Entra mas ninguém atende | worker parado, ou regra no modo `teste` |
| Sem áudio | RTP 20000-20099 no roteador, SIP ALG ligado, `PUBLIC_IP` mudou no `.env` |
| IA não responde | `GOOGLE_API_KEY` no `voice-agent\.env`, e erros no console do worker |

Os dados coletados em cada ligação ficam em `voice-agent\coletas.jsonl`.
