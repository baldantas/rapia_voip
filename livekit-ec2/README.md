# LiveKit + SIP em EC2 — homologação (RAPIA, módulo de voz)

Stack da **EC2 de homologação** (no ar desde 25/09/2026): LiveKit Server, LiveKit SIP,
Redis e Asterisk (SBC), todos em `network_mode: host`. sysweb, sysapi e o worker de IA
continuam no PC do desenvolvedor. Estado, IPs, IDs de trunks e pendências: seção 7.3 de
`voip/TODO-RAPIA-VOICE-V1.md`.

```
Provedor SIP (sobreip) ──REGISTER/INVITE──► asterisk :5060, RTP 20000-20099   (Elastic IP)
                                               │ 127.0.0.1:5080
                                            livekit-sip ──ws://127.0.0.1:7880── livekit ── redis 127.0.0.1:6379
                                                                                  ▲ 7880/tcp 7881/tcp 7882/udp
   webhook do LiveKit + CURL() do dialplan                                         │ (OpenVPN)
   ──► https://apiflowip.ngrok.app ──► sysapi no PC             PC: sysapi, navegador, worker de IA
```

Fora da homologação: Caddy/TLS, TURN e Egress (templates antigos em `extras/`).

```
voip/livekit-ec2/
├── docker-compose.yml       redis, livekit, sip, asterisk
├── .env.example             copiar para .env (segredos: nunca versionar)
├── templates/               livekit.yaml, sip.yaml, redis.conf (*.tmpl)
│   └── asterisk/            pjsip, extensions, manager, rtp, logger, modules (*.tmpl)
├── sounds/                  ura-boas-vindas.wav (8 kHz mono; voz Leda do Gemini)
├── scripts/
│   ├── bootstrap-host.sh    Docker + compose + envsubst + sysctl UDP (Ubuntu 24.04)
│   ├── render-config.sh     gera ./config a partir do .env (--gen-keys preenche segredos vazios)
│   └── provisiona-sip.sh    cria trunks e dispatch rules a partir de sip/*.json (ou "listar")
├── sip/                     inbound (IA, fila direta, fila padrão, ramais), outbound, dispatch rules
└── extras/                  caddy/egress (não usados)
```

## Security Group (entrada)

| Porta | Origem |
|---|---|
| 22/tcp, 7880/tcp, 7881/tcp, 7882/udp | VPN (origem vista: IP privado do servidor OpenVPN) e/ou IP público do desenvolvedor |
| 5060/udp+tcp, 20000-20099/udp | IPs do provedor, /32 cada: 189.113.38.59, 186.209.45.20, 186.209.52.214, 216.10.29.131, 52.67.163.135 |

Nunca `0.0.0.0/0`. Não abrir 5080, 6379, 5038 (AMI), 8081 (health do SIP), 10000-19999.

## Subir do zero

```bash
# do PC (Git Bash), com a VPN conectada
tar --exclude=.env --exclude=config --exclude=data -cf - . | ssh ubuntu@<IP_PRIVADO> 'mkdir -p ~/livekit-ec2 && cd ~/livekit-ec2 && tar -xf - && sed -i "s/\r$//" scripts/*.sh && chmod +x scripts/*.sh'

# na EC2
sudo ./scripts/bootstrap-host.sh          # e sair/entrar de novo (grupo docker)
curl -sSL https://get.livekit.io/cli | bash
cp .env.example .env                       # PUBLIC_IP, NODE_IP, SIP_PASSWORD, URA_API_TOKEN
./scripts/render-config.sh --gen-keys
# ANTES do asterisk: parar o Asterisk local (a conta SIP aceita UM registro)
docker compose up -d
./scripts/provisiona-sip.sh
```

Conferir: `docker compose ps` (4 running), `curl http://127.0.0.1:7880` = OK,
`curl http://127.0.0.1:8081` = OK, `docker compose exec asterisk asterisk -rx 'pjsip show registrations'`
= Registered.

## Variáveis principais (`.env`)

| Variável | Uso |
|---|---|
| `PUBLIC_IP` | Elastic IP; anunciado pelo Asterisk no SIP/SDP |
| `NODE_IP` | IP anunciado pelo LiveKit. OpenVPN UDP: IP privado. OpenVPN TCP: Elastic IP |
| `LIVEKIT_WEBHOOK_URL` | webhook para o sysapi (ngrok) |
| `RAPIA_BASE_URL`, `URA_API_TOKEN` | `CURL()` do dialplan: URA (`/voice/ura/runtime`) e filtro de números (`/voice/ura/caller-allowed`) |
| `URA_ATIVA` | 1 = entrada passa pela URA; 0 = direto para a IA |
| `SIP_PROVIDER_IN_IPS` | IPs de entrada do provedor (vão para o `identify`) |
| `SIP_OUT_PREFIX` | prefixo das chamadas de saída (vazio = `55DDDNUMERO`) |

Depois de mudar o `.env`: `./scripts/render-config.sh` e então `docker compose exec asterisk asterisk -rx
'dialplan reload'` (dialplan) / `'pjsip reload'` (pjsip) ou `docker compose restart livekit sip`.

## Fluxo de entrada (dialplan)

1. `[from-provedor]`: consulta o filtro de números permitidos **antes de atender**. Qualquer resposta
   diferente de `allow` (inclusive API fora do ar) -> `Hangup(17)` (ocupado; com 403 o provedor reenviava).
2. `URA_ATIVA=1` -> `[ura-menu]` (contexto próprio: o dígito é tratado assim que chega). Dígito ->
   `CURL()` no RAPIA -> `agent` (DID, sala `call-*` com IA) / `queue` (9990101, `fila-*`) / outro ->
   fila padrão (9990102, `filapadrao-*`).
3. Saída: `[from-livekit]` disca pelo provedor com caller ID = DID.

## Áudio da URA

Gerado com a voz do Gemini Live: `voip/voice-agent/scripts/gerar_audio_ura.py --saida <wav>` (opções
`--voz`, `--texto`). Copiar para `sounds/` aqui e na EC2 (`~/livekit-ec2/sounds/`); não precisa reiniciar.

## Derrubar / reverter

`docker compose down` (trunks e regras ficam em `data/redis`). Reversão para o ambiente local: seção 7.3
do TODO. Parar a instância quando não estiver em uso (o Elastic IP continua cobrando).
