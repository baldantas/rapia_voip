# LiveKit + SIP local (Windows / Docker Desktop) – RAPIA módulo de voz

Ambiente de desenvolvimento na sua máquina, recebendo chamadas reais pela **conta
SIP do provedor** (login e senha), com encaminhamento de portas no roteador.

O LiveKit SIP **não faz REGISTER** em provedor. Por isso o **Asterisk** entra como
SBC: ele registra na conta, mantém o registro vivo e conversa com o LiveKit por IP.

```
Provedor ──REGISTER/INVITE (login+senha)──► IP público ─► roteador (port forward)
  SIP 5060/UDP + RTP 20000-20099/UDP                           │
                                                  Windows (LAN_IP) ─ Docker Desktop
                                                                 │
     ┌─────────────────── rede docker 172.30.0.0/24 ────────────┤
     │ asterisk (.10) ──SIP/RTP por IP──► sip (.11) ◄──► livekit (.12) ◄──► redis (.13)
     └───────────────────────────────────────────────▲──────────┘
                                                     │ ws://localhost:7880 + UDP 7882
                           Navegador (softphone de teste / Painel 360) e worker de IA
```

Só o **Asterisk** fica exposto à Internet. O LiveKit SIP não tem porta publicada e
o LiveKit Server atende apenas a sua máquina e a LAN.

> Stack de produção/EC2: `../livekit-ec2`. Esta pasta é só para desenvolvimento.

## 1. Roteador

1. **Reserva de DHCP** para a sua máquina (hoje `192.168.0.21` no Wi‑Fi), para o
   IP da LAN não mudar. Se puder, use cabo: Wi‑Fi aumenta o jitter do áudio.
2. **Port forwarding** para `LAN_IP`:

   | Porta externa | Protocolo | Destino interno | Uso |
   |---|---|---|---|
   | 5060 | UDP e TCP | LAN_IP:5060 | Sinalização SIP (Asterisk) |
   | 20000-20099 | UDP | LAN_IP:20000-20099 | Áudio (RTP do Asterisk) |

   **Não** encaminhe 7880/7881/7882, 10000-10099 nem 6379: o RTP entre Asterisk e
   LiveKit SIP não sai da rede do Docker.

   Como o Asterisk renova o registro a cada `SIP_REG_EXPIRY` segundos, o NAT
   costuma manter o caminho de volta aberto mesmo sem encaminhamento. Ainda assim,
   encaminhar deixa o ambiente previsível.
3. Se o roteador permitir, **restrinja a origem** dessas regras aos IPs do provedor.
   Localmente, esse é o principal filtro de segurança do SIP (ver seção 6).
4. **Desative o SIP ALG** (às vezes chamado "SIP Helper", "SIP Passthrough" ou
   "VoIP ALG"). Ele reescreve pacotes SIP e causa chamada sem áudio, áudio só de
   um lado ou queda aos 30 segundos. É a causa nº 1 de problemas em testes assim.

## 2. Windows

```powershell
cd C:\wamp64\www\Infoprime\rapia\voip\livekit-local

# (uma vez) permitir scripts locais
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# regras de entrada no Firewall do Windows (PowerShell COMO ADMINISTRADOR)
.\scripts\firewall-windows.ps1
# ou já restringindo o SIP aos IPs da operadora:
.\scripts\firewall-windows.ps1 -OperadoraIPs 200.200.200.10,200.200.200.11
```

## 3. Subir a stack

```powershell
Copy-Item .env.example .env
notepad .env                        # PUBLIC_IP, LAN_IP e a conta SIP do provedor:
                                    # SIP_PROVIDER_HOST / SIP_USERNAME / SIP_PASSWORD / SIP_DID
.\scripts\render-config.ps1 -GenKeys  # gera key/secret/senha do Redis + config\*
docker compose up -d
docker compose logs -f asterisk sip livekit
```

Verificação:

```powershell
curl.exe http://localhost:7880      # -> OK
docker compose ps                   # asterisk, livekit, sip e redis "running"

.\scripts\asterisk.ps1 registro     # precisa mostrar "Registered"
.\scripts\asterisk.ps1 endpoints    # provedor: Available | livekit: Avail
```

Se o registro ficar em `Rejected`, confira usuário e senha e rode
`.\scripts\asterisk.ps1 trace` para ver o 401/403 devolvido pelo provedor.

Depois de mudar o `.env`: `.\scripts\render-config.ps1; docker compose up -d --force-recreate`.

## 4. CLI `lk` e tronco SIP

Instale a [LiveKit CLI](https://github.com/livekit/livekit-cli) (no Windows:
`winget install LiveKit.LiveKitCLI` ou o binário dos releases do GitHub).

```powershell
. .\scripts\lk-env.ps1               # exporta URL/key/secret do .env nesta sessão

# edite sip\inbound-trunk.json com o(s) número(s) (DID) da central em E.164
lk sip inbound create sip\inbound-trunk.json      # anote o ID (ST_...)     SIPTrunkID: ST_tVx9weF8Hitr

# coloque o ID em sip\dispatch-rule-teste.json -> trunk_ids         SIPDispatchRuleID: SDR_VnYQVxrrkwYg
lk sip dispatch create sip\dispatch-rule-teste.json

lk sip inbound list
lk sip dispatch list
```

O `inbound-trunk.json` só aceita chamadas vindas do Asterisk (`172.30.0.10/32`) e o
`outbound-trunk.json` aponta para ele. Quem trata login, senha e formato de número
do provedor é o Asterisk, não o LiveKit.

Confirme com o provedor: codec **G.711 A-law (PCMA)**, DTMF **RFC 2833/4733** e o
formato do número nas chamadas de saída (ajuste `SIP_OUT_PREFIX` no `.env`).

> O formato dos JSONs do `lk sip` pode mudar entre versões da CLI. Em caso de
> erro, veja `lk sip dispatch create --help`. Os mesmos objetos também podem ser
> criados por flags da CLI ou pela API, que é o que o RAPIA vai usar.

## 5. Primeiro teste ponta a ponta (sem IA)

A regra `dispatch-rule-teste.json` coloca **toda chamada** na sala fixa `teste-sip`.

1. Gere um token de atendente:
   ```powershell
   .\scripts\token.ps1 -Room teste-sip -Identity atendente1 | Set-Clipboard
   ```

   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJBUEkyODVjMWQ1YjdiYzUiLCJzdWIiOiJhdGVuZGVudGUxIiwibmFtZSI6ImF0ZW5kZW50ZTEiLCJuYmYiOjE3ODk4NjcwNzUsImV4cCI6MTc4OTg4MTQ4NSwidmlkZW8iOnsicm9vbSI6InRlc3RlLXNpcCIsInJvb21Kb2luIjp0cnVlLCJjYW5QdWJsaXNoIjp0cnVlLCJjYW5TdWJzY3JpYmUiOnRydWV9fQ.9MdyW-SySpx59Q_2cgArfKHEwN8IEo9TIygjuPGKJC8
   
2. Abra o softphone de teste pelo WAMP (precisa ser `localhost` para o microfone):
   `http://localhost/Infoprime/rapia/voip/livekit-local/test/atendente.html`
3. Cole o token → **Conectar** → permita o microfone.
4. Ligue do celular para o número da central. O chamador aparece como
   participante `SIP`, e vocês conversam pelo navegador. O teclado DTMF da página
   envia tons para o chamador.

**Chamada de saída (base do callback, cenário 4):** configure
`sip\outbound-trunk.json` com os dados da operadora e crie o tronco. Com o
softphone já conectado na sala `teste-sip`, origine a ligação:

```powershell
lk sip outbound create sip\outbound-trunk.json    # anote o ID (ST_...)
# ajuste sip\outbound-call.json (trunk de saída + número de destino)
lk sip participant create sip\outbound-call.json
```

Quando o worker de IA existir, troque a regra de teste por
`sip\dispatch-rule-agente.json` (uma sala `call-*` por chamada + despacho do
agente `rapia-voice`). O worker Python roda na sua máquina com
`LIVEKIT_URL=ws://localhost:7880` e a mesma key/secret do `.env`.

## 6. Particularidades do ambiente local

- **IP de origem no container:** o encaminhamento de portas do Docker Desktop pode
  trocar o IP de origem dos pacotes pelo gateway interno do Docker. Por isso o
  endpoint `provedor` casa por `line=yes` (o próprio registro) e por hostname, e o
  filtro por IP do provedor fica no roteador e no Firewall do Windows
  (`-OperadoraIPs`). Já o trunk do LiveKit filtra pelo IP fixo do Asterisk.
- **Faixa RTP pequena:** 100 portas (20000-20099) no Asterisk bastam para testes.
  Se aumentar, ajuste o `.env`, o roteador e o firewall juntos.
- **Softphone na mesma LAN** discando para `PUBLIC_IP` depende de o roteador
  suportar *NAT loopback*. Para testar sem operadora, prefira um softphone no
  celular usando o 4G/5G.
- **Webhook para o Laravel:** preencha `LIVEKIT_WEBHOOK_URL` com
  `http://host.docker.internal/...` (a rota ainda será criada no sysapi).
- **Acesso ao LiveKit fora da sua máquina** (ex.: outra atendente testando de
  casa) exige TLS/WSS e as portas 7880-7882 expostas, ou seja, a stack da EC2.
- **Se o `livekit` não subir** reclamando de `advertise_internal_ip` (versão da
  imagem mais antiga), remova essa linha do template e renderize de novo. O SIP
  alcança o LiveKit pelo `LAN_IP:7882` do mesmo jeito.

## 7. Diagnóstico rápido

| Sintoma | Causa provável |
|---|---|
| Registro `Rejected` com 401 repetido | Usuário de autenticação diferente do usuário da conta: preencha `SIP_AUTH_USERNAME` |
| Registro `Rejected` com 403 | Senha errada, conta bloqueada ou provedor esperando outro domínio em `client_uri` |
| Nenhuma tentativa de registro sai | `SIP_PROVIDER_HOST` errado, saída UDP 5060 bloqueada ou DNS do container |
| Chamada não chega (nada no log do `asterisk`) | Port forward 5060, firewall do Windows, provedor entregando em outro destino |
| Asterisk recebe, mas o LiveKit rejeita | Número enviado ≠ `numbers` do trunk (o dialplan manda o `SIP_DID` em E.164) ou `allowed_addresses` sem `172.30.0.10/32` |
| Atende, mas sem áudio / cai em ~30 s | SIP ALG ligado, RTP 20000-20099 não encaminhado, `PUBLIC_IP` errado |
| Áudio só de um lado | RTP bloqueado em um sentido (firewall/roteador) ou NAT do lado do provedor |
| Navegador não conecta na sala | Token expirado/sala errada, página aberta fora de `localhost`, porta 7882/UDP |

Comandos úteis: `.\scripts\asterisk.ps1 trace` (log SIP completo),
`.\scripts\asterisk.ps1 canais`, `.\scripts\asterisk.ps1 teste` (gera um tom do
Asterisk para dentro do LiveKit, sem depender do provedor) e
`.\scripts\asterisk.ps1 cli "pjsip show aors"`.
