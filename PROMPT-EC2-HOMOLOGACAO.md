# Prompt — Montagem da infraestrutura de voz em EC2 de homologação

> Sessão dedicada **só à infra**. O desenvolvimento do M4 (M4.3 discador) fica parado e será retomado
> em outra sessão depois que este ambiente estiver no ar e provado.

## 1. Contexto

Projeto RAPIA (atendimento para clínicas/hospitais/laboratórios): backend `sysapi` (Laravel 8), frontend
`sysweb` (Vue 2.5), módulo de voz em `voip/` (SIP + LiveKit + Gemini Live). `sysapi` e `sysweb` são repositórios
git; `voip/` **não é**.

Estado do módulo de voz (25/09/2026): M0–M3 concluídos; M4.1 (fila de retornos) e M4.2 (handoff WhatsApp)
concluídos e commitados; **M4.3 (discador/originação) aguardando esta infra**. A URA de entrada está **pausada**
(`URA_ATIVA=0`): no Docker Desktop do Windows, quando o próprio Asterisk atende a ligação, o relay de mídia do
provedor não envia áudio; quando quem atende é a ponte com o LiveKit, funciona. A única anomalia de rede que sobrou
foi o NAT do Docker Desktop (troca da porta de origem). Esta EC2 serve para eliminar essa variável e destravar os
testes de ligação real (entrada, URA e saída).

Leia, nesta ordem:
- `CLAUDE.md` da raiz;
- `voip/TODO-RAPIA-VOICE-V1.md`: seção 3 (Arquitetura), o bloco **M2.5 inteiro** (achado do áudio mudo, URA
  pausada, ramais, AMI), a seção 7.2 (URLs e multi-tenant) e o bloco M4 (só para contexto);
- `voip/livekit-local/`: a stack que roda **hoje** no Windows (`docker-compose.yml`, `templates/`,
  `scripts/render-config.ps1`, `scripts/render-ramais.ps1`, `sip/*.json`, `README.md`, `.env.example`);
- `voip/livekit-ec2/`: pacote para EC2, **desatualizado** (19/09/2026, anterior ao M2.5);
- `voip/teste-ec2/README.md`: teste diagnóstico só do Asterisk. Fica **dispensado** se esta stack subir.

## 2. Decisões já tomadas (não reabrir)

| Tema | Decisão |
|---|---|
| Onde roda | EC2 **dedicada à homologação** com LiveKit Server, LiveKit SIP, Redis (do LiveKit) e Asterisk, todos em `network_mode: host`. `sysweb`, `sysapi` (WAMP) e o worker de IA (`voip/voice-agent/agent.py`) **continuam no PC do usuário** |
| Região / SO | `sa-east-1`; **Ubuntu Server 24.04 LTS (x86_64)** (o `bootstrap-host.sh` usa apt) |
| Instância | **t3a.medium** (2 vCPU, 4 GiB), crédito **standard**, EBS **gp3 20 GiB**, **Elastic IP**. Parar a instância quando não estiver em uso (o Elastic IP continua cobrando) |
| Fora do escopo | Caddy/TLS, TURN, Egress (gravação), worker na EC2, produção, ramais SIP (ver seção 7) |
| PC → EC2 | pela **OpenVPN** do usuário (o PC já alcança instâncias de `sa-east-1`) |
| EC2 → PC | pelo **ngrok pago** do usuário: `.\ngrok.exe http http://localhost:8000 --domain=apiflowip.ngrok.app` |
| Tenant via ngrok | **não precisa reescrever o Host**: o `CheckSubDomain` e o `VoiceWebhookTenant` já convertem o subdomínio `apiflowip` em `api` |
| Restrição no ngrok | **não restringir por IP**: o mesmo domínio provavelmente recebe o webhook da Meta (WhatsApp). Os endpoints de voz já exigem assinatura JWT (webhook do LiveKit) ou `x-api-key` (URA) |
| Caller ID de saída | o **número do canal de saída** (DID do tronco, `+558431901994`); o `[from-livekit]` do dialplan já faz isso |
| Acesso do assistente | SSH com chave dedicada (ver seção 4) |

### Provedor SIP (sobreip)
- Conta com registro por login/senha no Asterisk; usuário `8431901994`; servidor `voz.sobreip.com.br:5060`;
  DID `+558431901994`. Senha no `.env` (nunca exibir). **A conta aceita UM registro por vez.**
- **IPs de entrada** (de onde chegam INVITEs): `189.113.38.59`, `186.209.45.20`, `186.209.52.214`, `216.10.29.131`.
- **IP de saída** (registro/sinalização e relay de mídia observado): `voz.sobreip.com.br` = `52.67.163.135`.
- **Ajuste obrigatório no `pjsip`**: hoje o `identify` do endpoint `provedor` só casa `voz.sobreip.com.br`.
  Incluir os 4 IPs de entrada no `match=`, senão INVITEs vindos deles podem não ser reconhecidos.

## 3. Topologia

```
Provedor SIP  (entrada: 189.113.38.59 / 186.209.45.20 / 186.209.52.214 / 216.10.29.131;
               saída/relay: 52.67.163.135)
   │ 5060 udp/tcp + RTP 20000-20099/udp  (Security Group só para esses 5 IPs)
   ▼
EC2 homologação (sa-east-1, Ubuntu 24.04, t3a.medium, Elastic IP) ── network_mode: host
   asterisk :5060 ──127.0.0.1:5080── livekit-sip ──ws://127.0.0.1:7880── livekit-server ── redis 127.0.0.1:6379
                                                                            ▲ 7880/tcp, 7881/tcp, 7882/udp
   │ webhook do LiveKit + CURL() da URA                                     │ (só pela OpenVPN)
   ▼                                                                        │
https://apiflowip.ngrok.app ─► localhost:8000 (sysapi)          PC do usuário (OpenVPN)
                                                                  sysapi -> http://<IP_EC2>:7880
                                                                  navegador e worker -> ws://<IP_EC2>:7880 + WebRTC
```

## 4. Acesso SSH do assistente

- O assistente roda no Windows do usuário e tem `ssh`/`scp` (OpenSSH em `C:\Windows\System32\OpenSSH`). A OpenVPN
  precisa estar conectada.
- **Chave dedicada** `ed25519`, gerada localmente em `~/.ssh/rapia_homolog` (a privada nunca sai do PC; só a
  pública é entregue ao usuário).
- Na EC2 o **usuário** cria um usuário Linux próprio (ex.: `rapia`) com a chave pública em `authorized_keys`, no
  grupo `docker` e com `sudo` sem senha (aceitável só por ser homologação; nunca em produção).
- Security Group da **22/tcp**: só a origem que a EC2 enxerga vindo da VPN. Se o servidor OpenVPN fica na VPC e
  faz NAT, essa origem é o **IP privado do servidor OpenVPN**, não o do PC.
- **Autonomia combinada nesta instância de homologação**: sem pedir, o assistente pode enviar arquivos, renderizar
  configs, subir/reiniciar/recriar containers, ler logs, rodar diagnósticos (inclusive `tcpdump`) e criar/remover
  trunks e dispatch rules no LiveKit **desta** EC2. **Pedir antes**: qualquer ligação real, ativar a URA
  (`URA_ATIVA=1`), apagar dados, alterar os `.env` locais (sysapi e worker), qualquer coisa fora desta instância.
  Security Group e console AWS são sempre feitos pelo usuário.

## 5. Pendências a confirmar no início (perguntar)

1. **Protocolo da OpenVPN** (`proto udp` ou `proto tcp` no `.ovpn`). Define o `NODE_IP` do LiveKit:
   - UDP e o PC alcança o **IP privado** da EC2 → `NODE_IP` = IP privado; mídia WebRTC toda pela VPN; 7880/7881/7882
     liberadas só para a origem da VPN.
   - TCP (áudio WebRTC sobre TCP picota) → `NODE_IP` = Elastic IP; 7881/tcp e 7882/udp liberadas só para o **IP
     público** do usuário; 7880 continua só pela VPN.
2. **A porta 8000 é o sysapi?** Nela escuta um processo `php` (provável `php artisan serve` do sysapi); o `api.ipsys`
   do WAMP está na porta 80. Se não for o sysapi, ajustar o túnel.
3. Dados da instância quando existir: IP privado, Elastic IP, usuário SSH criado, Security Group aplicado.

## 6. Etapas

### E1 — Atualizar o pacote `voip/livekit-ec2/` (só arquivos locais)
Portar do `livekit-local` (versão atual, pós-M2.5), trocando rede Docker por host:
- `templates/asterisk/extensions.conf.tmpl`: versão atual (URA com `CURL()` e fallback, `URA_ATIVA`, `[ramais]`,
  `[from-livekit]` com `OUT_PREFIX` e `CALLERID(num)` = DID). `172.30.0.11:5060` (LiveKit SIP) →
  `127.0.0.1:5080`; `http://api.ipsys/api` → `${RAPIA_BASE_URL}` (= `https://apiflowip.ngrok.app/api`).
- `templates/asterisk/pjsip.conf.tmpl`: `external_media_address`/`external_signaling_address` = Elastic IP;
  `local_net` = CIDR da VPC e `127.0.0.0/8`; vizinho `livekit` em `127.0.0.1:5080`; `identify` do provedor com os
  4 IPs de entrada; `#include` dos ramais só se não quebrar sem o arquivo.
- `templates/asterisk/manager.conf.tmpl`: portar com AMI **só em 127.0.0.1**.
- `templates/asterisk/rtp.conf.tmpl`: `20000-20099`.
- `templates/livekit.yaml.tmpl`: `rtc.udp_port: 7882` (mux em porta única, como no local) no lugar de
  50000-60000; `tcp_port: 7881`; `node_ip: ${NODE_IP}`; TURN desligado; webhook para
  `https://apiflowip.ngrok.app/api/voice/livekit/webhook`; `empty_timeout`/`departure_timeout` iguais ao local.
- `templates/sip.yaml.tmpl`: `ws_url: ws://127.0.0.1:7880`, `sip_port: 5080`, Redis em 127.0.0.1,
  `rtp_port` 10000-19999 (só local, sem Security Group).
- `docker-compose.yml`: só `redis`, `livekit`, `sip`, `asterisk` (Caddy e Egress fora ou atrás de `profiles`).
- `scripts/render-config.sh` + `.env.example`: variáveis novas (`NODE_IP`, `RAPIA_BASE_URL`, `URA_ATIVA`,
  `URA_API_TOKEN`, `AMI_USER`/`AMI_SECRET`, `OUT_PREFIX`, `TIMEOUT_SAIDA` etc.; conferir no `render-config.ps1`
  quais o dialplan atual usa).
- `sip/`: JSON de inbound trunk (`allowed_addresses: 127.0.0.1/32`), outbound trunk (`address: 127.0.0.1:5060`,
  `numbers: +558431901994`) e **todas** as dispatch rules que o local usa hoje. Listar com `lk sip inbound list`,
  `lk sip outbound list` e `lk sip dispatch list` contra o LiveKit local (ainda no ar) e gerar um JSON equivalente
  para cada uma (IA `call-`, fila direta, ramais `ext-`), **sem copiar IDs**.
- Gerar a chave SSH dedicada (seção 4) e entregar a pública.
- **Prova**: diff dos templates; renderização de teste (Git Bash) sem `${...}` sobrando e sem segredo real.

### E2 — Provisionamento (usuário, no console AWS; assistente entrega o checklist)
Instância conforme seção 2; usuário SSH conforme seção 4. **Security Group de entrada, nada `0.0.0.0/0`**:

| Porta | Origem |
|---|---|
| 22/tcp | origem da VPN (seção 4) |
| 7880/tcp | origem da VPN |
| 7881/tcp, 7882/udp | origem da VPN (OpenVPN UDP) **ou** IP público do usuário (OpenVPN TCP) |
| 5060/udp, 5060/tcp | 189.113.38.59, 186.209.45.20, 186.209.52.214, 216.10.29.131, 52.67.163.135 (/32 cada) |
| 20000-20099/udp | os mesmos 5 IPs |

Não abrir 5080, 6379, 10000-19999, 5038 (tudo em 127.0.0.1).

### E3 — Subir a stack
`scp` do pacote → `bootstrap-host.sh` (Docker, Compose v2, envsubst, sysctl UDP) → usuário preenche o `.env`
(senha SIP) → `render-config.sh --gen-keys` → **usuário para o Asterisk local**
(`cd voip\livekit-local ; docker compose stop asterisk`) → `docker compose up -d`.
**Provas**: 4 serviços `running`; `curl http://127.0.0.1:7880` = OK; health do SIP; `pjsip show registrations` =
Registered; `ss -lunp` com 5060, 5080 e 7882; do PC, `curl http://<IP_EC2>:7880` pela VPN. Depois criar trunks e
dispatch rules com o `lk` (na EC2) a partir dos JSONs da E1 e anotar os IDs.

### E4 — Apontar o ambiente local (autorização por arquivo)
- `sysapi/.env`: `LIVEKIT_URL=http://<IP_EC2>:7880`, `LIVEKIT_WS_URL=ws://<IP_EC2>:7880`,
  `LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET` novos (o usuário cola; não exibir); `php artisan config:clear` se houver
  cache. Guardar os valores antigos para reverter.
- `voip/voice-agent/.env`: `LIVEKIT_URL=ws://<IP_EC2>:7880` + key/secret. Reiniciar o worker (PID em
  `voip/.agente.pid`, log `voice-agent/agent.log` em UTF-16) e confirmar que registrou no LiveKit remoto; garantir
  que não sobrou `agent.py` órfão.
- Túnel ngrok no ar (seção 2). `php artisan queue:work redis` no ar (eventos em tempo real).
- Medir RTT da VPN (`ping <IP_EC2>`).
- **Provas**: Playground do Estúdio conectando no LiveKit remoto (sala `pg-*`, fala da IA chegando);
  webhook chegando no Laravel pelo ngrok (evento `room_started` em `voice_call_events`).

### E5 — Ligações reais (cada uma autorizada)
1. **Entrada direta para a IA** (`URA_ATIVA=0`): ligar para 84 3190-1994; ouvir a IA; transcrição no Painel 360.
   Com `tcpdump` na faixa RTP, contar pacotes **recebidos** de `52.67.163.135` (no local davam 0 quando o Asterisk
   atendia).
2. **URA** (`URA_ATIVA=1` + render + `dialplan reload`): ouvir o menu, digitar 1 (IA) e 2 (fila). **É o teste que
   decide o bloqueio do M2.5**: com áudio → a causa era o Docker Desktop; mudo → o chamado com o provedor vira
   prioridade (Call-IDs de evidência estão no TODO).
3. **Saída** (pré-requisito do M4.3): `lk sip participant create` para o celular do usuário, caller ID = DID,
   áudio nos dois sentidos.

### E6 — Registro e reversão
- Atualizar o TODO: resultado do teste de mídia no M2.5 e uma subseção "Ambiente de homologação (EC2)" com IPs
  (sem segredos), portas, como subir/derrubar, e o que **não** foi verificado. Atualizar o
  `voip/livekit-ec2/README.md`. Atualizar a memória do projeto.
- Reversão sempre documentada: `docker compose down` na EC2; restaurar os `.env` locais; `docker compose start
  asterisk` no local e conferir `Registered`. Lembrar de **parar a instância** quando não estiver em uso.

## 7. Pendências anotadas (não resolver agora)
- **Ramais SIP (M2.5)**: o Laravel gera `pjsip_ramais.conf` no disco local e recarrega o Asterisk via AMI em
  `127.0.0.1:5038`; na EC2 isso exige AMI pela VPN e sincronização do arquivo.
- **Latência**: com o worker no PC o áudio faz provedor → EC2 → VPN → PC → Gemini → volta; serve para desenvolver,
  não representa produção (lá o worker ficaria junto do LiveKit).
- **Segurança**: rotacionar o `URA_API_TOKEN` (o valor apareceu num resultado de ferramenta em 25/09/2026).
- `max_call_seconds` da versão do agente ainda não é aplicado em ligação real.

## 8. Regras do usuário (obrigatórias)
1. Comece com um **plano curto** e espere o "ok"; depois avance sem perguntar, exceto nas ações a autorizar.
2. Pontos pequenos e verificáveis; **pare ao fim de cada etapa** (E1…E6), mostre as provas e pergunte antes de seguir.
3. Se algo deste prompt estiver errado diante dos arquivos reais, avise e proponha o ajuste.
4. **Nunca exiba nem logue segredos** (senha SIP, API secret, senha do Redis, tokens). Para ler um `.env`, filtre
   com `grep -v -i 'secret\|pass\|token\|key'`.
5. Git (sysapi/sysweb): nunca `git push`; sempre na `main`; commit só com autorização a cada vez; só `git add` de
   arquivos específicos. (Esta sessão deve mexer quase só em `voip/`, que não é git.)
6. Português do Brasil, respostas curtas, sem emojis. Não criar documentos não pedidos (atualizar TODO e READMEs
   de `voip/` é permitido).
7. Nunca digitar senha nem fazer login pelo usuário.
8. PHP local: `C:\wamp64\bin\php\php7.4.33\php.exe`. Tinker usa o banco `ipsys`: replicar o `CheckSubDomain`
   (SysConnect subdomínio `api`) no início do script.

## 9. Primeira resposta esperada
Plano curto (até ~15 linhas): o que conferiu nos arquivos, as diferenças `livekit-local` × `livekit-ec2` que vai
portar, as pendências da seção 5 e o que vai provar em cada etapa. Depois espere o "ok".
