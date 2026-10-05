# TODO — Rapia Voice V1 (versão de apresentação)

> Plano de ação para a primeira versão apresentável do módulo de atendimento por
> voz do RAPIA. Objetivo: **demonstrar para os primeiros prospects e colher
> requisitos reais**, não entregar produto final.
>
> Base já pronta e validada (set/2026): Asterisk (conta SIP do provedor) + LiveKit
> + LiveKit SIP + worker Python com Gemini Live atendendo ligação real, coletando
> nome/CPF/nascimento e chamando functions. Ver `voip/COMANDOS.md`.
>
> Status: **M0 concluído e commitado em 22-23/09/2026**; **M1 concluído e
> commitado em 22/09/2026** (exceto adapter do ERP real, pendente do
> cliente-alvo) — detalhes na seção 7. Commits: sysapi `7a4f00b` (M0),
> `1fda087` (M1), sysweb `454c725f` + `8ef78674` (M0) (locais, sem push).
> **M2 concluído e commitado em 23/09/2026** (Painel 360 — listas em tempo
> real, assumir com lock, encerrar, transferência entre atendentes). Commits:
> sysapi `a76ed0b`, sysweb `12bdf8be` (locais, sem push).
>
> **M2.5 planejado em 23/09/2026** (ainda não iniciado): URA estática de
> entrada, ramais SIP internos e presença do atendente — escopo que não
> tinha sido levantado na análise original, entra antes do M3 porque muda a
> premissa "a IA sempre atende primeiro". Detalhes na seção 7.
>
> **Data-alvo da primeira apresentação: 01/11/2026** (6 semanas) — **em risco**
> com a entrada do M2.5 (+9 a 12 dias não previstos); ver cronograma na seção 7.
>
> **REGRA DE GIT (prioridade alta): nunca `git push`. `git commit` somente após
> perguntar e receber autorização, a cada ponto desenvolvido.**
>
> **Revisado em 22/09/2026** contra o estado da arte de módulos de voz em
> sistemas web (seção 2.5): a arquitetura (LiveKit + SIP nativo + Asterisk como
> SBC) continua sendo a escolha recomendada. Os ajustes desta revisão estão
> marcados com 🆕 e não mudam prazo nem escopo — são detalhes que faltavam.

---

## 1. Princípio que guia a V1

Numa primeira apresentação, o que convence não é a quantidade de telas: é a
sensação de **produto de verdade rodando ao vivo**. A régua da V1 é conseguir,
sem cortes, esta sequência na frente do cliente:

> O prospect liga do próprio celular para o número da demo → uma URA estática
> atende ("digite 1 para consultas, 2 para exames...") → conforme a opção, ou
> a IA atende em português e faz a triagem, ou a chamada já cai direto numa
> fila humana específica → a chamada aparece na fila do Painel 360 (com os
> dados da IA já preenchidos, quando for o caso) → a atendente assume a
> ligação em um clique e conversa → encerra com resumo automático no
> histórico do contato → em seguida abrimos o Estúdio do Agente, mudamos uma
> frase do prompt, publicamos e ligamos de novo para ouvir a mudança.

Cada item deste TODO existe para sustentar essa sequência. O que não sustenta,
está na seção "Fora da V1".

---

## 2. Benchmark: o que já existe e o que vale copiar

### 2.1 Consoles de contact center (a régua de usabilidade do atendente)

| Produto | O que vale copiar |
|---|---|
| **Amazon Connect (CCP)** | Softphone enxuto e sempre visível, independente da tela aberta; estados de presença explícitos |
| **Genesys Cloud / Five9 / Talkdesk** | Barra de status do agente (disponível, pausa com motivo, pós-atendimento), timers de SLA na fila, códigos de encerramento (disposition) obrigatórios |
| **Twilio Flex** | Layout de 3 colunas (fila → interação → contexto do cliente) e painel de supervisão com escuta/sussurro |
| **Zendesk Talk / Chatwoot** | Histórico omnichannel do contato ao lado da conversa: voz e chat na mesma linha do tempo |

### 2.2 Plataformas de voz com IA (a régua de "ponta")

| Produto | O que vale copiar |
|---|---|
| **Vapi / Retell / Synthflow** | Estúdio do agente com prompt versionado, catálogo de tools com JSON Schema, botão "falar com o agente" no navegador, custo e latência por chamada |
| **ElevenLabs Agents** | Biblioteca de vozes com pré-escuta; ajuste de interrupção (barge-in) |
| **LiveKit Agents Playground** | Transcrição ao vivo lado a lado com o áudio e log de chamadas de tools em tempo real |
| **AssemblyAI / Level AI (agent assist)** | Transcrição ao vivo + próxima melhor ação para o humano; resumo e tags automáticos no pós-chamada |

### 2.3 Padrões que a V1 adota (e que criam o efeito "produto pronto")

- [ ] **Transcrição ao vivo** rolando enquanto a IA fala com o paciente — é o item de maior impacto visual e o mais barato de entregar (o worker já recebe o texto).
- [ ] **Dados extraídos aparecendo campo a campo**, preenchendo a ficha em tempo real conforme a IA confirma cada dado.
- [ ] **Timers em tudo**: tempo em fila, duração da chamada, tempo de resposta da IA.
- [ ] **Um clique para assumir**: sem discagem, sem transferência de ramal — o áudio simplesmente passa para a atendente (vantagem estrutural do LiveKit, e vale explicar isso na apresentação).
- [ ] **Resumo automático pós-chamada** com tags — parece mágico e é barato (uma chamada ao LLM com a transcrição).
- [ ] **Escuta silenciosa do supervisor** — impressiona gestor de clínica e já é nativo no LiveKit (token só de assinatura).

### 2.4 Diferencial competitivo a enfatizar na apresentação

O RAPIA já tem WhatsApp oficial, filas, agentes e histórico. Os concorrentes de voz
com IA **não têm o chat**; os concorrentes de contact center **não têm a IA
integrada ao WhatsApp**. A V1 precisa mostrar o paciente indo de voz para WhatsApp
sem perder contexto (cenários 3 e 4 da análise). Esse é o argumento central.

### 2.5 🆕 Confirmação da arquitetura (revisão de 22/09/2026)

Perguntou-se explicitamente se a estrutura escolhida continua sendo a mais
recomendada para módulos de voz em sistemas web. Resumo do que a pesquisa deste
mês confirma ou muda:

| Item | Veredito | Fonte / observação |
|---|---|---|
| LiveKit como base (SIP nativo + Agents) | **Confirmado.** Comparativos de 2026 continuam apontando LiveKit como a melhor opção para telefonia nativa em produção: SIP embutido no próprio servidor (Go), sem precisar de um Twilio no meio | Comparativos LiveKit x Pipecat x Twilio, set/2026 |
| Asterisk como SBC na frente do LiveKit SIP | **Confirmado**, é a solução padrão quando o provedor só oferece conta SIP com senha (o LiveKit SIP não registra) | Já validado com ligação real (19/09) |
| Modelo speech-to-speech nativo (Gemini Live) vs. pipeline STT→LLM→TTS | **Confirmado como padrão para latência baixa.** Só reduz o controle fino sobre o turno de fala, que é o item novo abaixo | Comparativos de frameworks de voz, 2026 |
| Turn-taking / barge-in | 🆕 **Gap identificado** — ver abaixo | Guias de barge-in e turn detection, 2026 |
| MCP (Model Context Protocol) para as ferramentas do agente | 🆕 **Tendência emergente** — ver seção 5 | LiveKit Agents já traz suporte nativo a MCP |
| Observabilidade por chamada (transcrição + trace + custo, tudo correlacionado) | 🆕 **Padrão do mercado** que a V1 deve reproduzir por conta própria (self-hosted não tem o produto gerenciado da LiveKit Cloud) | ver seção 4.2 |
| Custo do Gemini Live | 🆕 Número real obtido — ver seção 9 (Riscos) | Preço oficial do Gemini API, set/2026 |

**Sobre turn-taking (o gap real encontrado):** com um modelo speech-to-speech
nativo, quem decide quando o paciente terminou de falar é o próprio modelo — isso
reduz peças móveis, mas também reduz o controle da aplicação sobre a interrupção
(*barge-in*: o paciente falar por cima da IA). O RealtimeModel do Gemini Live tem
parâmetros de sensibilidade de interrupção (`realtime_input_config`), mas a V1
**ainda não testou nem ajustou isso** com áudio de telefone (8 kHz, ruído de
linha, atraso do SIP). Isso é diferente de testar em navegador com microfone
limpo. Ação adicionada ao M1 (seção 7).

**Sobre MCP:** não muda o desenho da V1 (o catálogo de ferramentas continua HTTP
+ JSON Schema, que é o suficiente e o que o time já conhece), mas é um motivo a
mais para manter a definição de cada ferramenta desacoplada do worker — ver nota
na seção 5.2. Se um dia o RAPIA quiser que o copiloto do chat WhatsApp use as
mesmas ferramentas do agente de voz, expor o mesmo catálogo via um servidor MCP
vira trabalho pequeno, não um redesenho.

---

## 3. Arquitetura da V1

```
                              ┌─► [opção 1] LiveKit SIP ─► sala (IA) ─┐
Provedor SIP ─► Asterisk (SBC)│                                       │
                URA estática  ├─► [opção 2] LiveKit SIP ─► sala (fila)┤
                (Background/  │                                       ▼
                 Read, DTMF)  └─► [timeout] fila padrão do tronco ─►  RAPIA API (Laravel 8)
                                                                        │      ▲
                              ramal ─► LiveKit SIP ─► sala pessoal ─────┘      │
                              (colega liga pro ramal, sem passar pela URA)    Pusher
                                                                                │
                            worker Python (rapia-voice, Gemini Live)           ▼
                                    │ carrega config / executa functions  Painel 360 (Vue 2)
                                    ▼                                          │
                         RAPIA API (Laravel 8)                        livekit-client (áudio)
                                    │
                              MySQL / Redis / S3
```

Decisões que já estão tomadas e não mudam na V1:

- O **worker é burro**: prompt, functions e regras vêm do RAPIA a cada chamada.
- O **RAPIA é o dono do estado**: filas, sessões, contatos, callbacks, histórico.
- O **Painel 360 fala com o LiveKit só para áudio**; todo o resto é API + Pusher.
- A V1 roda **na máquina local** (decisão 2): stack `voip/livekit-local` + Asterisk
  registrado na conta SIP, com o Laravel e o Vue do WAMP. O Egress entra nessa
  mesma stack para a gravação (decisão 5).
- 🆕 **A URA e o roteamento de entrada são decididos no Asterisk, não na IA nem
  no LiveKit** (decisão do M2.5, 23/09/2026): quem entra na sala (IA, ninguém,
  ou nem chega a existir sala) é resolvido pelo dialplan **antes** de discar
  pro LiveKit — mantém a IA fora da decisão de roteamento e evita abrir
  sala/worker pra quem desiste no meio do menu.
- 🆕 **Ramal SIP real, bridgeado pro LiveKit** (decisão do M2.5): ligação
  interna entre colegas não cria um segundo sistema de áudio — o Asterisk
  disca pra uma sala pessoal do usuário no LiveKit, e o mesmo softphone do
  Painel 360 (`V_Softphone.vue`) atende, com uma notificação de "chamada
  interna" antes de conectar.

---

## 4. Ponto 1 — Painel 360 do atendente

### 4.1 Desenho da tela

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Rapia Voice   [● Disponível ▾]  Fila: Central ▾      ⏱ 3 em espera  ☎ Discador │
├──────────────┬───────────────────────────────────┬────────────────────────────┤
│ EM CURSO (2) │  Maria da Silva · (84) 99999-0000 │  FICHA DO CONTATO          │
│ ┌──────────┐ │  Em triagem com IA · 01:12        │  Maria da Silva            │
│ │IA 01:12  │ │                                   │  CPF 123.456.789-00        │
│ │Maria S.  │ │  ── DADOS EXTRAÍDOS PELA IA ───── │  Nasc. 10/03/1980          │
│ │triagem   │ │  Nome ....... Maria da Silva   ✓  │  Convênio: Unimed          │
│ └──────────┘ │  CPF ........ 123.456.789-00   ✓  │                            │
│              │  Nascimento . 10/03/1980       ✓  │  HISTÓRICO (omnichannel)   │
│ EM FILA (3)  │  Motivo ..... remarcar consulta   │  • 19/09 WhatsApp - exames │
│ ┌──────────┐ │  Urgência ... normal              │  • 02/09 Voz 4m12 - agenda │
│ │⏱ 00:48   │ │                                   │  • 28/08 WhatsApp - boleto │
│ │João P.   │ │  ── TRANSCRIÇÃO AO VIVO ───────── │                            │
│ │[ASSUMIR] │ │  IA: Confirmando, 123.456.789-00? │  TAGS  [agendamento][idoso]│
│ └──────────┘ │  Paciente: Isso mesmo.            │  NOTAS  + adicionar        │
│              │  IA: Vou direcionar para um...    │                            │
│ RETORNOS (1) │                                   │  AÇÕES                     │
│ ┌──────────┐ │  ── LINHA DO TEMPO ────────────── │  [Assumir chamada]         │
│ │Ana L.    │ │  00:03 chamada atendida pela IA   │  [Enviar p/ WhatsApp]      │
│ │2ª tentat.│ │  00:41 buscar_paciente → achou    │  [Agendar retorno]         │
│ │[LIGAR]   │ │  01:05 registrar_triagem → ok     │  [Transferir fila ▾]       │
│ └──────────┘ │  01:10 pediu atendente humano     │  [Encerrar]                │
├──────────────┴───────────────────────────────────┴────────────────────────────┤
│ ☎ 00:00  [🎤 mudo] [⏸ espera] [123 teclado] [↗ transferir] [■ desligar]        │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Tarefas

**Backend**
- [ ] Migrations (`voice_calls`, `voice_call_events`, `voice_queue_entries`, `voice_callbacks`, `voice_transcripts`) — com a checagem `strpos($databaseName, 'rapia')` do CLAUDE.md
- [ ] 🆕 `voice_call_events` e `voice_transcripts` ganham `turn_seq` (inteiro, sequencial por chamada): é o que permite reconstruir "nesta fala do paciente, a IA chamou esta tool e respondeu isto" em uma única linha do tempo. É o mesmo princípio do produto de observabilidade da LiveKit Cloud (transcrição + trace + áudio correlacionados por turno) — como estamos self-hosted, replicamos isso nas nossas tabelas em vez de comprar o produto
- [ ] `VoiceCallsController`: listar em curso / em fila / retornos; detalhe da chamada; assumir (com lock atômico no Redis); encerrar; transferir
- [ ] `VoiceTokenController`: emite JWT do LiveKit por sala e papel (atendente publica / supervisor só escuta)
- [ ] `VoiceWebhookController`: recebe webhooks do LiveKit (`participant_joined/left`, `room_finished`) validando a assinatura
- [ ] `VoiceDialerController`: originar chamada (CreateSIPParticipant) a partir do discador e dos retornos
- [ ] Eventos Pusher no canal privado do tenant: `voice.call.started`, `voice.call.updated`, `voice.queue.updated`, `voice.transcript.appended`, `voice.callback.available`
- [ ] Job de pós-chamada: resumo + tags via LLM, gravação do S3 vinculada, atualização do histórico do contato

**Frontend (`pages/rapia/voz/Painel360.vue` + componentes em `components/componentes/rapia/voz/`)**
- [ ] Layout de 3 colunas seguindo os padrões de `MapaAgentesAtendimento.vue` (cards, tabelas, modais já existentes)
- [ ] `V_ListaChamadas.vue` — abas Em curso / Em fila / Retornos, com timers ao vivo
- [ ] `V_FichaChamada.vue` — dados extraídos, transcrição ao vivo, linha do tempo
- [ ] `V_Contato360.vue` — histórico omnichannel (reaproveita as sessões de WhatsApp existentes)
- [ ] `V_Softphone.vue` — barra fixa: mudo, espera, teclado DTMF, transferir, desligar (base pronta em `voip/livekit-local/test/atendente.html`)
- [ ] `V_Discador.vue` — teclado para originação manual + busca de contato por nome/telefone
- [ ] Serviço `livekit.js` no Vuex: conectar, publicar microfone, tocar áudio remoto, eventos
- [ ] Carregar `livekit-client` pelo bundle UMD (Webpack 3 não transpila o pacote moderno)
- [ ] Permissão de microfone e device picker (headset) com aviso claro quando negada

**Riscos desta frente**
- Webpack 3 + `livekit-client`: resolver **no primeiro dia** da M2, é o risco que pode empurrar o cronograma.
- Latência percebida ao assumir a chamada: medir; se passar de ~2 s, pré-conectar a atendente na sala em modo mudo.

---

## 5. Ponto 2 — Estúdio do Agente (prompt + functions)

### 5.1 Decisão de produto proposta

O `DrawFlowAA.vue` resolve fluxo determinístico (chatbot). Agente de IA por voz
**não é fluxograma**: é prompt + ferramentas + guardrails. Forçar o Drawflow aqui
geraria uma tela bonita e inútil, e ainda esbarraria no Vue 2.5.

**Decidido:** editor estruturado por blocos **mais uma aba de visualização do
fluxo em modo leitura**, gerada a partir da configuração e desenhada com o
Drawflow que já existe no projeto. Configura-se nos blocos; a aba de fluxo serve
para explicar o agente ao cliente na apresentação, sem o risco de um editor
gráfico que não corresponde ao que o modelo faz em tempo real.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Estúdio do Agente · "Triagem Central"        v3 (publicada)  [Publicar] │
├───────────────┬─────────────────────────────────────────────────────────┤
│ ▸ Identidade  │  BLOCO: Coleta de dados                                 │
│ ▸ Objetivo    │  ┌───────────────────────────────────────────────────┐  │
│ ▪ Coleta      │  │ Peça um dado por vez, nesta ordem: nome completo, │  │
│ ▸ Regras      │  │ CPF e data de nascimento. Confirme cada um...     │  │
│ ▸ Encerramento│  └───────────────────────────────────────────────────┘  │
│ ▸ Guardrails  │  Variáveis: {{clinica}} {{horario}} {{data_hoje}}       │
│               │                                                         │
│ FERRAMENTAS   │  FERRAMENTAS HABILITADAS                                │
│ ▪ internas    │  [x] registrar_triagem      [x] transferir_humano       │
│ ▪ integrações │  [x] buscar_paciente (ERP)  [x] enviar_whatsapp         │
│               │  [x] agendar_callback       [ ] agendar_consulta (ERP)  │
│ VOZ E MODELO  │                                                         │
│ Modelo ▾ Voz ▾│  [ ▶ Falar com o agente ]   [ Testar ferramenta ]       │
└───────────────┴─────────────────────────────────────────────────────────┘
      Abas:  [ EDITOR ]   [ VISÃO DO FLUXO (somente leitura) ]
```

A aba de fluxo é gerada a partir da configuração, não editada:

```
  [Atende]──►[Coleta 3 dados]──►[registrar_triagem]
                                       │
                    ┌──────────────────┴────────────┐
                    ▼                               ▼
             [transferir_humano]            [enviar_whatsapp]
```

### 5.2 Tarefas

**Backend**
- [ ] `voice_agents` (nome, modelo, voz, temperatura, idioma, saudação, tempo máx., fila padrão) — avaliar estender a tabela `cad_agentes_ia` existente, que já tem `prompt` e vector storages
- [ ] `voice_agent_versions` (blocos do prompt em JSON, rascunho/publicada, autor, data, rollback)
- [ ] `voice_agent_tools`: ferramentas internas (catálogo fixo) + externas **reaproveitando `cad_integracoes`/`cad_integracoes_params`/`cad_integracoes_headers`**, que já existem para campanhas
- [ ] Endpoint de runtime `GET /voice/agents/{id}/runtime` consumido pelo worker no início de cada chamada
- [ ] Executor de tools: valida parâmetros (JSON Schema), aplica timeout, registra em `voice_call_events`, guarda credenciais fora do prompt
- [ ] Ferramentas internas da V1: `registrar_triagem`, `buscar_paciente`, `transferir_humano`, `enviar_whatsapp`, `agendar_callback`, `encerrar_chamada`
- [ ] 🆕 Nota de arquitetura (sem tarefa extra na V1): definir cada ferramenta como
      {nome, descrição, JSON Schema dos parâmetros, endpoint} independente do
      worker é o que já estava planejado — e é também o formato que um servidor
      MCP exige. Não construir MCP agora; só evitar acoplar a definição da
      ferramenta ao código do worker, para não redesenhar se um dia o copiloto do
      chat WhatsApp quiser usar o mesmo catálogo
- [ ] **ERP Demo**: adapter falso com pacientes e agenda fictícios, para a apresentação não depender de integração real

**Frontend (`pages/rapia/voz/EstudioAgente.vue`)**
- [x] Editor por blocos com variáveis e contador de caracteres
- [x] Versões: rascunho, publicar, comparar, reverter
- [x] Catálogo de ferramentas com liga/desliga e formulário da integração HTTP (método, URL, headers, params, mapeamento de resposta)
- [x] Botão "Testar ferramenta" com valores de exemplo, mostrando requisição e resposta
- [x] **Playground**: "Falar com o agente" pelo navegador usando a versão rascunho, com transcrição e log de tools ao lado
- [x] Seletor de voz com pré-escuta (E6; com lista de vozes recomendadas pelo responsável)
- [x] Aba "Visão do fluxo": monta o JSON do Drawflow a partir do agente (blocos +
      ferramentas habilitadas) e renderiza em modo leitura, sem edição

**Worker**
- [ ] Ler `agent_id`/`tenant` dos metadados do dispatch e buscar a configuração no RAPIA
- [ ] Montar prompt e tools dinamicamente a partir do JSON (hoje estão fixos em `agent.py` e `prompt.md`)
- [ ] Publicar transcrição e eventos de tool no RAPIA (HTTP) para alimentar o painel
- [ ] Cache curto da configuração + recarregar quando uma versão for publicada

---

## 6. Ponto 3 — Menu e acesso restrito a SUPER

- [ ] Bloco novo em `components/layouts/Menu.vue`, no padrão já usado:
      `v-if="['1','5'].includes(getConfig.projeto_id) && getSuperUser == 'S'"`
- [ ] Itens: **Voz** → Painel 360 · Estúdio do Agente · Números e Troncos · Histórico de Chamadas
- [ ] Rotas em `router/index.js` com guarda por SUPER (não basta esconder o menu)
- [ ] Criar as chaves de permissão desde já (`RAPIAVOICEPAINEL`, `RAPIAVOICEESTUDIO`, `RAPIAVOICEADMIN`) em `SysPermissoes`, mesmo que a V1 só libere para SUPER — evita retrabalho quando abrir para atendentes
- [ ] Validar a permissão **também no backend**, em todas as rotas `/voice/*`

---

## 7. Fases e entregas

Estimativas em dias de desenvolvimento, para uma pessoa focada. Ajustar conforme
o time.

### M0 — Fundação (3–4 dias) ✅ concluído em 22-23/09/2026
- [x] Migrations e models (6 tabelas `voice_*` + permissões + token do worker;
      rodado e testado via `php artisan migrate:all`, só pega no `ipsys-rapia`)
- [ ] Levantar a API do ERP do cliente-alvo: endpoints de paciente e agenda,
      autenticação, limites e ambiente de teste (credenciais já disponíveis) —
      **pendente**: entra no M1, depende do cliente-alvo estar confirmado
- [x] Rotas `/voice/*` autenticadas + permissões + menu SUPER (`voice.access`
      middleware; menu em Menu.vue e guarda em router/index.js; testado com
      usuário SUPER, usuário comum e sem token)
- [x] Emissão de token do LiveKit e webhooks recebidos e gravados (validado
      contra o LiveKit real via `/rtc/validate`; assinatura, idempotência e
      sala fora do padrão testados por curl e por ligação real)
- [x] Ambiente local conferido de ponta a ponta com `voip/iniciar.ps1` (webhook
      apontando para a rota real, `extra_hosts: api.ipsys:host-gateway`)
- **Pronto quando:** uma chamada real aparece gravada em `voice_calls` com sua
  linha do tempo. **Confirmado** com uma chamada de teste via Asterisk passando
  pelo webhook real: `room_started` → `participant_joined` (SIP + agente) →
  `participant_left` → status `ended` com duração calculada.

  **Detalhes técnicos que só apareceram na implementação** (não estavam no
  plano original, registrados aqui para o M1 não redescobrir):
  - Formato de sala confirmado por ligação real e webhook: um evento
    `participant_joined` com `kind=SIP` é o paciente (telefone em
    `attributes["sip.phoneNumber"]`, `anonymous` quando oculto); um com
    `kind=AGENT` e `identity="agent-AJ_..."` é o worker de IA.
  - Assinatura do webhook: `Authorization` traz o JWT **sem** prefixo "Bearer ",
    claim `sha256` = base64(sha256(corpo bruto)). Confirmado capturando um
    webhook real antes de escrever o validador (nunca documentado a esse nível
    de detalhe pela doc pública consultada).
  - `sys_permissoes_funcs.user_type` (FK para `users_types`) só existe por uma
    migration de alteração posterior à criação da tabela — permissão nova
    nasce sem especificar o campo (fica com o default).
  - Rota do webhook fica **fora** do middleware `subdominio`, no mesmo padrão
    já usado pelo webhook da Meta (URL única, tenant resolvido pelo payload) —
    reaproveitado em vez de inventado.
  - Achado à parte, sem relação com o código: havia dois processos `agent.py`
    esquecidos rodando desde uma sessão anterior. Como a dispatch rule estava
    em modo "agente", a chamada de teste chegou a ser atendida de verdade pelo
    Gemini por alguns segundos antes de eu perceber e encerrar os processos.
    Vale um hábito de conferir `Get-Process` antes de testar chamadas.

### M1 — IA conectada ao RAPIA (4–6 dias) ✅ concluído em 22/09/2026 (exceto ERP)
- [x] Worker carregando prompt e tools do banco (`GET /voice/agents/{id}/runtime`)
- [x] Tools internas (`registrar_triagem`, `transferir_para_atendente`, via
      `POST /voice/worker/tools/{name}`)
- [x] 🆕 **Calibrar barge-in em áudio telefônico:** testado com ligação real
      (celular → provedor SIP → Asterisk → LiveKit). `realtime_input_config`
      configurado com `start_of_speech_sensitivity=HIGH` e
      `end_of_speech_sensitivity=HIGH` (`VOICE_START_SENSITIVITY`/
      `VOICE_END_SENSITIVITY` no `.env` do worker) — a IA parou de falar assim
      que interrompida, sem corte falso por ruído de linha. Mantido HIGH/HIGH
      como padrão; não precisou de ajuste.
- [ ] **Adapter do ERP real** do cliente-alvo (paciente e agenda) — **pendente**:
      cliente-alvo/ERP ainda não confirmado (mesma pendência da seção 10).
      Tools que não dependem de ERP (triagem, transferência) não foram afetadas.
      **DECISÃO (05/10/2026): item CANCELADO no Voice.** Não haverá adapter de ERP só do VOIP. A comunicação com Klingo/Smart é
      feita uma vez, no Flow Studio/`sysflow` (conectores), e consumida por fluxos, pela IA de voz, pelo painel do atendente
      (Assistant do /chat e ficha do /voice/painel) e por formulários de agendamento. Blocos E0–E5, ordem e decisões em
      `ALINHAMENTO-VOIP-FLOW-STUDIO.md` (raiz). O ERP Demo continua como servidor de demonstração, por trás de um conector.
- [ ] Modo de contingência do adapter — **cancelado**: o circuito/contingência é dos conectores do `sysflow` (ver alinhamento)
- [x] Triagem gravada, contato criado/vinculado. Eventos ficam em
      `voice_call_events` (não há broadcast Pusher específico do M1 — o
      `VoiceCallUpdated` do M0 já cobre mudança de status; um evento dedicado a
      "triagem atualizada" fica para o M2, quando o Painel 360 for escutar isso)
- **Pronto quando:** a IA atende, coleta, registra no RAPIA e enfileira o
  contato. **Confirmado** com ligação real (84988345243 → sala
  `call-api_84988345243_5UbHiDa2S7XT`): `voice_calls.triage` preenchido,
  `contact_id` vinculado a um contato já existente (sem sobrescrever nome),
  15 turnos em `voice_transcripts`, 2 pares `tool_called`/`tool_result` em
  `voice_call_events` com `turn_seq` correlacionado.

  **Detalhes técnicos que só apareceram na implementação** (registrados para o
  M2/M3 não redescobrir):
  - **Modelagem do agente:** decidido criar `voice_agents` /
    `voice_agent_versions` / `voice_agent_tools` em vez de estender `ia_agents`
    (`App\Models\Rapia\AgenteIa`) — aquela tabela é do copiloto de texto do
    WhatsApp (RAG com `ia_agents_vs`), sem noção de modelo/voz/temperatura nem
    de tools com JSON Schema. `voice_calls.agent_id` e `VoiceCall::agent()`,
    que o M0 tinha deixado apontando para `cad_agentes_ia`/`AgenteIa` por
    presunção, foram corrigidos para `voice_agents`/`VoiceAgent`.
  - **JSON Schema de tool sem parâmetros:** o cast `'array'` do Eloquent
    colapsa `{}` (objeto vazio) em `[]` ao ir e voltar do banco — um
    `"properties": []` não é um JSON Schema válido e o function-calling do
    Gemini rejeitaria. `VoiceAgentRuntimeController` decodifica
    `getRawOriginal('parameters_schema')` sem `assoc` para preservar `{}`.
  - **`sysapi/.env` não aceita valor com espaço sem aspas:** adicionar
    `VOICE_CLINICA_NOME=Clínica Coopab` sem aspas quebrou o parser do
    `vlucas/phpdotenv` e **toda a API passou a responder 200 com corpo vazio,
    silenciosamente** (sem log — quebra antes do bootstrap). Precisa de aspas:
    `VOICE_CLINICA_NOME="Clínica Coopab"`. Vale conferir isso primeiro se uma
    rota parar de responder do nada depois de mexer no `.env`.
  - **Contato por telefone:** `contacts.number` não tem convenção clara de
    formato (com ou sem DDI) entre os fluxos existentes; `localizaOuCriaContato`
    casa pelos **últimos 8 dígitos** (`RIGHT(number, 8)`), o mesmo critério
    "fuzzy" que `ContactsController::validNumberWhats` já usa para achar
    `accounts` do WhatsApp. Não sobrescreve nome/CPF/nascimento que o contato já
    tinha — só completa o que estava vazio.
  - **Metadados do dispatch:** `agent_id` viaja em
    `room_config.agents[0].metadata` (JSON) na dispatch rule — confirmado no
    protobuf `livekit.protocol.room.RoomAgentDispatch` (campo `metadata`,
    `str`). Chega ao worker em `ctx.job.metadata` (protobuf `agent.Job`, mesmo
    campo). Sem isso (`agent.py console`, sem dispatch rule), cai no
    `VOICE_AGENT_ID` do `.env`.
  - **Tools dinâmicas no worker:** `function_tool(impl, raw_schema={...})` do
    `livekit-agents` aceita uma function assíncrona `async def
    _executa(raw_arguments: dict) -> Any` sem precisar de introspecção de
    assinatura Python — é o mesmo padrão que o próprio `livekit.agents.llm.mcp`
    usa para expor tools de um servidor MCP. Cada chamada vira um
    `POST /voice/worker/tools/{name}`; erro vira `ToolError` (o modelo recebe o
    erro e decide o que fazer, não é uma exceção que derruba a sessão).
  - **`agent.py console --text` não dá para automatizar:** usa
    `prompt_toolkit`, que exige TTY de verdade — texto mandado via stdin
    pipado não chega como fala do usuário. Validar a mecânica sem telefone só
    dá pra fazer até a saudação; o resto (tool-calling, barge-in) precisa de
    sessão interativa de verdade (console com humano digitando, ou ligação).
  - Achado à parte: `mysql` (cliente CLI do WAMP) mostra acento errado em
    alguns `SELECT` sem `--default-character-set=utf8mb4` — é só exibição do
    cliente; os dados no banco e as respostas HTTP (curl) sempre vieram em
    UTF-8 correto.

### M2 — Painel 360 (5–7 dias) ✅ concluído em 23/09/2026 (exceto escuta do supervisor)
- [x] Listas em tempo real (em curso / em fila / retornos) com timers, ficha da
      chamada (dados extraídos, transcrição ao vivo, linha do tempo), contato
      360 (histórico omnichannel voz + WhatsApp)
- [x] Softphone WebRTC (LiveKit) + assumir chamada com lock atômico (Redis) +
      encerrar (derruba a sala no LiveKit/Asterisk) + transferência direta
      entre atendentes
- [ ] Escuta do supervisor — **não implementado nesta rodada**. O token
      `role=supervisor` (`canPublish=false, hidden=true`) já existe desde o M0
      em `VoiceTokenController::token`, só falta a tela consumir. Fica como
      pendência pro M3/M4.
- **Pronto quando:** a atendente assume pelo navegador sem a ligação cair.
  **Confirmado** em teste real no navegador (Chrome, via `npm run dev`):
  chamada sintética em fila → assumida → LiveKit conectado de verdade
  (`connected to Livekit Server... 1.13.7`, microfone publicado, evento
  `track_published` gravado em `voice_call_events` por webhook real) →
  transferida para outro atendente (evento "transferida de X para Y" na linha
  do tempo, softphone de quem perdeu a chamada desconectou sozinho via reação
  do Vue, sem código extra pra isso) → encerrada (`DeleteRoom`, `status=ended`,
  duração calculada).

  **Detalhes técnicos que só apareceram na implementação** (registrados pro
  M3/M4 não redescobrir):
  - **`livekit-client` no Webpack 3**: resolvido copiando o bundle UMD
    (`livekit-client@2.22.3`, pinado) pra `sysweb/static/assets/js/` e um
    `<script>` a mais no `index.html` — exatamente o mesmo padrão que o
    projeto já usa pra Drawflow/ApexCharts/GridJS (bibliotecas grandes que o
    Babel 6 não transpila não entram via `npm import`, entram como vendor
    estático expondo `window.LivekitClient`). Zero dependência nova no
    `package.json`.
  - **Fila da V1 é única**: `voice_queue_entries.queue_id` fica `null`
    (decisão do usuário, 23/09/2026) — o "Fila: Central" do desenho da tela
    (seção 4.1) é só rótulo, sem seleção de fila real. **Pendência**: quando
    o sistema precisar de mais de uma fila de voz, revisar
    `VoiceWorkerToolController::transferirParaAtendente` (hoje sempre cria
    `queue_id=null`) e o board do `VoiceCallsController`.
  - **Redis lock (`assumir`) — cuidado com a assinatura do Laravel**:
    `Illuminate\Redis\Connections\PhpRedisConnection::set()`/`eval()` usam a
    forma **posicional** (`Redis::set($k,$v,'EX',10,'NX')`,
    `Redis::eval($script,1,$key,$arg)`), não o array de opções nativo do
    phpredis (`['NX','EX'=>10]`) mesmo com `REDIS_CLIENT=phpredis` no `.env` —
    o wrapper do Laravel já monta esse array por baixo. Passar o array direto
    quebra silenciosamente (warning "Illegal offset type", NX vira SET normal).
    Achado testando via `php artisan tinker` antes de plugar no frontend.
  - **Canal privado x broadcast, condicionado por `ENABLE_PRIVATE_CHANNELS`**:
    canais privados do projeto (todos, não só voz) estão em análise pendente
    de liberação — hoje `ENABLE_PRIVATE_CHANNELS=N` no `.env` (`sysapi`) /
    `enable_private_channel=N` no `config.conf` (`sysweb`). Segui o mesmo
    padrão que `App\Events\Flow\RefreshChat` (público) /
    `RefreshChatPrivate` (privado) já usa pro chat: `VoiceCallUpdated::
    broadcastOn()` decide entre `PrivateChannel("voice.{tenant}")` e
    `Channel("channel.{tenant}")` (o mesmo canal público que `RefreshChat`/
    `SendRefresh` já usam) por essa mesma flag, num único lugar — quando os
    canais privados forem liberados, só muda a env var. No frontend,
    `Painel360.vue` escuta o evento certo em cada canal e, no modo
    broadcast, só dá `stopListening()` ao sair da tela (nunca `leave()`,
    porque `channel.{tenant}` é compartilhado com o resto do app).
  - **Transferência não mexe no LiveKit**: só troca `voice_calls.user_id`. A
    sala continua a mesma; quem perde a chamada tem o softphone desmontado
    pelo próprio Vue (o computed que decide "mostrar softphone" já checava
    `user_id === currentUserId`) e desconecta sozinho do LiveKit — confirmado
    no log real (`track_unpublished` → `participant_left` logo após o
    transfer). Quem recebe conecta pelo mesmo fluxo do "assumir".
  - **Bug de UI achado testando (não teórico)**: o botão "Transferir" usava
    `!atendenteDestino` pra decidir se estava habilitado — `id=0` é um user_id
    real no banco (conta "Sistema") e `!0` é `true` em JS, então o botão nunca
    habilitava pra esse destino. Corrigido pra `atendenteDestino === ''`.
    Excluí também esse id=0 da lista de atendentes disponíveis pra
    transferência (`VoiceCallsController::attendants`) — é conta de
    sistema/serviço, não uma atendente de verdade.
  - **"Retornos" sempre vazio por enquanto**: nada popula `voice_callbacks`
    até o M4 (fila de retornos); a coluna já existe na tela, só não tem dados.
  - Ambiente de teste: LiveKit local (`voip/livekit-local`) já estava no ar
    durante toda a sessão (não iniciado por esta sessão, não parado por ela).

### M2.5 — Ramais, URA de Entrada e Presença do Atendente (9–12 dias) 🆕 planejado em 23/09/2026 — **concluído em 24/09/2026; URA provada em ligação real em 25/09/2026 na EC2 de homologação (a causa do áudio mudo era o NAT do Docker Desktop, ver o achado abaixo e a seção 7.3)**

Escopo levantado numa conversa com o usuário sobre pontos que não tinham
entrado na análise original (mercado/benchmark da seção 2, nem nos marcos
M0–M5): URA estática antes da IA, ramais internos de verdade, ramal padrão
por usuário e presença do atendente. Entra **antes** do M3 porque muda a
premissa "a IA sempre atende primeiro", que o Estúdio do Agente do M3 herdaria
se fosse construído antes.

**Decisões tomadas nesta fase (23/09/2026)**

| # | Decisão | Escolha | Por quê |
|---|---|---|---|
| 1 | Onde roteia a URA | **Dialplan do Asterisk** (`Background`/`Read`), não a IA nem o LiveKit | É literalmente pra isso que o Asterisk existe; quem desiste no meio do menu nunca abre sala/worker (economiza custo de IA); mantém a IA fora da decisão de roteamento |
| 2 | Tipo de ramal | **SIP real**, registrado no Asterisk | Ligação interna colaborador-a-colaborador de verdade, não só um número de exibição |
| 3 | Como o ramal toca pro atendente | **Bridgeado pro LiveKit**, reaproveitando o `V_Softphone.vue` do M2 | Evita um segundo sistema de áudio paralelo — mesma stack (LiveKit + `livekit.js`) atende paciente e colega |
| 4 | Presença do atendente | **Automática no login/ao abrir o Painel 360**, sem modal | Mesmo padrão que `users.chat_status` já usa pro chat hoje (confirmado em `UserController.php`) — não existe modal de presença em nenhuma tela do projeto |

**Backend**
- [x] `voice_extensions` (migration + model `App\Models\Rapia\VoiceExtension`):
      `extension_number`, `user_id` (sem FK), `sip_password` (cast `encrypted`
      no model — nunca em texto puro no banco, confirmado via tinker: valor
      cru é um blob cifrado, `$model->sip_password` decifra sozinho), `status`.
      Testado com `php -l` em todos os arquivos + `migrate:all` + tinker
      (create/read/delete) só na base `ipsys-rapia`, confirmado ausente nas
      outras (`ipsys-02`).
- [x] `voice_trunks` (migration + model `VoiceTrunk`) e `voice_ura_options`
      (migration + model `VoiceUraOption`, FK real pra `voice_trunks`/
      `voice_agents` por serem do mesmo módulo — `queue_id` continua sem FK,
      mesmo padrão de `voice_agents.default_queue_id`) — schema pronto pro
      cadastro de Números/Troncos e pro "dígito→destino" da URA; **os
      endpoints/telas ainda não existem**, só as tabelas+models.
- [x] `users.voice_status` (campo próprio, não reaproveita `chat_status` — ver
      comentário na migration: `chat_status` já é setado uma vez no login e
      significa "logado no chat", presença de voz precisa do próprio ciclo de
      vida ligado ao Painel 360) e `users.default_extension_id` (sem FK) —
      migration feita, **endpoint/regra de negócio ainda não implementados**.
- [x] **Decisão técnica fechada em 23/09/2026**: **template + reload via AMI**,
      não Realtime PJSIP. Testado antes de decidir: a imagem `andrius/asterisk`
      tem os módulos de Realtime compilados (`res_odbc`, `res_sorcery_realtime`,
      `pbx_realtime`...) mas **nenhum driver ODBC de MySQL/MariaDB instalado**,
      e a imagem é usada direto do Docker Hub (sem Dockerfile próprio no
      projeto) — um `apt-get install` do driver não sobreviveria a um próximo
      `--force-recreate`. Asterisk fica **sem conexão direta ao MySQL**; quem
      lê `voice_extensions` é o Laravel (como qualquer tabela `rapia`), que
      gera a config equivalente ao `pjsip_ramais.conf` (hoje gerado à mão por
      `voip/livekit-local/scripts/render-ramais.ps1` a partir de
      `ramais/ramais.json` — andaime temporário) e dispara reload via AMI.
      🆕 **Pendência para fase futura**: validar se o MySQL do WAMP aceita
      conexão vinda do container pelo mesmo mecanismo `extra_hosts:
      host-gateway` já usado pro Apache (`api.ipsys`) — não testado ainda
      (depende de `bind-address` no `my.ini` e dos grants do usuário `root`,
      hoje só usado via `127.0.0.1`). Isso reabriria a conversa sobre Realtime
      **se** um dia a lista de ramais crescer o bastante pra o custo do reload
      via AMI incomodar — não é bloqueio pra V1.
- [x] `VoiceWebhookController` reconhece `fila-{tenant}_...` e
      `filapadrao-{tenant}_...` (URA sem IA), além de `call-{tenant}_...`
      (fluxo com IA, inalterado) — `REGEX_SALA` virou
      `/^(call|fila|filapadrao)-([a-z0-9]+)_([^_]*)_([A-Za-z0-9]+)$/`. Quando
      o paciente (kind=SIP) entra numa sala `fila-`/`filapadrao-`, o webhook
      já faz a mesma transição que `VoiceWorkerToolController::
      transferirParaAtendente` faz no fluxo com IA (status→`queued`,
      `queued_at`, cria `VoiceQueueEntry`) — direto pro board do Painel 360,
      sem nunca passar por status `ai`. Testado com **3 ligações sintéticas
      reais** (webhook de verdade, `api.ipsys` respondendo): opção 2 →
      `voice_calls` id 11 (`fila-api_...`, status `queued`, 1 queue entry);
      timeout → id 12 (`filapadrao-api_...`, idem); opção 1 → id 13
      (`call-api_...`, status ficou `ringing`, 0 queue entries — confirma que
      o fluxo com IA não mudou).
- [x] Ramal interno (`ext-{tenant}_...`) reconhecido no `VoiceWebhookController`
      (`REGEX_SALA` ganhou o 4º prefixo) e tratado à parte em `handleRamal()`:
      **não vira `voice_calls`** (decisão — aquela tabela é de chamada de
      paciente, `contact_id`/`triage`/`summary` não fazem sentido pra ligação
      interna); é só um evento efêmero. Em `participant_joined` (kind=SIP), lê
      `sip.trunkPhoneNumber` (o ramal discado — não está no nome da sala nem em
      `sip.phoneNumber`, confirmado por ligação sintética), busca
      `VoiceExtension` pelo número, e dispara `VoiceCallUpdated` op
      `internal.ringing` com `target_user_id`/`from_extension` — mesma classe
      de evento reaproveitada, sem herdar nada de `voice_calls`. Ramal
      inexistente/inativo/sem usuário: loga e ignora, não quebra.
      **Testado com ligação sintética real** ramal→ramal (1002, ramal de teste
      vinculado a um usuário real): log confirma `user_id` e ramal corretos;
      **ramal de teste ficou no banco** (`voice_extensions` id 2, `1002`) de
      propósito, como fixture pro próximo marco (frontend) testar o
      `V_Softphone.vue` sem precisar recriar o cadastro.
      Achado à parte, não relacionado a esta mudança: log tem um erro antigo
      (11:33, sessão anterior) de `Pusher\Pusher::__construct()` com
      argumento nulo, ao registrar `routes/channels.php` no boot — parece
      ligado a `ENABLE_PRIVATE_CHANNELS=N`/Pusher não configurado localmente;
      não impediu o evento de disparar (log da minha mudança veio limpo logo
      depois), mas vale investigar antes do M3 se for atrapalhar algo visível.
- [x] **Endpoint/regra pra "dígito da URA → destino", ligado de verdade em
      24/09/2026** (decisão revista: o usuário preferiu ligar já, em vez de
      deixar pro roadmap). `VoiceUraRuntimeController::resolve`
      (`GET /voice/ura/runtime?did=&digit=`) responde em **texto puro**
      (`agent`/`queue`/`none`, não JSON — dialplan não tem parser de JSON sem
      módulo extra), autenticado pelo mesmo `x-api-key`/`VOICE_WORKER_TOKEN`
      que o worker Python usa (reaproveitado de propósito: ambos são
      chamadores de infra confiáveis, nunca o navegador).
      **Pré-requisito resolvido**: `docker-compose.yml` ganhou
      `extra_hosts: api.ipsys:host-gateway` no serviço `asterisk` (mesmo
      mecanismo que o `livekit` já usa e já está validado desde o M0) — testado
      com `curl` de dentro do container: resolve e responde em ~7ms.
      `[from-provedor]` trocou os dois `exten => 1,1.../exten => 2,1...`
      hardcoded por um único `exten => _[0-9],1...` que roda `CURL()` com
      `CURLOPT(conntimeout)=1`, `CURLOPT(httptimeout)=2` e o header
      `x-api-key`, e decide o destino por `GotoIf` no resultado — **qualquer**
      resposta que não seja exatamente `"agent"` ou `"queue"` (incluindo vazio,
      erro, timeout) cai no mesmo `Goto(t,1)` do timeout de dígito, ou seja,
      no fallback seguro de sempre (fila padrão). Token do worker duplicado
      como global `URA_API_TOKEN` em `extensions.conf.tmpl` (sem sincronização
      automática se o token rotacionar — registrado como pendência menor).
      **Testado com ligações sintéticas reais e a API rodando de verdade**:
      dígito 1 → consulta real → `"agent"` → discou o DID; dígito 2 →
      `"queue"` → discou `9990101`; dígito sem opção cadastrada (`5`) →
      `"none"` → caiu em `9990102` (fila padrão). **Testado o cenário de
      falha** apontando o `CURL()` pra um IP não roteável: falhou em ~1s
      (limitado pelo `conntimeout`), devolveu vazio, sem travar nem derrubar a
      ligação — prova que a API cair no meio de uma chamada real não quebra a
      demo.
      **Limite que continua valendo** (documentado no controller): isto só
      escolhe ENTRE os dois caminhos que já existem fisicamente no LiveKit
      (trunk do DID com agente / trunk sem agente) — não suporta múltiplos
      agentes ou filas específicas de verdade ainda, isso exigiria um
      trunk+dispatch-rule por destino (provisionamento novo, não só esta
      consulta). Fica pro dia em que precisar de mais de um agente/fila.
- [x] Evento novo (`VoiceCallUpdated`, op `internal.ringing`) pra notificar o
      navegador da atendente-alvo quando uma ligação interna chega — implementado
      junto com `handleRamal()` (ver bullet acima). O softphone do M2 conecta
      automaticamente ao assumir uma chamada de paciente; ligação interna
      precisa perguntar antes ("Atender/Recusar") — **isso é frontend, ainda
      não feito**.
- [x] **`VoiceExtensionsController` (CRUD de ramais) + reload via AMI**,
      completando a decisão técnica de cima. Peças novas:
      - `app/Services/Voice/AsteriskAmiService.php`: protocolo AMI cru via
        socket (sem SDK/dependência nova, mesmo espírito do `LiveKitService`
        e do `dispatch.py`) — `login()` + `Action: Command` (usado com
        `pjsip reload`).
      - AMI habilitada no Asterisk (`manager.conf` novo, gerado por
        `render-config.ps1`) e publicada **só em `127.0.0.1`** no
        `docker-compose.yml` (nunca `0.0.0.0` — motivo: `command`/`reload` são
        permissão de administração total do Asterisk, e a sessão já viu
        tráfego de scan real batendo na porta SIP pública; AMI não pode ter
        esse risco). `.env`/`.env.example` ganharam `AMI_PORT`/`AMI_USER`/
        `AMI_SECRET` (gerado por `-GenKeys`); `sysapi/.env` ganhou
        `VOICE_AMI_*` (mesmo secret) e `VOICE_PJSIP_RAMAIS_PATH` (caminho
        local do `pjsip_ramais.conf` — decisão de rodar tudo na mesma máquina
        segue valendo, mesma lógica do resto da V1).
      - `VoiceExtensionsController::regeneraConfigRamais()` reescreve
        `pjsip_ramais.conf` com todos os ramais `status=A` (mesmo formato que
        `render-ramais.ps1` gerava à mão) e chama o AMI depois de CADA
        create/update/destroy. "Destroy" não é hard delete, é `status='I'`
        (mesmo padrão de `voice_agents`) — ramal desativado some do arquivo
        no próximo reload, mas a linha continua no banco.
      - Rotas em `/voice/extensions/{list,store,update,destroy}`, dentro do
        grupo já protegido por `voice.access`.
      **Testado de ponta a ponta via tinker** (sem precisar de token real,
      só `$request->setUserResolver()`): criei o ramal `1003` pelo
      controller → `pjsip_ramais.conf` ganhou o bloco → `pjsip show
      endpoints` no container mostrou `1003` carregado **ao vivo, sem
      restart** → desativei pelo controller → arquivo perdeu o bloco →
      endpoint sumiu do `pjsip show endpoints` de novo. AMI testada primeiro
      isolada (spike com socket cru em PHP) antes de escrever o service,
      mesmo padrão de "provar o risco antes" da URA/ramal.
      Achado técnico: a resposta do AMI pro `Action: Command` vem misturada
      com o evento assíncrono `FullyBooted` (que o Asterisk manda logo após
      todo login) — o log de auditoria às vezes captura só o `FullyBooted` e
      perde a saída do comando dentro da janela de timeout; aumentei de 3
      para 5s. Não afeta a função (o reload sempre aconteceu de verdade,
      confirmado via `pjsip show endpoints`), só a completude do log.
- [x] Endpoint de ramal padrão no cadastro de usuário:
      `VoiceExtensionsController::setDefaultExtension`
      (`/voice/extensions/set-default`) escreve `users.default_extension_id`.
      Ficou fora do `Login\UserController@add/update` (o CRUD geral de
      usuário, compartilhado por outros produtos do RAPIA, com branch por
      `PROJECT_ID`) de propósito — menor risco mexer só num controller do
      módulo de voz. Valida que o ramal pertence mesmo ao usuário antes de
      salvar (`voice_extensions.user_id === user_id`, já que um usuário pode
      ter mais de um ramal — mesa + softphone — e este campo escolhe qual é o
      principal). Testado via tinker: ramal de outro usuário rejeitado.
- [x] Presença: campo próprio `users.voice_status` (não reaproveita
      `chat_status` — ver comentário na migration), setado por
      `VoiceCallsController::presence` (`/voice/presence`), chamado
      automaticamente pelo front ao abrir o Painel 360 (ainda não plugado -
      isso é frontend) e pelo seletor `[● Disponível ▾]` pra alternar manual.
      `VoiceCallsController::assume` agora bloqueia com 403 se
      `voice_status !== 1`, testado via tinker (chamada de teste inexistente,
      só pra validar que o guard bloqueia **antes** de tocar no Redis/banco).

**Asterisk** ✅ concluído em 23/09/2026 (detalhes técnicos na seção 7, ao final do M2.5)
- [x] Prompt de áudio da URA — **placeholder** (TTS pt-BR do Windows/SAPI,
      convertido pra 8kHz/mono/16-bit via ffmpeg; locução profissional de
      verdade continua pendente, já era risco conhecido) — e dialplan novo em
      `extensions.conf`: `Background()`/`WaitExten()` captura o dígito, branch
      por opção (1=IA, 2=fila direta, timeout/inválido=fila padrão). Testado
      com ligações sintéticas: os 3 destinos batem no trunk/sala certos.
- [x] Contexto novo pra ramais (`[ramais]`) com os endpoints SIP — via
      template+reload (decisão acima), gerado por `render-ramais.ps1` a
      partir de `ramais/ramais.json`. `pjsip show endpoints` confirma os
      ramais de teste carregando sem erro.
- [x] Dialplan do ramal: ao discar um ramal, disca pro LiveKit num trunk
      catch-all (sem agente) — sala pessoal por chamada, não uma sala fixa
      por usuário (ver nota do `VoiceWebhookController` acima sobre como
      identificar o ramal-alvo). Testado com ligação sintética ramal→ramal.

**Frontend** ✅ concluído em 24/09/2026 (testado no navegador de verdade,
`npm run dev`, logado como SUPER)
- [x] Seletor `[● Disponível ▾]` no topo do Painel 360: **presença automática
      ao abrir** (chama `/voice/presence` com 1, sem modal) e volta a
      Indisponível ao sair da tela (`beforeDestroy`). Testado: abrir a tela
      marca Disponível; alternar no seletor grava `voice_status` no banco e
      mostra o aviso "Indisponível: você não recebe chamadas da fila". Fechar
      a aba não passa pelo `beforeDestroy` — o status fica até a próxima
      abertura (limitação conhecida).
- [x] `V_Softphone.vue` ganha o fluxo de "chamada interna recebida": nova prop
      `interna` ({room_name, from_extension}); toca (Web Audio 440+480 Hz
      gerado na hora, sem arquivo de áudio novo), mostra "Chamada interna do
      ramal X" com Atender/Recusar e **só conecta ao LiveKit depois do clique**
      (o fluxo "assumir da fila" continua conectando direto). Sem resposta em
      45s recusa sozinho. Backend novo: `VoiceCallsController::rejectInternal`
      (`/voice/internal/reject`, derruba a sala no LiveKit; só a atendente-alvo
      pode, conferido por um registro efêmero no Redis que o webhook grava ao
      tocar) e o evento `internal.ended` (emitido pelo webhook quando quem
      ligou desiste ou a sala termina — sem ele a barra ficaria tocando pra
      sempre). **Testado no navegador com ligação sintética ramal→ramal**:
      tocar (barra azul, evento chegou pelo WebSocket), **Recusar** (barra
      some, Asterisk fica com 0 canais), **Atender** (barra vira "Conectado",
      console confirma `connected to Livekit Server 1.13.7`; o automatizador
      não tem microfone, então usei um stream mudo no `getUserMedia` só nessa
      aba de teste), **Encerrar** (0 canais) e **quem ligou desiste** (barra
      some sozinha).
- [x] Campo **"Ramal padrão (Voz)"** no cadastro de usuário
      (`ModalUsuarios02.vue`, a tela `/usuarios-rapia` — não a `Usuarios.vue`):
      só aparece editando um usuário existente e para SUPER
      (`$store.state.user.super === 'S'`; `getSuperUser` do Menu é computed
      local, não getter do Vuex — errei isso na primeira versão e o teste no
      navegador pegou). Salva **na hora** pelo endpoint da Voz
      (`/voice/extensions/set-default`), não pelo `ADD_UP` genérico
      (`Login\UserController`, compartilhado com outros produtos). Lista só os
      ramais do usuário e vem pré-selecionado (`is_default` novo em
      `/voice/extensions/list`). Testado: selecionar `1002` → toast "Ramal
      padrão atualizado." + `users.default_extension_id=2` no banco; recarregar
      a página e reabrir → vem pré-selecionado.
- ⚠️ **Achado de ambiente (não é código)**: os eventos de voz (e os do chat)
  são `ShouldBroadcast` com `QUEUE_CONNECTION=redis`: vão pra fila e só depois
  pro **Pusher/Ably** (o projeto migrou em 01/12/2025 — `broadcasting.php`
  aponta pra `rest-pusher.ably.io`; o `laravel-websockets` self-hosted,
  porta 6002, está comentado e **não é necessário**; a instrução antiga em
  `sysapi/Anotações.txt` está desatualizada). Sem **`php artisan queue:work
  redis`** rodando, o evento fica parado na fila e **nenhuma tela em tempo
  real funciona** — tinha 18 eventos acumulados. Precisa estar no ar em
  qualquer demonstração; incluir no checklist de pré-apresentação (seção 10)
  e no `voip/iniciar.ps1`. (Correção: numa primeira versão desta nota eu
  também exigia `websockets:serve` e ligava isso ao erro antigo
  `Pusher::__construct()` no log — ambos errados/sem prova; esse erro de
  configuração continua sem explicação.)
  **Fragilidade encontrada no mesmo dia**: o `queue:work` **morreu sozinho**
  minutos depois. O log do projeto (`LOG_CHANNEL=stack`) inclui o
  `SlackWebhookHandler`, e um lapso de DNS (`Could not resolve host:
  hooks.slack.com`) fez o próprio envio do log lançar exceção e derrubar o
  worker (o `websockets:serve` continuou vivo). Sem worker, o tempo real para
  em silêncio. Mitigações a decidir: rodar o worker sob um supervisor que o
  reinicie (loop no `iniciar.ps1` no local; Supervisor/systemd na EC2) e/ou
  fazer o canal Slack não lançar exceção quando a rede falha.

**Riscos desta frente**
- **Maior risco, prototipar primeiro**: hoje a decisão "quem entra na sala"
  (IA ou ninguém) é um toggle **global** (`dispatch.py agente|teste`). Pra
  opção 2 da URA pular a IA por chamada, essa decisão precisa virar **por
  chamada**, resolvida pelo Asterisk antes de discar pro LiveKit — ainda não
  está claro qual mecanismo do LiveKit SIP (header custom? trunk/dispatch
  rule separado por branch?) permite isso. Validar com uma ligação de teste
  antes de construir o resto da fase, mesmo padrão usado pro Webpack 3 no M2.
- Realtime PJSIP (se for essa a escolha) muda a forma como o Asterisk lê
  configuração — precisa validar com uma ligação de teste real, não só de
  leitura no banco.
- Gravação da URA em português precisa soar profissional — usar locução
  gravada de verdade (ou TTS de alta qualidade), não voz robótica de exemplo.

- 🆕 **Achado de 24/09/2026 — URA fica MUDA em ligação real (ainda em
  aberto).** Os testes sintéticos da URA passavam, mas na primeira ligação
  real do celular a chamada atende e fica muda (só o chiado de ruído de
  conforto da operadora), e o dígito não chega. Investigação com 10 ligações
  reais, `tcpdump` dentro do container e `pktmon` na placa de rede do Windows:
  - **Regra sem exceção**: quando quem atende o provedor é a **ponte do
    `Dial()` com o LiveKit** (entrada direto pra IA), o áudio funciona nos
    dois sentidos; quando é o **próprio Asterisk** (`Answer`/`Background`/
    `Playback`), o relay de mídia do provedor (`52.67.163.135`) **não envia
    nenhum pacote**, nem depois de uma ponte posterior (teste em fases: tom →
    fala → ponte com a IA, tudo mudo).
  - **Descartado, um a um**: arquivo de áudio (o Asterisk lê idêntico ao
    original), codec (PCMA nos dois casos), `strictrtp`, firewall do Windows,
    atraso/`180 Ringing` antes do atendimento, canal Local entre o provedor e
    a URA, e `Remote-Party-ID` (saiu idêntico ao da ligação que funciona). A
    sinalização SIP ficou **byte a byte igual** entre a ligação que falha e a
    que funciona, exceto o texto do `Remote-Party-ID`.
  - **Única anomalia de rede que sobrou**: o Docker Desktop no Windows troca a
    porta de origem de tudo que sai (SDP anuncia `20024`, o pacote sai por
    `61845`) e mascara a origem de tudo que entra (`172.30.0.1`). O relay do
    provedor responde na porta trocada quando funciona. O "host networking" do
    Docker Desktop foi testado e **não resolve** (continua trocando a porta, e
    a origem de quem entra vira `127.0.0.1`, pior para segurança) — revertido.
  - **O SIP trunk por IP** (alternativa ao registro com login/senha) **não
    foi retentado**: com o Docker Desktop, o provedor chegaria ao Asterisk
    como `172.30.0.1`, sem como identificá-lo por IP sem abrir brecha.
  - **Estado atual (pausa segura)**: chave `URA_ATIVA` no `.env` de
    `voip/livekit-local` (padrão `0` = entrada direto pra IA, o caminho que
    funciona). Todo o código da URA (dialplan com `CURL()` e fallback,
    `VoiceUraRuntimeController`, cadastro de troncos/opções) continua pronto;
    reativar é `URA_ATIVA=1` + `render-config.ps1` + `dialplan reload`.
  - **Chamado com o provedor (sobreip)** — levar os Call-IDs: sem áudio
    `021CC4BA0C8140000006EBF6@TB008235_VOIP0.TB008235` (24/09/2026 01:34:09
    UTC); com áudio, mesma sinalização,
    `021CC4BB508140000006EC1C@TB008235_VOIP0.TB008235` (01:39:35 UTC). Pergunta:
    por que o relay `52.67.163.135` recebeu nosso RTP e não enviou nenhum na
    primeira.
  - Achado de segurança à parte: a porta SIP pública recebe, a cada ~50s,
    `INVITE`s da internet tentando ligar para números internacionais de
    tarifa premium (`+44 20 3996 9300` e variações). Todos rejeitados com
    `401` (nenhum endpoint aceita). Restringir a origem da porta 5060 no
    roteador aos IPs do provedor quando possível.
- ✅ **RESOLVIDO em 25/09/2026 — a causa era o Docker Desktop.** Com a stack
  inteira numa EC2 de homologação (`network_mode: host`, seção 7.3), 3 ligações
  reais pela URA tiveram áudio do provedor **já durante o menu**, quando só o
  Asterisk atende (655, 923 e 579 pacotes RTP de `52.67.163.135` antes do
  dígito; no Windows eram 0) e o DTMF chegou (1, 2, 2). Opção 1 -> IA
  (chamada 41, 8 falas transcritas); opção 2 -> fila (chamadas 42 e 43, 1
  `voice_queue_entries` cada; o usuário assumiu uma no Painel 360). **O chamado
  com o provedor não é mais necessário.** A URA fica **ativa** na homologação
  (`URA_ATIVA=1`, decisão do usuário). Ajustes feitos no mesmo dia:
  - **Espera de 4 s depois do dígito**: medida no tcpdump (DTMF 17:13:03,8 ->
    consulta 17:13:07). O padrão do DID `_[0-9+].` no `[from-provedor]` também
    casava "1" + mais dígitos, e o Asterisk esperava o `TIMEOUT(digit)`. O menu
    foi para o contexto próprio `[ura-menu]` (só extensões de 1 dígito). Nos
    dois templates (`livekit-ec2` e `livekit-local`). Depois do dígito sobram
    ~0,3–1 s da consulta pelo ngrok + ~1,3 s até o LiveKit SIP atender (espera
    o worker, que está no PC); em produção isso cai.
  - **Áudio da URA refeito com a voz Leda do Gemini Live** (o SAPI soava
    travado): `voice-agent/scripts/gerar_audio_ura.py` (reaproveita o
    `gerar_amostras_voz.py`; passa-baixa + reamostragem soxr para 8 kHz). Texto
    com as opções atuais: "Olá! Você ligou para a Clínica Coopab. Para falar
    com a nossa assistente virtual, digite 1. Para falar com um atendente,
    digite 2. Ou, se preferir, aguarde na linha que você será atendido."
    Original SAPI guardado em `voip/backup-env-pre-ec2/`.
  - **Voz Leda no agente**: `voice_agents.voice` do agente 1 `Kore -> Leda` (a
    versão publicada não tem `settings`, então vale o campo do agente) e
    `GEMINI_VOICE=Leda` no `voice-agent/.env` (fallback). Ao publicar versão
    nova no Estúdio, escolher Leda (a versão tem prioridade).
  - **Idioma fixo pt-BR**: numa ligação real a 1ª resposta do paciente virou
    "¿Qué?" e a IA repetiu a saudação. O `agent.py` não passava `language` ao
    `RealtimeModel`; agora passa `runtime.language` (`voice_agents.language`) ou
    `GEMINI_LANGUAGE` (padrão `pt-BR`). Prova: `playground_smoke.py` 8/8 (o
    script também deixou de fixar `localhost:7880` e lê o `.env` do worker).
    **Não verificado**: nova ligação real depois da correção.
  - **Filtro de números permitidos** (sysapi `5291d6d`): antes de atender, o
    `[from-provedor]` consulta `GET /voice/ura/caller-allowed?from=` (texto
    `allow`/`deny`, mesmo `x-api-key` da URA). Parâmetros VOICE
    `VOICE_FILTRO_ENTRADA` (S/N, começa `S`) e `VOICE_NUMEROS_PERMITIDOS`
    (lista por vírgula, compara os 11 últimos dígitos; começa com
    `84988345243`), em Parâmetros do Sistema (`/sys-parametros`). **Qualquer
    resposta que não seja `allow` recusa, inclusive API fora do ar** (decisão do
    usuário). Provado: controller (6 formatos), endpoint pelo ngrok (allow,
    deny, 401 sem token), chamada sintética sem caller ID e API inalcançável
    simulada -> recusada; ligações reais do usuário incluindo/removendo o
    número na lista. Recusa inicialmente com `Hangup(21)` (403): o provedor
    **reenviava o INVITE** (4 vezes em ~17 s) e o chamador ficava mudo até ele
    desistir; trocado para `Hangup(17)` (486 Busy Here, resposta final, sinal
    de ocupado). **Não verificado ainda**: ligação real recusada depois da troca.
- ~~Teste diagnóstico só do Asterisk na EC2 (`voip/teste-ec2/`)~~ — dispensado:
  a stack completa subiu na EC2 de homologação (seção 7.3). Texto original:
- [x] **(dispensado)** teste
      diagnóstico do Asterisk na EC2 de produção (AWS sa-east-1). Pacote
      pronto e validado (dialplan e pjsip carregados num Asterisk descartável)
      em `voip/teste-ec2/` — roteiro completo no `README.md` de lá. Só o
      Asterisk, em `network_mode: host` (rede Linux real, sem tradução de
      porta), atendendo sozinho: toca a URA, lê um dígito e faz eco. Pré-requisitos: autorização para rodar em produção; Security
      Group liberando UDP 5060 e 20000-20099 **só para `52.67.163.135/32`**
      (nunca `0.0.0.0/0`); **parar o Asterisk local** durante o teste (a conta
      aceita um registro por vez). Leitura do resultado: se ouvir a URA/eco e
      chegar RTP do provedor → a causa é o NAT do Docker Desktop, e a decisão
      passa a ser mover o Asterisk (ou a stack) para a nuvem, redesenhando a
      ligação com o LiveKit SIP, a consulta via `CURL()` e o reload via AMI,
      que hoje apontam para o Laravel local; se ficar mudo igual → o problema
      é do provedor e o chamado vira prioridade.

- **Pronto quando:** o prospect liga, ouve a URA, digita 1, a IA atende
  (fluxo de hoje); digita 2, cai direto numa fila humana sem passar pela IA;
  não digita nada, cai na fila padrão do tronco depois do timeout; e um
  colaborador liga pro ramal de outro e o Painel 360 dele toca a ligação.
  **Status (24/09/2026)**: o critério da URA fica **bloqueado** pelo achado
  acima até o teste da EC2 / resposta do provedor; os demais critérios
  (ramal tocando no Painel 360, presença) seguem no frontend.
  **Status (25/09/2026)**: critério da URA **atendido na EC2 de homologação**
  (opções 1 e 2 em ligação real). Falta provar o timeout (não digitar nada ->
  fila padrão) em ligação real e o ramal pela EC2 (pendência na seção 7.3).

### M3 — Estúdio do Agente (6–9 dias) ✅ concluído em 25/09/2026
- [x] Editor de blocos, versões, catálogo de ferramentas, teste de ferramenta
- [x] Aba de visualização do fluxo (Drawflow, somente leitura)
- [x] Playground por navegador
- **Pronto quando:** dá para mudar o prompt, publicar e ouvir a diferença na ligação seguinte. **Atendido pelo Playground**
  (publicar, "Ouvir a publicada", a IA muda o que diz). Em ligação real por telefone a garantia é só a do código (o worker lê o
  runtime no início de cada ligação); o teste com ligação real depende da EC2 (pendente).

**Prova de risco do Playground (iniciada em 24/09/2026)** — antes de qualquer UI,
provar a cadeia: criar sala → despachar o agente com a versão rascunho → worker
carrega o rascunho → áudio nos dois sentidos → transcrição/eventos chegam ao RAPIA.
- [x] **P1. Runtime aceita rascunho**: `GET /voice/agents/{id}/runtime?version=draft`
      (ou `?version={id}`) devolve a versão pedida, sem cache; sem `version` continua
      devolvendo a publicada (cache de 45s). Resposta ganhou `version_status`.
      Testado por `curl` com rascunho de teste (versão 2, frase-marca "abacaxi"):
      publicada não contém a marca, rascunho contém; `version=nada` → 422;
      `version=999` → 404; sem token → 401.
- [x] **P2. Sala `pg-{tenant}_{userId}_{rand}` + token com despacho do agente**:
      `POST /voice/playground/session` (grupo `voice.access`, só SUPER; body
      `agent_id`, `version` = `draft` (padrão) | `published` | id). Resolve a versão
      para um id concreto, gera a sala e o token (10 min) com
      `roomConfig.agents[{agentName, metadata:{agent_id, version_id, playground:true,
      max_seconds:300, user_id}}]`. Devolve `token, ws_url, room, identity,
      max_seconds, agent, version`. Novo `config('voice.agent_name')`
      (`VOICE_AGENT_NAME`, padrão `rapia-voice`). Provado: cliente entrou na sala com
      o token e o participante `agent-…` (kind AGENT) apareceu com os metadados
      certos, **sem** dispatch rule e sem worker extra; sala `pg-` não criou
      `voice_calls` nem `voice_call_events` (webhook a ignora) e fechou sozinha
      20s depois de vazia. Erros: versão inexistente/agente inexistente → 404,
      `version` inválida → 422.
- [x] **P3. Worker lê os metadados do despacho e carrega a versão pedida**
      (`voice-agent/agent.py`): `agent_id_do_job` virou `parametros_do_job`
      (`agent_id`, `version_id`, `playground`, `max_seconds`); `busca_runtime`
      passa `?version={id}` quando há `version_id`; no Playground, um cronômetro
      chama `ctx.shutdown()` ao fim de `max_seconds`. Ligação real não traz esses
      campos e segue igual (versão publicada, sem limite). Provado com 3 salas no
      worker reiniciado (log em `voice-agent/agent.log`): **A)** sessão do
      Playground → "versão=2 (draft) | PLAYGROUND" e a IA abriu a fala com
      "Abacaxi" (a marca do rascunho); **B)** despacho só com `agent_id` → "versão=1
      (published)" e sem a marca; **C)** `max_seconds=20` → log "limite de 20s
      atingido" e o agente saiu da sala 21,1s depois de entrar.
- [x] **P4. Destino de transcrição/eventos das salas `pg-` + tools em sandbox**
      (sysapi): novo `App\Services\Voice\PlaygroundBuffer` (lista Redis
      `voice:pg:{sala}:events`, TTL 1h, máx. 500 eventos, `id` sequencial por sala;
      cada evento também sai por `VoiceCallUpdated` com `op = playground.event`).
      `VoiceWorkerController::transcript/event` e
      `VoiceWorkerToolController::run` desviam salas `pg-` para ele — ligação real
      segue o caminho antigo (inclusive o 404 para sala desconhecida). Tools em
      sandbox (`runPlayground`): validam e respondem como as reais (a validação de
      CPF foi extraída para `avaliaTriagem`, compartilhada), mas não criam contato,
      não entram na fila humana, não disparam evento do Painel 360; o buffer marca
      `tool_result.simulated = true` (o modelo **não** recebe essa marca). Leitura:
      `POST /voice/playground/events {room, after_id}` (SUPER e só o dono da sala;
      outro usuário/sala real → 404) → `{events, last_id}`.
      Provado: (1) 3 rotas do worker com sala `pg-` fictícia — 11 eventos gravados
      (transcrições, tool_called/tool_result com CPF inválido e válido,
      transferência, tool desconhecida → 404, evento genérico); contagem de
      `contacts/voice_calls/voice_call_events/voice_transcripts/voice_queue_entries`
      idêntica antes e depois; sem token → 401; (2) regressão do caminho real
      (`registrar_triagem` válido e `cpf_invalido`) em transação revertida; (3) ao
      vivo com o worker real: a fala da IA ("Olá, abacaxi! …") chegou ao buffer e
      o worker não logou mais o 404. Fila: 0 pendentes e 0 `failed_jobs`.
- [x] **P5. Cliente headless `voice-agent/scripts/playground_smoke.py`** — faz o
      papel do navegador: abre a sessão, entra na sala `pg-`, **fala** com o
      agente (TTS local, voz "Microsoft Maria Desktop", pt-BR, 16 kHz) e confere
      elo a elo (PASS/FAIL, exit code 0/1): sessão, agente presente, áudio
      agente→cliente (grava o WAV em `%TEMP%\playground_smoke\` e mede energia),
      áudio cliente→agente (a fala volta como transcrição `patient` no RAPIA),
      transcrição `ai`, marca do rascunho (`--marker/--expect-marker`), tools
      (modo `full`), ausência de `voice_calls`, e sala fechando sozinha. Sem
      `--user-token` roda em modo local (tinker em processo, usuário 9); com
      `--user-token`/`RAPIA_USER_TOKEN` usa os endpoints HTTP reais. Se o agente
      não entra, imprime as linhas do log do LiveKit sobre o despacho.
      **Resultados (24/09/2026)**: `--mode full` → 12/12 (o Gemini entendeu nome,
      CPF de 11 dígitos e data ditos por TTS; `registrar_triagem` chegou com
      `{nome: "Maria da Silva Souza", cpf: "52998224725", data_nascimento:
      "01/02/1990"}`, resultado `simulated`, e depois `transferir_para_atendente`;
      63,6s de fala ativa do agente, 7 falas `ai` e 6 `patient` no RAPIA);
      `--version published --expect-marker no` → 9/9 (publicada sem "abacaxi",
      rascunho com); `--mode quick --runs 5` → 45/45 (agente entra em 0,8s);
      execução após ~7 min ocioso → 9/9. Latências típicas: 1º áudio do agente
      ~2,5s, saudação publicada no RAPIA em 12–17s.

**Construção do Estúdio (após a prova de risco, aprovada em 24/09/2026)** — ordem: backend → worker (se preciso) → frontend, um ponto por vez:
- [x] **E1. API de versões** (sysapi, `VoiceStudioController`, rotas `POST /voice/studio/*`, só SUPER):
      `options` (modelos, vozes, idiomas, variáveis, limites), `agents/list`,
      `agents/detail`, `versions/list`, `versions/detail`, `draft/save` (cria o
      rascunho clonando a publicada + tools; edita blocos/settings/nota; `expected_updated_at`
      → 409 em conflito), `draft/discard`, `versions/restore` (copia uma versão para o
      rascunho — "reverter" nunca publica sozinho), `publish` (arquiva a atual, publica o
      rascunho, espelha as settings nos campos do agente, `Cache::forget` do runtime),
      `versions/compare` (diff por linha dos blocos, settings e tools). Migration
      `2026_09_24_100000_alter_voice_agent_versions_studio` (`number`, `blocks`, `settings`,
      `notes`, `published_by`, status `archived`; rodada só em `ipsys-rapia`, com
      `migrate --path`, porque o `migrate:all` percorre também `ipsys-02`/`ipsys`).
      Novo `VoicePromptBlocks` (blocos ⇄ prompt compilado, variáveis, validação, diff).
      Runtime passou a usar as settings da versão (fallback: campos do agente).
      Provado num agente de teste (apagado; agente 1 intocado): 37 verificações — v1 antiga
      quebrada em 6 blocos e `compila(blocos) == prompt original`, rascunho, validações
      (422), conflito (409), comparação, runtime rascunho × publicada, **publicar reflete
      na hora** (cache invalidado), publicar igual → 422, restaurar v1 e republicar.
- [x] **E2. Catálogo de tools (liga/desliga por versão) + "Testar ferramenta"** (sysapi + worker):
      `POST /voice/studio/tools/{list,toggle,save,add-internal,delete,test}` (só SUPER; toda
      alteração vai para o RASCUNHO, criado da publicada se não existir).
      - **Catálogo**: `VoiceToolCatalog::internas()` lista só as tools que existem de verdade
        (`registrar_triagem`, `transferir_para_atendente`); uma removida pode voltar por
        `add-internal`. Tool interna: só a descrição é editável.
      - **Tool HTTP** (`kind=http`, coluna nova `http_config`): método, URL, headers (com
        `secret`), query, corpo (valor `{{param}}` exato mantém o tipo), timeout 1–10s,
        `response_map` (só esses campos vão ao modelo), modo no Playground (`live`/`simulate`,
        padrão GET=live, demais=simulate) e resposta de exemplo. Nome único por versão.
        **Segredos** criptografados (`enc:`), nunca saem do servidor (a API devolve
        `has_value:true`; salvar com valor em branco mantém o segredo); o runtime **não**
        entrega URL/credenciais ao worker.
      - **Executor** (`VoiceToolExecutor`): valida argumentos contra o schema (aceita "123"
        para inteiro e "true" para booleano, porque o modelo às vezes manda texto), monta a
        requisição, **anti-SSRF** (metadata `169.254.x.x` sempre bloqueado; `block_private_hosts`
        e `allowed_hosts` em `config/voice.php`; redirects desligados), resposta lida até 64 KB,
        erros viram resultado amigável ao modelo (`http_404`, `indisponivel` + orientação).
      - **Testar ferramenta** (`tools/test`): aceita a tool salva ou a definição ainda não salva
        do formulário; devolve `request` (segredo mascarado), `response`, `duration_ms` e
        `result_for_model`. Tool HTTP que não é GET só roda de verdade com `confirm_live:true`
        (senão 422 `requires_confirmation`); `mode:"simulate"` usa a resposta de exemplo.
      - **Worker → RAPIA**: `agent.py` passou a enviar `version_id` em cada tool; o
        `VoiceWorkerToolController` executa tools HTTP (chamada real grava
        `tool_called`/`tool_result` com `duration_ms`/`http_status`; Playground grava também
        `request`/`response` no buffer, com `simulated`).
      - **ERP Demo** (`VoiceDemoErpController`, `GET /voice/demo-erp/patients|appointments`,
        `POST /voice/demo-erp/callbacks`, chave própria `x-demo-key` = `config('voice.demo_erp_key')`,
        5 pacientes fictícios com CPF válido, agenda relativa a hoje, nada é gravado).
      Provado: 56 verificações num agente de teste (E1 segue 37/37) e **ponta a ponta com o
      modelo de verdade** (`playground_smoke.py --mode erp`): o cliente diz o CPF, o Gemini
      chama `buscar_paciente`, o RAPIA faz o GET real no ERP Demo (200, segredo mascarado), o
      modelo recebe só `{nome, plano}` e a IA **fala** "Olá, Maria da Silva Souza. Seu plano é o
      Coopab Essencial." — 12/12. Regressão do worker novo: `--mode full` no agente real, 12/12.
- [x] **E3. Frontend do Estúdio** (`sysweb`, `pages/rapia/voz/EstudioAgente.vue` + `components/componentes/rapia/voz/V_Estudio*.vue`
      + `functions/rapia/voz/estudio.js`; nenhuma mudança no backend). Feito em 24/09/2026, testado no Chrome (login do usuário SUPER):
      - **E3.1 Esqueleto**: seletor de agente, badges "Publicada vN / Rascunho (vN)", abas Editor · Ferramentas · Versões,
        estados de carregamento/erro com "Tentar novamente".
      - **E3.2 Editor de blocos**: blocos reordenáveis (↑↓), título editável, contadores por bloco e do prompt total
        (limites de `options.limits`), chips de variáveis que inserem no cursor, aviso de variável desconhecida por bloco,
        adicionar/remover, `identidade` fixo no topo, prévia do prompt resolvido, "Salvar rascunho", "Desfazer alterações",
        indicador "Alterações não salvas", 422 por bloco/global e 409 com "Recarregar rascunho".
      - **E3.3 Configurações da sessão**: modelo, voz (sem pré-escuta), idioma, temperatura, tempo máx., instrução da saudação
        e nota da versão, salvos junto do rascunho (só os campos alterados são enviados).
      - **E3.4 Versões**: publicar (modal com nota + resumo das mudanças + bloqueio se o rascunho é igual à publicada ou se o
        editor tem alterações não salvas), descartar, histórico, comparar (2 versões marcadas ou rascunho × publicada; diff por
        bloco, configurações e ferramentas), restaurar versão arquivada no rascunho (com aviso de que substitui o atual).
      - **E3.5 Ferramentas**: lista com liga/desliga, adicionar interna do catálogo, remover, editar descrição da interna,
        formulário completo da tool HTTP (parâmetros, método/URL, headers com "secreto", query, corpo, timeout, mapeamento da
        resposta, modo no Playground, resposta de exemplo), renomear, painel "Testar ferramenta" (campos gerados do schema,
        requisição/resposta/`result_for_model`/duração, confirmação para não-GET em modo real, testa definição ainda não salva).
      - **E3.6 Acabamento**: proteção contra perda de alterações (troca de agente, saída de rota e `beforeunload`), datas
        `dd/mm/aaaa hh:mm`, erro de rede com nova tentativa.
      Provado no navegador (agente de teste, já apagado; agente 1 intocado e sem rascunho): edição → salvar → 422/409 → comparar →
      publicar → restaurar → descartar; tool HTTP GET (`buscar_paciente`) e POST (`registrar_retorno`) ponta a ponta no ERP Demo,
      segredo mascarado e mantido ao editar/renomear; interna testada em sandbox. Console do Chrome sem erros.
      **Não verificado**: layout em largura de celular (o Chrome automatizado não redimensiona o viewport; o layout usa a grade do
      Bootstrap e deve empilhar) e a proteção `beforeunload` só foi vista pelo bloqueio da navegação, não por clique do usuário.
- [x] **E4. Playground na UI** (`sysweb`, aba "Playground" do Estúdio: `V_EstudioPlayground.vue` + `estudio.js` + ajuste em `livekit.js`;
      nenhuma mudança no backend nem no worker). Feito em 24/09/2026:
      - Escolha da versão (Rascunho vN / Publicada vN; o rascunho é o padrão quando existe) e "Falar com o agente": abre
        `POST /voice/playground/session`, entra na sala pelo LiveKit (`livekit.js`, microfone + alto-falante do navegador) e espera o
        agente (15 s; senão "Tentar de novo").
      - Estados na tela: conectando · aguardando o agente · conversando · encerrada · falhou; mudo, medidores de nível (você/agente),
        contagem regressiva do limite de 5 min, "Encerrar", "Nova conversa", "Trocar versão".
      - **Transcrição** e **Ferramentas chamadas** lado a lado: eventos do buffer por **polling** (`/playground/events`, 1,5 s, com
        `after_id` só avançando pelo polling) mais o **push** do Echo (`playground.event`, filtrado por `data.room`), deduplicados por id.
        Ferramentas: chamada + resultado pareados, selo real × simulado, duração, argumentos, resultado para a IA e
        "ver requisição e resposta"; eventos desconhecidos (ex.: `call.transferred`) aparecem como evento genérico.
      - Avisos: editor com alterações não salvas (o Playground usa o rascunho salvo) e rascunho alterado depois que a conversa começou.
      - Limpeza: sair da tela, trocar de agente ou "Encerrar" desconectam da sala (`beforeDestroy`); microfone negado/inexistente
        mostra mensagem clara **e não deixa a sala aberta** (correção em `livekit.js`, que também vale para o Painel 360).
      Provado no Chrome (login do usuário; microfone simulado, veja abaixo): sessão com publicada e com rascunho (id da versão certo),
      agente entra, saudação chega à transcrição, fala do "usuário" volta transcrita, nome/CPF/data reconhecidos pelo Gemini, mudo,
      limite de 5 min encerra a tela com a mensagem certa, saída da rota envia `leave` ao LiveKit, microfone negado → mensagem +
      sala fechada em <1 s, pareamento/renderização de tools com eventos sintéticos gravados no `PlaygroundBuffer` da sala ativa,
      console sem erros, agente 1 sem rascunho no fim e sem processos `agent.py` órfãos.
      **Não verificado**: microfone e alto-falante reais (o Chrome automatizado não tem; usei `getUserMedia` substituto com fala
      sintetizada em pt-BR + ruído de fundo), o fluxo completo `registrar_triagem` pela UI (o STT perdeu os 3 primeiros dígitos do CPF
      sintetizado; o worker/tool já estava provado em `playground_smoke.py`) e o layout em tela de celular.
- [x] **E5. Aba "Visão do fluxo"** (`sysweb`, somente leitura: `V_EstudioFluxo.vue` + `functions/rapia/voz/estudioFluxo.js` + a aba em
      `EstudioAgente.vue`; nenhuma mudança no backend). Feito em 24/09/2026. É uma visão **explicativa** gerada da configuração da
      versão (blocos + ferramentas habilitadas), não a lógica que o modelo executa nem um editor:
      - **E5.1 Gerador puro** (`gerarFluxo(versao)` -> nós, conexões, ferramentas desligadas): Ligação entra -> Saudação -> Identidade
        -> hub "Ferramentas" -> "Encaminha para atendente humano" (só se `transferir_para_atendente` estiver ligada) na linha y=0;
        "Limites da sessão" sob a entrada, demais blocos sob a Identidade, ferramentas sob o hub (até 8 por coluna); mais de 8
        blocos viram 6 + "+N blocos". Ferramentas desligadas ficam fora do desenho (selo do hub e legenda). Todo texto é escapado.
      - **E5.2 Canvas** (Drawflow em modo fixed, sem arrastar nós/criar ligações), seletor Rascunho (vN) / Publicada (vN) com o
        rascunho como padrão, zoom −/+ e Ctrl+roda, arraste do fundo.
      - **E5.3 Ferramentas clicáveis**: modal com para que serve, parâmetros, método e endereço (sem query/credenciais), origem de
        cada campo enviado (nunca o valor), mapeamento da resposta, modo no Playground, timeout e só a **contagem** de cabeçalhos.
      - **E5.4 Acabamento**: (a) todos os nós clicáveis com o mesmo modal (texto completo do bloco com quebras de linha, "+N
        blocos" com o texto de cada um, saudação, modelo/voz/idioma/temperatura, limites com a ressalva de que é só a configuração
        da versão, hub com habilitadas x desligadas, humano); (b) legenda de cores completa, gerada das mesmas variáveis CSS dos nós;
        (c) legibilidade: "Ajustar" agora ajusta à **largura** (zoom entre 0,6 e 1, ~0,82 no agente de teste, antes ~0,44), o canvas
        cresce até caber o diagrama e é a **página** que rola (roda comum), e o botão "Ver tudo" enquadra o diagrama inteiro na
        altura da tela (~0,5); (d) estados: sem versão, sem ferramentas (hub "Nenhuma habilitada: o agente só conversa"), só
        publicada (um botão só) e com rascunho; trocar de versão ou de agente fecha o modal; o botão ativo passou a seguir a
        versão realmente desenhada.
      Provado: 31 verificações em Node no gerador (agente 1 real + agente sintético grande: colapso de blocos, ferramentas em
      colunas, sem sobreposição, sem vazamento de segredos, casos limite). No Chrome (login do usuário) nos 4 cenários: agente de
      teste com rascunho v2 (12 blocos, 4 ferramentas ligadas + 1 desligada), o mesmo **sem nenhuma ferramenta ligada**, o mesmo com a
      versão publicada, e o agente 1 (só publicada, sem botão de rascunho). Cliquei os 16 nós do agente de teste (todos abrem o
      modal com o conteúdo certo); varredura do HTML do diagrama e dos 16 modais sem `rapia-demo`, `x-demo-key`, `cpf=`, `token=` nem
      `Bearer`; a roda comum rola a página inteira (topo e fim alcançáveis); console sem erros após recarregar. Um `AxiosError`
      apareceu uma vez no console durante os testes e não voltou em três recargas nem em nenhuma requisição do Estúdio (todas 200).
      **Não verificado**: layout em largura de celular (o Chrome automatizado não redimensiona o viewport, `resize_window` não
      mudou `innerWidth`; só simulei um contêiner estreito de 560 e 900 px, que confirma o reenquadramento e o piso de 0,6, mas
      corta a coluna da direita e exige arrastar o fundo); versão sem nenhum bloco só foi coberta pelo teste em Node, não na tela;
      as cores do hub (laranja) e da ferramenta HTTP (laranja escuro) são próximas, como pedido, e não foram validadas para daltonismo.
- [x] **E6. Ajustes finais** (`sysweb` + `sysapi` + script no worker). Feito em 24–25/09/2026:
      - **E6.1 "Publicar e ouvir a diferença"** (só sysweb: `EstudioAgente.vue`, `V_EstudioVersoes.vue`, `V_EstudioPlayground.vue`):
        depois de publicar aparece, em todas as abas, o aviso "Versão vN publicada às HH:MM. As próximas ligações já usam esta
        versão; as ligações em andamento seguem com a anterior" (mais a ressalva de até 1 min com várias instâncias da API) e o botão
        "Ouvir a publicada no Playground": abre a aba, seleciona a Publicada (vN, com selo "nova") e explica que falta clicar em
        "Falar com o agente" (o microfone exige gesto do usuário; não inicia sozinho). Com conversa em andamento o botão não a
        interrompe e avisa. O aviso é por agente e some ao trocar de agente.
      - **E6.2 Seletor de voz com pré-escuta** (`V_EstudioEditor.vue`): botão "Ouvir/Parar" ao lado do seletor; toca a amostra fixa em
        pt-BR da voz escolhida (`static/assets/audio/voz/{Voz}.mp3`, 8 arquivos de 56–66 KB, 9–11 s); trocar de voz ou sair da tela
        para o áudio; arquivo ausente mostra "Não há amostra de áudio para a voz X". As amostras foram geradas **uma vez** por
        `voip/voice-agent/scripts/gerar_amostras_voz.py` (modelo `gemini-3.8-live`, mesma chave do worker, frase fixa de clínica;
        conferência pela transcrição da própria saída; mp3 mono 48 kbps via ffmpeg). Custo: 5.128 tokens de entrada e 2.063 de
        saída no total, 8 chamadas, sem falhas. Para adicionar uma voz nova: incluir em `config('voice.studio.voices')` e rodar o
        script com `--voz Nome`.
      - **E6.3 Vozes recomendadas**: o responsável ouviu as 8 amostras em 25/09/2026 e indicou, da melhor para a pior, **Leda, Kore,
        Aoede, Zephyr**. Ficam em `config('voice.studio.recommended_voices')`, saem em `options.recommended_voices` (só as que existem
        em `voices`) e o seletor mostra o grupo "Recomendadas em pt-BR" (nessa ordem) e depois "Outras". A lista é decisão dele, não uma
        validação automática. Não mudei a voz de nenhum agente existente (o agente 1 segue em Kore).
      Provado: (B) num agente de teste (apagado; agente 1 intocado e sem rascunho): publicar o rascunho v2 mostra o aviso; `runtime`
      sem `version` devolve na hora a versão nova (id 55, com a marca); o botão leva ao Playground com a Publicada selecionada; a sessão
      abre na **versão id 55** e a IA diz "Olá, abacaxi!" (marca só da v2); com conversa ativa o botão avisa e não derruba. (A) por
      rede: 8/8 GET 200, `audio/mpeg`, tamanho exato; decodificam no navegador com as durações certas e volume não nulo; clique real
      cria o `Audio`, chama `play()`, mostra "Parar" e volta a "Ouvir" ao parar. O responsável ouviu as 8 vozes no próprio navegador.
      Console sem erros. Sem processos `agent.py` órfãos (uma árvore só, a do PID de `.agente.pid`).
      **Não verificado**: no Chrome automatizado o elemento `<audio>` não passou de "carregando" porque a aba fica em segundo plano
      (`visibilityState=hidden`) e o Chrome não carrega mídia assim; por isso `canplay`/`playing`/fim da amostra e a mensagem de arquivo
      ausente não foram vistos por mim (a reprodução foi confirmada pelo responsável ouvindo); "ligação real por SIP pegando a versão
      nova" (o teste da EC2 segue pendente: só vale o que o código garante, o worker lê o runtime no início de cada ligação e a
      publicação invalida o cache); o atraso de até 1 min com várias instâncias da API (`CACHE_DRIVER=file` é local a cada instância;
      o TTL do cache é 45 s) vem da leitura do código, não de teste com réplicas; o layout em celular; a transcrição da Zephyr saiu
      com "vocêHoje" (provável falha da transcrição, não conferida).

**Detalhes técnicos que só apareceram na implementação (Estúdio)**
- **Ajuste ao plano**: as configurações da sessão (modelo, voz, temperatura, idioma,
  saudação, tempo máximo) **passaram a ser versionadas** (`voice_agent_versions.settings`),
  em vez de ficarem só em `voice_agents`. Sem isso, trocar a voz num rascunho mudaria as
  ligações reais na hora. Versões antigas (settings nulo) usam os campos do agente.
- **Bug pego pelo teste**: uma versão anterior ao Estúdio dependia dos campos do agente,
  que a publicação seguinte espelha; se não fossem congelados ao arquivar, "reverter"
  traria a voz/temperatura da versão nova. Ao arquivar, a publicação agora grava
  `blocks` e `settings` da versão que sai.
- O `id` das tools não entra na assinatura "rascunho == publicada" (muda a cada clone);
  sem isso "publicar sem mudanças" não era bloqueado.
- Número da versão: descartar/substituir um rascunho **reaproveita** o número dele
  (`max(number)+1`); números só são "definitivos" depois de publicados.
- Um agente tem no máximo 1 rascunho (garantido em código, como já era a publicada).
- Variáveis desconhecidas no prompt (`{{Nome}}`, maiúsculas, espaços nas chaves) não
  bloqueiam o salvamento: voltam em `warnings` (a IA falaria o texto literal).
- **Ajuste ao plano (E2)**: as tools HTTP **não** reaproveitam `cad_integracoes`/`params`/
  `headers` (o TODO 5.2 sugeria): aquela tabela é das campanhas (`camp_system_id`), sem URL
  nem autenticação e não versionável junto com o agente. Ficam em `voice_agent_tools`
  (`kind=http` + `http_config`). O **ERP Demo** (previsto no TODO 5.2, ainda inexistente) foi
  criado agora porque a tool HTTP e o "Testar ferramenta" precisam de um alvo.
- **Bug pego no E2 (vinha do E1)**: o clone de tools decodificava/recodificava o
  `parameters_schema` como array PHP, o que troca `"properties": {}` por `[]` (schema
  inválido para o function-calling do Gemini). O clone agora copia o JSON **cru**, e
  `VoiceToolCatalog::schemaJson` sempre grava `properties` como objeto.
- O worker (`agent.py`) foi reiniciado de novo em 24/09 (mesma janela com `Tee-Object`,
  PID em `.agente.pid`) para carregar o envio de `version_id`.
- Tools HTTP guardam a URL também em `voice_agent_tools.endpoint` (só para exibição);
  a fonte é `http_config.url`. Se a URL tiver query própria, ela é mesclada com os itens
  de `query` (o Guzzle, sozinho, descartaria uma das duas).
- Em produção ligar `VOICE_TOOLS_BLOCK_PRIVATE=true` (e, se possível, `VOICE_TOOLS_ALLOWED_HOSTS`);
  localmente fica desligado porque o ERP Demo roda em `api.ipsys` (127.0.0.1).
- Seletor de voz: lista em `config('voice.studio.voices')` (8 vozes Gemini). A validação em pt-BR e a
  pré-escuta vieram no E6 (recomendadas: Leda, Kore, Aoede, Zephyr, por escolha do responsável).

**Detalhes técnicos que só apareceram na implementação (E3 — frontend do Estúdio)**
- O projeto **não registra o BootstrapVue globalmente** (só Bootstrap 5 em CSS): abas, modais e formulários do Estúdio
  são HTML/CSS do Bootstrap 5 puro; `V_EstudioModal.vue` é o modal reutilizável (confirmações, publicar, testar ferramenta).
- `estudio.js` nunca lança: devolve `{ok, data|message|erros, conflito, precisaConfirmar, validacao}`. Os campos extras de erro
  (`requires_confirmation`, `current_updated_at`) vêm no nível raiz do JSON, e `erros` é um mapa (`blocks`, `settings`, `tool`).
- Erros de blocos vêm como texto "Bloco N: ..."; a UI extrai o número para marcar o bloco certo (os demais viram erro global).
- **Regra de consistência editor × ferramentas**: toda operação de ferramenta atualiza `updated_at` do rascunho. Para não perder
  texto digitado nem sobrescrever em silêncio, operações de ferramenta ficam **bloqueadas enquanto o editor de prompt tem
  alterações não salvas** (mensagem na tela), e após cada operação a tela recarrega o detalhe do agente.
- Publicar leva só o que está salvo; por isso o botão fica bloqueado com o editor "sujo". O modal de publicar consulta
  `versions/compare` (publicada × rascunho) para resumir as mudanças e bloquear publicação de algo idêntico.
- `compare`: blocos `same` chegam com `diff: []` (só os alterados trazem linhas); o componente esconde os iguais por padrão.
- Segredos: na edição o campo do header secreto vem vazio com placeholder "mantido"; enviar vazio + `secret:true` preserva o
  valor (testado editando e renomeando). Desmarcar "secreto" exige digitar o valor de novo (o servidor devolve 422).
- Modo do teste: GET abre em "Real"; não-GET abre em "Simulado" e o modo Real pede confirmação explícita (`confirm_live`).
- Efeito só de desenvolvimento: o hot reload do webpack recria o componente de ferramentas e perde o formulário aberto (e
  pode deixar a flag "alterações não salvas" da página desatualizada); em build normal isso não acontece.
- Ainda **não existe** tela/endpoint para criar, renomear ou desativar um agente (só versões); o seletor lista os agentes existentes.

**Detalhes técnicos que só apareceram na implementação (E5 — Visão do fluxo)**
- O Drawflow carregado é `static/assets/js/drawflow.min.js`, **diferente** de `node_modules/drawflow`: conferir a API nele.
- No modo `fixed`, o arraste do fundo só funciona se a **primeira classe** (`classList[0]`) do contêiner for `parent-drawflow`. Por
  isso o `div` do canvas não tem classe própria e o estilo vem de `.estudio-fluxo-moldura > div`.
- O Drawflow escala a partir do **centro** do canvas. O componente fixa `transformOrigin` em `0 0` e sobrescreve
  `editor.zoom_refresh` (zoom em torno do centro; usado pelos botões e pelo Ctrl+roda).
- A roda comum **não** dá zoom (só com Ctrl): rola a página. O layout base não rola (`body` com `overflow: hidden`), quem rola é o
  `.voz-rolagem`; por isso o canvas não pode prender a roda, ou o resto da tela fica inalcançável.
- Um `ResizeObserver` reenquadra quando muda a largura ou a altura do canvas; sem ele o enquadramento saía deslocado (o layout
  se acomoda depois de criar o canvas). No modo "Ajustar" a própria altura do canvas depende do zoom, então o reenquadramento
  compara com a altura **alvo**, para não entrar em laço.
- O canvas só pode ser criado com a aba ativa (com `v-show` a largura é 0). Destruir no `beforeDestroy` e `clear()` ao redesenhar.
- Nós de tamanho fixo (250x96, `.fluxo-caixa`) com texto em `line-clamp`. O HTML dos nós é escapado e o texto de bloco no modal é
  exibido pelo Vue com `white-space: pre-wrap` (texto puro: `{{x}}`, `**` e crases aparecem literais, como no prompt).
- O clique é **delegado** na moldura (`data-fluxo`); um arraste de fundo que termina sobre um nó não abre o modal.
- Nunca exibir nem logar segredos: o gerador só guarda origem do dado ("parâmetro cpf", "valor fixo"), o endereço sem
  credenciais/query/fragmento e a contagem de cabeçalhos. Testes em Node verificam que valores fixos, cabeçalhos e credenciais na
  URL não aparecem em nenhum nó nem detalhe.
- `voice_agents.max_call_seconds` ainda **não é aplicado** em ligação real; por isso o desenho diz "Tempo máximo configurado" e o
  modal avisa que não garante o encerramento naquele tempo. Não prometer esse comportamento na tela.
- Decisão de legibilidade: enquadrar tudo deixava o texto de 12 px em ~6 px numa tela de ~700 px. O padrão passou a ser
  ajustar à largura (piso 0,6, teto 1) com a altura do canvas acompanhando o diagrama; "Ver tudo" fica como visão geral.
- `min-height`/`calc` na CSS em vez de `max()`: o pipeline de CSS antigo do Webpack 3 pode não entender `max()`.
- Armadilha de teste: os botões "Rascunho (vN)"/"Publicada (vN)" existem também no Playground (escondido por `v-show`); seletores
  JS precisam ser escopados ao componente do fluxo (o pai da moldura).

**Detalhes técnicos que só apareceram na implementação (E6)**
- **`<base href="/">` do `index.html` (commit `8ef78674`, M2) quebrava a paginação de todo o sistema** (achado do responsável em
  25/09/2026): com o `<base>`, `<a href="#">` resolve para `/#` (outro documento) e o clique recarregava a home. Afetava todo
  `PaginacaoBase01` (mesmo com uma só página) e qualquer outro `href="#"` sem `prevent` (217 no `src`, 26 com `prevent`). Correção: script
  no `index.html`, logo abaixo do `<base>`, que faz `preventDefault` em cliques de `a[href^="#"]` (fase de captura; os handlers do Vue e do
  Bootstrap seguem rodando). O `<base>` fica (28 caminhos relativos do `index.html` e ~50 `static/...` em componentes dependem dele).
  Provado no Chrome: 13 rotas de Cadastros (templates-meta, tags, channels, channels-v2, queues, motivos-chat, motivos-pausas,
  mensagens-predefinidas, tipo-campanha, sistema-campanha, campanha, integracoes, agentesia): "<" na 1ª página não navega e, onde
  há 2 páginas, a página 2 carrega (`?page=2`); `/voice/painel` em carga completa segue carregando (bootstrap, jquery, drawflow) e o
  modal "Perfil" (`href="#"` + `data-bs-toggle="modal"`) abre. **Não testado**: "Sair" (logout) e as abas Bootstrap dos modais.
- O worker **não tem cache**: `busca_runtime` roda no início de cada ligação (`atender`). O cache é do servidor
  (`Cache::remember`, TTL 45 s) e `publish` faz `Cache::forget` logo depois do commit. Como o `CACHE_DRIVER` é `file` (local a cada
  instância), com **várias réplicas do sysapi** (Docker Swarm) só a réplica que recebeu a publicação limpa o cache: as outras servem
  a versão antiga por até 45 s. Hoje, com uma instância, o atraso é zero. Trocar o cache para redis eliminaria o atraso (não feito).
- O Playground com "Publicada" resolve o **id** da versão e não passa pelo cache; por isso ouvir a publicada no Playground é imediato
  mesmo com várias réplicas. Não confundir com o caminho da ligação real, que usa o `runtime` sem `version` (com cache).
- O botão "Ouvir a publicada" não inicia a conversa: `getUserMedia` exige gesto do usuário e o navegador pede permissão do microfone.
- O gerador de amostras usa a API Live (`google.genai`, `live.connect` com `response_modalities=["AUDIO"]`,
  `output_audio_transcription` e `send_realtime_input(text=...)`) do mesmo `.venv` do worker; devolve PCM 16-bit mono a 24 kHz e o
  `usage_metadata` (uso por chamada: ~640 tokens de entrada, ~240–280 de saída). Sem ffmpeg no PATH o script não roda.
- URL das amostras: `static/assets/audio/voz/{Voz}.mp3`, relativa; funciona por causa do `<base href="/">` do `index.html`.
- **Armadilha de teste**: no Chrome automatizado a aba fica com `document.visibilityState = 'hidden'` e o Chrome **não carrega
  mídia** de `<audio>` nesse estado (`readyState 0`, `networkState 2` para sempre; `play()` e `loadstart` disparam, `canplay` nunca).
  WebRTC (Playground) não sofre. Para provar `<audio>` é preciso a janela em primeiro plano ou o navegador do usuário; decodificar o
  arquivo com `OfflineAudioContext.decodeAudioData` prova o arquivo, não o elemento. O `HEAD` a um arquivo de `static/` no
  webpack-dev-server devolve 404 (o `GET` devolve 200): testar com `GET`. A ferramenta `javascript_tool` bloqueia (`[BLOCKED: Cookie/query
  string data]`) respostas que contenham o cabeçalho `content-type` de uma resposta.
- Clique por coordenada: `scrollIntoView` num elemento dentro do layout base (body `overflow: hidden`) desloca o layout inteiro; refazer a
  captura de tela antes de clicar por coordenada.

**Regra de layout das telas de voz (rolagem)**: o layout base **não rola a página** (`index.html` fixa `<body style="overflow: hidden;">`
e o CSS base força `.main-content { min-height: 1570px }`), então toda tela precisa limitar a própria altura e rolar por dentro, como
as demais telas do RAPIA (`calc(100vh - N)`). Padrão adotado: classe `voz-rolagem` no `.container-fluid` (`height: calc(100vh - 118px);
overflow-y: auto; overflow-x: hidden`) em Estúdio, Histórico de Chamadas e Números e Troncos; o Painel 360 já usa colunas de altura fixa
com `overflow-y: auto` em cada uma. Toda tela nova de voz deve seguir isso. Verificado no Chrome com a roda do mouse (página em
`scrollTop 0`, contêiner rolando até o fim). Antes desta correção, Estúdio (2383px de conteúdo) e Histórico ficavam cortados.

**Detalhes técnicos que só apareceram na implementação (E4 — Playground na UI)**
- **O SDK do LiveKit derruba e reconecta sozinho quando o servidor deixa de receber pacotes do seu microfone**
  (`local connection quality lost while publishing, triggering full reconnect`, ~10 s depois). Um microfone simulado com
  **silêncio digital** dispara isso a cada 20–85 s; com ruído de fundo a conversa durou os 5 min sem nenhuma reconexão. Microfone
  real (ruído ambiente) não deve sofrer disso, e "Silenciar" não conta. Se aparecer em campo, ver `livekit.js`
  (`setMicrophoneEnabled`) e as opções de DTX/`red` da publicação.
- **Reconexão total = participante novo**: o worker fecha a sessão dele ao ver o participante sair (`close_on_disconnect`
  padrão do LiveKit Agents), mesmo que o navegador reentre 80 ms depois, e o agente continua na sala "morto". Por isso a UI
  compara o `sid` do participante local no `Reconnected` e, se mudou, encerra a conversa avisando o motivo. (Se um dia quiser
  tolerar isso no Playground, é `RoomInputOptions.close_on_disconnect=False` só nos jobs `playground:true` no `agent.py`; não feito.)
- Durante a reconexão o SDK **limpa a lista local de participantes remotos** antes de reconectar: nunca decidir "o agente saiu"
  pelo evento `ParticipantDisconnected`. A UI varre `room.remoteParticipants` a cada 250 ms e só considera que o agente saiu
  depois de 3 s contínuos de ausência, com a sala `connected` e sem reconexão em curso; a primeira fala `ai` também prova que
  ele entrou (o evento de entrada pode chegar enquanto `connect()` ainda não devolveu a sala).
- Armadilha de diagnóstico: métodos de componente Vue 2 são **propriedades da instância**, não do protótipo. Um wrapper de
  depuração com `Object.getPrototypeOf(comp).método.call` lança dentro do SDK, que loga `error reading from signal stream ...
  (reading 'call')` e reconecta. Quem for instrumentar o SDK não deve lançar exceção dentro de handlers de evento da sala.
- Reaproveitar o **mesmo** `MediaStream` de teste entre sessões falha em silêncio (o LiveKit para a faixa ao sair): o microfone simulado precisa de um `createMediaStreamDestination()` novo a cada `getUserMedia`.
- O reconhecimento de fala do Gemini vem com atraso (a fala do usuário só chega à transcrição junto da resposta do agente,
  ~15–25 s depois) e em voz sintética costuma anexar "copyright" no início; falar por cima da saudação do agente não é
  registrado (há 3 s de `aec warmup` sem interrupção).
- As primeiras conversas mostraram que o `emptyTimeout`/limite de 5 min do worker se comportam como no P3: a UI recebe a saída do
  agente e mostra "O agente saiu da sala (tempo esgotado ou conversa encerrada por ele)".

**Detalhes técnicos que só apareceram na implementação (Playground)**
- Boa parte da lista "Worker" da seção 5.2 (ler `agent_id`, montar prompt/tools
  dinamicamente, publicar transcrição e eventos) **já foi entregue no M1**; para o
  Playground faltava só o worker aceitar a versão rascunho.
- Fora de requisição HTTP (tinker/artisan) o Laravel usa o banco `ipsys`, não o do
  tenant (`ipsys-rapia`): scripts avulsos precisam replicar o `CheckSubDomain`
  (buscar `SysConnect` pelo subdomínio `api` e trocar `database.default`).
- **A autenticação das rotas `/voice/*` é a coluna `users.token`** (`TokenIsValid`),
  não o Passport: token pessoal do Passport dá 401. Para testar controller sem
  usar credencial real, chamar em processo (tinker + `setUserResolver`).
- **Correção do plano**: o token do LiveKit **não** limita a duração da sessão
  (o `exp` só vale para entrar). Os 5 min do Playground precisam ser aplicados
  pelo worker (metadata `max_seconds`) — entra no P3. Enquanto isso, o único
  limite é `emptyTimeout` (20s) da sala.
- Worker reiniciado em 24/09/2026 fora do `iniciar.ps1`, com
  `... agent.py dev *>&1 | Tee-Object -FilePath agent.log` numa janela própria
  (PID em `voip/.agente.pid`, então `iniciar.ps1 -Parar` continua valendo). O
  `Tee-Object` do PowerShell 5.1 grava o log em **UTF-16**: ler com
  `iconv -f UTF-16 -t UTF-8 agent.log`. Um worker = launcher (venv) + filho.
- Antes do P4 o worker logava `Falha ao publicar transcrição (HTTP 404)` em toda
  fala de sala `pg-`; resolvido (ver P4).
- **Despacho intermitente (causa não identificada)**: 2 sessões de ~17 nunca
  receberam o agente (`pg-api_9_G11Bja77XhhH` e `pg-api_9_5TlP5sfgBYBs`; em ambas
  a seguinte, idêntica, funcionou). O log do LiveKit mostra, na falha, `failed to
  send job request: no servers available (received 1 responses)` para o job
  `JT_ROOM` — o worker (que segue registrado, sem "worker closed WS") não
  responde à oferta — e o worker **não loga nada** (nem "received job request"),
  então a oferta não chegou ou foi ignorada. As linhas `not dispatching agent job
  since no worker is available` para `JT_PARTICIPANT/JT_PUBLISHER` são ruído
  (aparecem também em sessões boas). Não reproduziu em 8 execuções seguidas do
  smoke (nem após ~7 min ocioso). O LiveKit **não reenvia** a oferta. **Consequência
  para a UI do Playground**: esperar o agente entrar com timeout (~10–15s) e
  oferecer "tentar de novo" (nova sessão); nunca assumir que o despacho funcionou.
  Mitigação a avaliar se voltar a acontecer: despacho explícito (`CreateDispatch`)
  com nova tentativa no backend.
- O broadcast ao vivo sai como `VoiceCallUpdated` (`op = playground.event`) no
  canal público `channel.{tenant}` (privados desligados, `ENABLE_PRIVATE_CHANNELS`
  ≠ `S`). **Provado no Chrome (24/09/2026)** com uma página de escuta mínima (mesma
  config Pusher/Ably do `main.js`, chave do projeto RAPIA, `channel.api`, evento
  `VoiceCallUpdated`; a página foi apagada depois): (1) 3 eventos sintéticos
  (transcrição, `tool_called`, `tool_result simulated`) chegaram em ordem; (2)
  sessão real do Playground com o worker → a fala da IA chegou ao navegador com
  `op=playground.event`. Ressalva: não foi testado dentro do app logado (sem
  credencial); o Painel 360 usa o mesmo `iniciarEcho`, então a UI do Playground
  deve assinar igual (`$echo.channel('channel.'+subdomain).listen('.VoiceCallUpdated')`)
  e **filtrar por `data.room`** (o canal é público e compartilhado com o chat e o
  Painel 360). **Achado**: `Painel360.vue::tratarEventoVoz` tratava qualquer `op`
  desconhecido como "mudança estrutural" e recarregava as 3 listas — cada fala do
  Playground faria isso em todo SUPER com o Painel aberto. Corrigido com uma
  guarda (`op` começando por `playground.` → `return`) em `Painel360.vue`.
  **Provado no app logado (Chrome, `localhost:8080/voice/painel`, usuário SUPER,
  login feito pelo usuário)**: `window.Echo` conectado; com um listener extra em
  `channel.api`, 4 eventos `playground.event` sintéticos chegaram e o Painel **não**
  refez `POST /voice/calls/board` (1 requisição, a do carregamento); controle
  positivo — um `call.test_controle` fez o board ir a 2 requisições; e uma sessão
  real do Playground (sala `pg-api_9_cTnRGhO7q1t7`, fala da IA em ~13s) chegou ao
  app sem recarregar o board. Efeito colateral do teste: abrir o Painel põe o
  usuário em `voice_status = 1`; sair da tela **pelo roteador** restaura `2`
  (`beforeDestroy`); fechar a aba não restaura.
  O buffer + polling continua sendo a fonte confiável.
- A saudação do agente no Playground levou 12–19s do "entrar" até a primeira
  transcrição publicada (latência do Gemini Live + envio; varia) — considerar na
  UI (estado "conectando/agente ouvindo") e medir no P5.
- `voice_agents.max_call_seconds` (600 no seed) continua **sem ser aplicado em
  ligação real**; só o Playground ganhou corte por tempo. Decidir à parte se vale
  aplicar nas chamadas reais.
- O despacho por token (`roomConfig.agents`) funciona no LiveKit local; não foi
  preciso `CreateDispatch` explícito. O worker tem `agent_name` fixo, então só
  recebe despacho explícito — não disputa as salas do SIP.
- O rascunho de teste (`voice_agent_versions.id = 2`, agente 1, frase-marca
  "abacaxi") foi **apagado ao fim do P5** (tools em cascata; sobrou só a versão 1
  publicada). Para rodar o smoke com `--version draft` de novo, crie um rascunho
  (ou use `--version published`).

### M4 — Saída: discador, retornos e WhatsApp (3–4 dias)
- [ ] Discador manual e originação de chamadas (**M4.3, desbloqueado em 25/09/2026**: a saída foi provada por ligação real na
      EC2 de homologação, ver seção 7.3. Ao implementar: sala de saída com prefixo próprio e `direction='outbound'` - no teste
      a sala `call-api_*` virou `voice_calls` 45 como `inbound`)
      - [x] **M4.3.1 Sala de saída e direção** (`sysapi` + `sysweb`). Feito em 25/09/2026:
        - Prefixo **`out-{tenant}_{numero-do-paciente}_{aleatorio}`** no `REGEX_SALA` do `VoiceWebhookController`: a sala nasce
          `direction='outbound'` com o número do nome em `to_number`. Participante SIP de saída: `to_number` = `sip.phoneNumber`
          (paciente), `from_number` = `sip.trunkPhoneNumber` (nosso DID) — confirmado nos eventos da chamada 45.
        - **Decisão**: `from_number`/`to_number` seguem o sentido literal da ligação; o número do paciente é o accessor
          **`VoiceCall::patient_number`** (`$appends`; `to_number` na saída, `from_number` na entrada). Passaram a usá-lo:
          `agendar_callback`/`VoiceCallbackService::cria`, `enviar_whatsapp`, localização do contato na `registrar_triagem`,
          payloads de broadcast (campo novo `patient_number`), cartões do Painel 360 e cabeçalho da ficha (com marca de saída).
          O Histórico de Chamadas mostra De/Para literais (já tinha a coluna Entrada/Saída).
        - **`answered_at` não é gravado pelo webhook na saída**: o participante SIP entra em `dialing` e o LiveKit não manda
          webhook quando o paciente atende (sequência da chamada 45: `participant_joined` em `dialing` -> `track_published` ->
          agente entra 1 s depois -> `participant_left` em `hangup`). Quem origina a chamada (M4.3.2, `CreateSIPParticipant` com
          `wait_until_answered`) é quem grava o atendimento; sem isso a duração conta desde a discagem.
        - **Correção junto**: `VoiceWebhookTenant` em `tenant_mode=room` só reconhecia `call-`; agora aceita os mesmos prefixos
          do controller (`call|fila|filapadrao|ext|out`). Em `fixed` (o modo em uso) não muda nada.
        - **Provado** (script com eventos simulados, sem assinatura, no `ipsys-rapia`; dados apagados ao fim): sala `out-` ->
          `outbound`, DID em `from`, paciente em `to`/`patient_number`, `answered_at` nulo, agente -> `ai`, SIP sai -> `ended`;
          regressão da entrada `call-` igual a antes (`inbound`, `answered_at` gravado); middleware extrai `api` de
          `out-`/`call-`/`fila-`/`ext-` e ignora `teste-sip`/`pg-`.
        - **NÃO verificado**: ligação real numa sala `out-` (depende do M4.3.2 ou de `lk sip participant create` com `--room
          out-api_...`); a tela no navegador (build não rodado, alteração só de template).
        - Commitado em 25/09/2026: sysapi `696606b`, sysweb `d3e1d3cc`.
      - [x] **M4.3.2 Discador no backend + agente em ligação de saída** (`sysapi` + `voice-agent`). Feito e provado por ligação
        real em 25/09/2026:
        - **Ligação real, modo IA, para o celular do responsável** (script chamando `VoiceDialerService::disca`, usuário 9, com
          motivo). **Chamada 55**: a IA esperou o atendimento e falou certo, mas o job marcou `failed`/`nao_atendeu`: o
          `queue:listen` rodava desde 24/09 14:22 (antes da troca para a EC2) e os `queue:work --once` filhos herdavam o
          `LIVEKIT_URL=localhost` antigo (o Dotenv não sobrescreve variável que já está no ambiente do processo) -> `ListParticipants`
          com "connection refused", tratado como "sala sumiu". **Correções**: erro de rede/LiveKit na conferência agora **reagenda**
          (só vira `failed`, com `sem_resposta_livekit`, depois do limite); `queue:listen` reiniciado. **Chamada 62** (depois das
          correções): discou 16:20:25, agente na sala 16:20:27 esperando, atendimento 16:20:35 (`call_answered`, `answered_at` e a IA
          começando a falar no mesmo segundo), desligou 16:21:06 -> `ended`, 31 s. A IA se apresentou como a clínica, avisou da
          gravação, perguntou com quem falava e explicou o motivo (exame de sangue amanhã às 8 h, em jejum).
        - **Achados da chamada 62** (não bloqueiam): a transcrição da fala do paciente veio ruim ("S�.", "quantidade de dentes") e a
          IA entendeu o nome errado ("Quintebaldo"): áudio de telefone 8 kHz, mesmo problema de qualidade já anotado na seção 7.3; o
          `¿Qué?` da chamada 55 mostra que a transcrição de entrada ainda às vezes sai em espanhol mesmo com `language=pt-BR`.
        - **Regra de ambiente nova**: depois de mudar o `sysapi/.env`, **reiniciar o `queue:listen`** (os jobs não veem o `.env` novo).
        - Commitado em 25/09/2026: sysapi `d38392f` (o `agent.py` fica em `voip/`, fora de repositório).
        - `POST /voice/dialer/call` (`VoiceDialerController`) `{numero, modo: humano|ia, motivo?}` -> `VoiceDialerService::disca`:
          valida (número BR com DDD ou E.164; já existe saída aberta para o número; atendente em modo humano já em ligação -> 409),
          cria `voice_calls` (`outbound`, `ringing`, `user_id` no modo humano, `agent_id` no modo IA), `CreateRoom`, no modo IA
          `AgentDispatchService/CreateDispatch` (metadata `{agent_id, direction:'outbound', motivo}`), `SIP/CreateSIPParticipant`
          (identidade `sip-out-{id}`, `ringing_timeout` 30 s, `play_dialtone` só no modo humano) **sem `wait_until_answered`**.
          Erro do LiveKit -> `failed` + evento `dial_failed` (`erro_originar`). Encerrar = o `/voice/calls/end` que já existia.
        - **Atendimento**: o LiveKit não manda webhook quando o paciente atende. `JobVoiceDialWatch` (fila redis, a cada
          `watch_seconds`=2 s) chama `ListParticipants` e olha `sip.callStatus`: `active` -> `answered_at`, status `ai` (IA) ou
          `human` + `human_at` (humano), evento `call_answered`, broadcast `call.answered`; participante sumiu -> `failed`
          (`nao_atendeu`); ainda tocando depois de `ringing_timeout`+20 s -> `DeleteRoom` + `failed`. Não usei
          `wait_until_answered` porque prenderia a requisição (o `php -S` local atende uma por vez) ou o worker da fila (atrasando
          os broadcasts de todo o painel).
        - **Webhook na saída**: antes do atendimento, agente/atendente entrando **não** muda o status (fica `ringing`); o SIP saindo
          sem `answered_at` -> `failed` (e não `ended`/`abandoned`, sem criar retorno). Corrigido junto: número sem dígitos no nome
          da sala gravava `+` em `to_number`.
        - **`agent.py`**: com `direction=outbound` nos metadados, espera o `sip.callStatus=active` **antes** de abrir a sessão do
          Gemini (senão o modelo ouve o toque e fala sozinho), limite `OUTBOUND_ANSWER_TIMEOUT` (90 s) -> encerra; saudação própria
          de ligação feita pela clínica (confirma quem atendeu; o `motivo` entra na instrução). O prompt do agente é o mesmo.
        - Config `voice.outbound.*` (`VOICE_OUTBOUND_TRUNK_ID` = `ST_EkKWGzGVyyFj` já no `sysapi/.env`, `_RINGING_TIMEOUT`,
          `_WATCH_SECONDS`, `_AGENT_ID`=1). `LiveKitService::call` ganhou `$timeout`.
        - **Provado**: (1) contra o LiveKit da EC2, sem discar: `CreateRoom`, `ListParticipants` (JSON em snake_case), tronco de saída
          listado, `DeleteRoom`; o webhook real (ngrok) transformou a sala `out-api_teste_*` em `outbound` (linha apagada). (2) Lógica
          com LiveKit falso no `ipsys-rapia` (dados apagados): máscara de número, payloads/grants, job enfileirado, duplicado,
          atendente ocupado, número inválido, tocando -> reagenda, ativo -> `human` com `answered_at`/`human_at`, modo IA com
          `CreateDispatch`+motivo, participante sumiu -> `failed`, toque além do limite -> `DeleteRoom`+`failed`, erro do SIP ->
          `failed`, webhook com agente entrando durante o toque (continua `ringing`) e SIP saindo sem atender (`failed`), saída
          atendida e desligada -> `ended`.
        - **NÃO verificado**: ligação real no modo humano (precisa da tela do M4.3.3 para a atendente entrar na sala);
          `play_dialtone` na prática; paciente que recusa/não atende em ligação real; chamada pelo endpoint HTTP (a prova usou o
          serviço direto, o controller só valida e repassa);
          **corrida conhecida**: se o paciente atende e desliga antes da próxima conferência do job (2 s + latência do worker da fila
          local, que roda `--once`), o webhook marca `failed` uma ligação que foi atendida. **Aconteceu na ligação real 89
          (M4.3.3); resolvido no modo humano pelo aviso do navegador (`/voice/dialer/answered`); no modo IA continua.**
      - [x] **M4.3.3 Tela do discador, modo humano e "Ligar agora" do retorno** (`sysweb` + ajustes pequenos no `sysapi`).
        Detalhamento (25/09/2026):
        - **(a) `V_Discador.vue`** (componente novo em `components/componentes/rapia/voz/`, aberto por um botão "Discar" na barra do
          Painel 360, ao lado da presença; modal ou painel lateral, no padrão visual dos modais já existentes):
          - teclado 0–9, `*`, `#`, apagar; campo com máscara `(DD) 9XXXX-XXXX`, aceita colar número com/sem +55;
          - **busca de contato** por nome ou telefone (endpoint novo `POST /voice/contacts/search`, `{q}` -> até 10 contatos:
            id, nome, número; busca por `name LIKE` e por `RIGHT(number, 8)`, mesmo critério "fuzzy" do
            `localizaOuCriaContato`); escolher um contato preenche o número;
          - seletor **Quem fala: Eu (atendente) | IA** (padrão: Eu) e campo **Motivo** (obrigatório no modo IA, até 300
            caracteres, vai para a saudação do agente; opcional no humano, fica no evento `dial_requested`);
          - botão Ligar -> `POST /voice/dialer/call`; erros 409 viram mensagem na própria tela (número inválido, já em ligação,
            número com ligação aberta, discador não configurado); botão desabilitado durante a requisição (evita discagem dupla);
          - **pré-condição do modo humano**: presença Disponível (`voice_status = 1`) e microfone liberado; conferir as duas
            coisas antes de discar (sem microfone, a pessoa atenderia e ninguém ouviria).
        - **(b) Modo humano, entrar na sala durante o toque**: depois do `dialer/call`, o navegador pede `POST /voice/token`
          (`room` = `room_name` devolvido) e conecta pelo `livekit.js` **imediatamente** (ouve o `play_dialtone` enquanto toca).
          Ajustes necessários:
          - `Painel360.vue`: `mostrarSoftphone` hoje exige `status === 'human'`; incluir a saída em curso da própria atendente
            (`direction === 'outbound' && user_id === currentUserId && status in ['ringing','human']`); selecionar a chamada nova
            automaticamente depois de discar;
          - `V_Softphone.vue`: estado "Chamando..." (contador do toque) enquanto `answered_at` for nulo; ao receber
            `call.answered` pelo Pusher, virar "Em ligação" com o cronômetro contando de `answered_at`; `call.ended` com
            status `failed` -> mensagem "Não atendeu" e fecha sozinho em ~3 s;
          - cancelar durante o toque = o "Desligar" já existente (`/voice/calls/end`, que faz `DeleteRoom`); conferir que a chamada
            vira `failed` (e não `ended`) quando cancelada antes do atendimento — hoje o `end` grava `ended`: ajustar no
            `VoiceCallsController::end` (saída sem `answered_at` -> `failed`, motivo `cancelada` no evento);
          - DTMF do teclado do softphone já existe (`sendDtmf`); validar numa URA de terceiros (ex.: ligar para um 0800).
        - **(c) "Ligar agora" do retorno originando de verdade** (hoje só aceita a oferta; a atendente liga por fora):
          - `POST /voice/callbacks/accept` passa a aceitar `{discar: true}` (padrão true na tela): depois do aceite, chama
            `VoiceDialerService::disca(user, callback.phone, 'humano', 'Retorno: ' . reason/note)` e grava o vínculo;
          - **vínculo retorno <-> chamada**: coluna nova `voice_callbacks.dial_call_id` (migration com a checagem `rapia`, rodar só
            no `ipsys-rapia`) — o `call_id` que já existe é a chamada **de origem** (a que gerou o retorno), não a de saída;
          - **resultado automático**: quando a chamada de saída termina, o `VoiceCallbackService` fecha o retorno sozinho —
            atendida (`answered_at` preenchido) -> `done`; `failed` -> mesmo caminho do "Não atendeu" (volta para `pending`
            com `next_attempt_at` +10 min até `max_attempts`, depois `failed`). Gancho: `VoiceDialerService::falha` e o
            `encerraChamada` do webhook (ou um listener único de fim de chamada, para não duplicar a regra em dois lugares);
          - os botões manuais "Atendeu"/"Não atendeu" continuam como plano B (ex.: discador fora do ar -> a atendente liga
            pelo celular e registra), mas somem enquanto houver uma chamada de saída viva para aquele retorno;
          - erro ao discar (409/LiveKit) -> o retorno volta para `offered` para a mesma atendente (não perde a oferta nem
            conta tentativa).
        - **(d) Histórico e ficha**: `HistoricoChamadas.vue` já mostra Entrada/Saída; acrescentar filtro por direção e o motivo
          da falha (`dial_failed.motivo`: `nao_atendeu`, `erro_originar`, `sem_resposta_livekit`, `cancelada`) numa coluna
          "Resultado"; ficha da chamada mostra "Ligação feita por <atendente>" ou "Ligação feita pela IA — motivo: ...".
        - **Critérios de pronto**: ligação real no modo humano (atendente ouve o toque, paciente atende, os dois se ouvem,
          `answered_at`/`human_at` gravados, desligar pelos dois lados); cancelar durante o toque -> `failed`/`cancelada`;
          retorno com "Ligar agora" -> atendeu -> `done` sem clicar em nada; retorno -> não atendeu -> volta para a fila;
          modo IA disparado pela tela (a prova do M4.3.2 usou o serviço direto).
        - **Fora deste passo**: discagem em massa/campanha, agendamento de ligações, gravação (M5), número de origem diferente
          do DID único.
        - **Andamento 25/09/2026 — (a) e (b) feitos e provados por ligação real; (c) e (d) pendentes**:
          - `sysapi`: `POST /voice/dialer/contacts` (rota com esse nome, não `/voice/contacts/search`) -> `VoiceDialerService::
            buscaContatos` (sem letras e 4+ dígitos = telefone, senão nome; até 10). **Achado**: `contacts.number` tem cadastros
            com máscara (`(84) 98829-6353`), então a busca e o vínculo do contato comparam só os dígitos
            (`REGEXP_REPLACE(number,'[^0-9]','')`, MySQL 8). `dialer/call` aceita `contact_id` (sem ele, acha pelo número) e
            exige `motivo` no modo IA (422 com mensagem). `/voice/calls/end` numa saída ainda tocando -> `VoiceDialerService::
            cancela` (`DeleteRoom`, `failed`, `dial_failed` motivo `cancelada`). Webhook: saída não atendida agora grava também
            `dial_failed`/`nao_atendeu` e `duration_seconds = 0` (antes ficava com o tempo de toque, ex. chamada 67 = 17 s).
          - `sysweb`: `V_Discador.vue` (reaproveita `V_EstudioModal`; busca com atraso de 300 ms, teclado 0–9 + apagar — `*`/`#`
            ficam no DTMF do softphone —, Eu/IA, motivo, aviso quando Indisponível, checagem do microfone antes de discar no
            modo Eu, erros do backend na própria tela); botão **Discar** na barra do Painel 360; `mostrarSoftphone` inclui a
            saída da própria atendente em `ringing`; `V_Softphone` mostra "Chamando <número> · mm:ss" / "Em ligação · mm:ss"
            (desde `answered_at`) e "Cancelar" durante o toque; o Painel recarrega a ficha em `call.answered`,
            `participant_left` e `room_finished` (isso também resolve, para qualquer chamada, o item do M5 "detalhe de chamada
            encerrada fica aberto sem aviso" — conferir numa entrada real antes de fechar lá) e avisa "encerrada sem
            atendimento" na saída própria que falhou. Ícone `mdi-robot-outline` não existe na versão do MDI do projeto: usar
            `mdi-robot`.
          - **Provado no Chrome, pelo responsável, com ligação real para o próprio celular (25/09/2026)**: modo Eu (chamada 69:
            toque no PC, atendeu 18:45:23, conversa nos dois sentidos, desligou pelo celular -> `ended` 15 s, `human_at`
            gravado); cancelar durante o toque (68 -> `failed`/`cancelada`); modo IA pela tela com motivo (71 -> atendida
            18:47:13, `ended` 25 s). 67 e 70 = tentativas recusadas/desligadas no toque -> `failed`. Busca de contato na tela
            (nome e telefone) e vínculo `contact_id` conferidos. Testes com LiveKit falso (11 cenários + busca/cancelamento)
            continuam verdes.
          - Commitado em 25/09/2026: sysapi `5c4bef9`, sysweb `1eb6a475`. Prompt da sessão seguinte ((c) e (d)):
            `voip/PROMPT-INICIO-M4.3.3-CD.md`.
        - **Andamento 25/09/2026 (noite) — (c) e (d) feitos e provados por ligação real**:
          - **Vínculo**: migration `2026_09_25_130000_add_dial_call_id_voice_callbacks` (só `ipsys-rapia`): `voice_callbacks.dial_call_id`
            (FK `voice_calls`, `ON DELETE SET NULL`) = ligação de saída **da tentativa atual**; `aceita()` limpa o da tentativa
            anterior (sem isso a 2ª tentativa do mesmo retorno herdava a ligação velha). `abertos()`/board devolvem `dial_call_id`,
            `dial_status`, `dial_answered_at` (eager load, sem N+1).
          - **`accept` com `discar`** (padrão `true` na tela): `aceita()` -> `VoiceDialerService::disca(user, phone, 'humano',
            'Retorno: {reason} - {note}', contact_id)` -> `vinculaDiscagem()` (evento `callback_dialed`); resposta traz `call`.
            Erro do discador -> `desfazAceite()`: volta para `offered` com a mesma atendente, `attempts - 1`, **`offered_at`
            renovado e novo job `expirar`** (o job da oferta original já tinha rodado ou encontraria `calling`: a oferta ficaria
            sem prazo), evento `callback_dial_error`, 409 com a mensagem do discador. `erro_originar` acontece dentro do `disca()`
            antes do vínculo existir, então quem trata é essa reversão (o gancho automático não acha o retorno). Sem `discar` =
            comportamento antigo (link "Vou ligar por fora" no cartão, plano B com o discador fora do ar).
          - **Resultado automático, ponto único** `VoiceCallbackService::resultadoDaDiscagem(VoiceCall)`: atendida -> `done`
            (no atendimento, não no fim); `failed`/`ended`/`abandoned` sem `answered_at` -> regra do "Não atendeu" (extraída do
            `conclui` para `aplicaResultado`, sem exigir `$user`); **cancelada conta tentativa** (decisão do responsável).
            Idempotente pelo `UPDATE ... WHERE status='calling' AND dial_call_id=?`. Evento `callback_result` com
            `origem: 'discador'` (manual = `'manual'`), broadcast `callback.updated` com `next_attempt_at`. Chamado em:
            atendimento (`registraAtendimento`), `VoiceDialerService::falha` (nao_atendeu, cancelada, sem_resposta_livekit) e
            `VoiceWebhookController::encerraChamada` para saída (cobre o caminho `failed` do SIP saindo **e** o `room_finished`,
            que grava `ended` mesmo sem atendimento).
          - **Achado da ligação real (chamada 89)**: o responsável atendeu e falou ~5 s, mas ficou `failed`/`nao_atendeu`: o
            `JobVoiceDialWatch` não conferiu durante a conversa porque a fila local (`queue:listen`, um `--once` por job) estava
            ocupada com ~8 broadcasts da discagem/webhooks (no modo humano há mais eventos: o navegador também entra na sala). É a
            "corrida conhecida" do M4.3.2, pior do que o previsto. O webhook não ajuda a distinguir: `sip.callTag`/`callIDFull`
            aparecem também em ligações recusadas (67, 70). **Correção (modo humano)**: o navegador da atendente está na sala e
            recebe `ParticipantAttributesChanged` (livekit-client 2.22.3) -> `sip.callStatus = 'active'` -> `POST
            /voice/dialer/answered {id}` -> `VoiceDialerService::atendidaPeloNavegador` (só a dona da chamada, ainda `ringing`;
            confere no LiveKit e recusa só se o SIP ainda estiver na sala e não `active`; se já saiu, vale o navegador). Job e
            navegador passam pelo mesmo `registraAtendimento` (UPDATE condicional; evento `call_answered` com `origem`
            `job|navegador`). O Painel recarrega a ficha pela resposta, sem esperar o broadcast (que passa pela mesma fila).
            **Modo IA continua dependendo do job** (a mesma correção caberia no `agent.py`, que já espera o `active`: avisar o
            backend por `/voice/worker/event`; não feito). Em produção com `queue:work` em daemon a latência é bem menor.
          - **Front**: "Ligar agora" confere o microfone (`painel360.js::microfoneLiberado`, extraído do `V_Discador`), chama
            `accept` com `discar:true` e reaproveita `onDiscou` (softphone em "Chamando…"); cartão com ligação viva mostra
            "Chamando <número>…"/"Em ligação…" no lugar de "Atendeu"/"Não atendeu" e o clique abre a ligação de saída; de volta em
            `pending` mostra "Não atendeu — nova tentativa às HH:MM".
          - **(d)**: `listAll` com parâmetro próprio `direction` (`inbound|outbound`, outro valor é ignorado; não passa pelo
            `whereRaw` dos `filters`) e `dial_failed_motivo` por subconsulta (2 consultas por página). `HistoricoChamadas.vue`:
            Todas/Entrada/Saída, coluna Paciente (`patient_number`; De/Para literais mantidos), coluna Resultado (Atendida, Não
            atendeu, Cancelada, Erro ao discar, Sem resposta do servidor; saída `failed` sem evento = "Não completada", caso da 67,
            anterior à correção do webhook). Ficha: "Ligação feita por <atendente>" / "Ligação feita pela IA" + " — motivo: …"
            (do `dial_requested`) e os eventos da discagem descritos na linha do tempo.
          - **Provado**: (1) LiveKit falso no `ipsys-rapia`, dentro de transação desfeita: 39 cenários (accept com sucesso, motivo,
            job, board; tocando/atendeu/gancho repetido; não atendeu -> `pending` +10 min; webhook repetido; 2ª tentativa com
            `dial_call_id` novo; cancelada; `room_finished` na 3ª -> `failed`; SIP saiu -> `pending`; erro do LiveKit / já em
            ligação / número inválido -> 409 e `offered` sem gastar tentativa; sem `discar` + "Atendeu" manual; atendimento pelo
            navegador: outro usuário, SIP tocando, SIP já saiu, SIP ativo, repetido, job depois, webhook depois -> `ended`, endpoint
            HTTP 200/409). (2) **Ligações reais no Chrome, logado pelo responsável**: 89 (antes da correção: atendida, marcada
            não atendeu -> retorno voltou para a fila, o que provou esse caminho); **101** (retorno 19, 2ª tentativa: atendeu
            19:14:15, `call_answered` origem navegador no mesmo segundo, retorno `done` sem clique, `ended` 12 s); **103** (retorno
            30: o responsável **recusou**, a operadora desviou para a **caixa postal**, que atende -> `sip.callStatus=active` ->
            registrado como atendida e retorno `done`; encerrada pelo softphone). Histórico conferido na tela (filtro e Resultado).
          - **Limitação (não resolvida)**: caixa postal/secretária eletrônica = atendimento para o SIP; o retorno fecha como `done`.
            Proposta para depois (M4.4 ou item próprio): botão "Caiu na caixa postal" no softphone da saída de retorno (reabre como
            "Não atendeu") e/ou detecção de secretária (AMD) pelo áudio no worker. **NÃO verificado**: recusa real sem caixa postal
            (o celular de teste desvia sempre), "Não atendeu" real depois da correção (a 89 foi por outro motivo), mais de uma
            atendente. A 89 ficou no banco com o resultado errado (é o registro real do achado).
          - Dados de teste apagados (origens 88/102, retornos 19/30 e eventos); ficaram as ligações reais 89, 101, 103.
          - Commitado em 25/09/2026: sysapi `779e952`, sysweb `60e7f235`.
      - [ ] **M4.4 Qualidade do áudio e compreensão -> atendimento humano** (`voice-agent` + `sysapi` + Estúdio). Registrado em
        25/09/2026, depois da ligação 62 (fala do paciente transcrita errada em áudio limpo) e da pergunta do responsável:
        "é possível verificar a qualidade do áudio e, se estiver ruim ou com muito ruído, direcionar para o humano?".
        - **Por que não dá só com o LiveKit**: a "qualidade de conexão" (`ConnectionQuality`) mede perda/jitter entre o serviço
          SIP e o servidor LiveKit, que estão na mesma EC2 — fica sempre "ótima". O que estraga o áudio (celular, operadora,
          provedor, codec 8 kHz) está antes do Asterisk e o LiveKit não vê. O cancelamento de ruído pronto do LiveKit (Krisp /
          `livekit-plugins-noise-cancellation`) só funciona no LiveKit Cloud, não no self-hosted; no worker hoje só existe o
          plugin `google`.
        - **Duas coisas diferentes a detectar**:
          1. **Sinal ruim** (ruído de rua/TV/vento, áudio estourado, cortes): mede-se no próprio worker, nos quadros de áudio do
             paciente;
          2. **Compreensão ruim** (caso da 62: áudio limpo, modelo entendendo errado; "¿Qué?" da 55): não aparece em métrica de
             sinal; mede-se pelo comportamento da conversa.
        - **(a) Métricas de sinal no `agent.py`** (Python puro + numpy, sem dependência nova pesada): assinar a trilha do participante
          SIP (`rtc.AudioStream`) em paralelo à sessão e, em janelas de ~5 s:
          - **ruído de fundo** = RMS (dBFS) dos trechos sem fala (usar a detecção de fala do próprio Gemini/atividade de voz, ou
            um limiar de energia simples com histerese);
          - **nível de fala** = RMS dos trechos com fala; **SNR estimada** = fala − ruído (dB);
          - **clipping** = % de amostras em ±32767 (ou >= 0,99 do fundo de escala);
          - **buracos** = sequências de quadros com silêncio digital absoluto (0) >= 100 ms (as lacunas de ~0,12 s a cada 10 s da
            seção 7.3 aparecem aqui);
          - publicar um evento `audio_quality` a cada ~10 s e um resumo no fim (`POST /voice/worker/event`, grava em
            `voice_call_events` com o `turn_seq` atual) — serve também para o dashboard do M5 e para o custo/qualidade por
            provedor;
          - cuidado de CPU: o worker roda no PC na homologação; medir o custo por chamada (numpy em quadros de 10–20 ms é leve,
            mas confirmar com 2–3 chamadas simultâneas).
        - **(b) Sinais de compreensão**:
          - **regra no prompt** (vale já, sem código): "se não entender o paciente duas vezes seguidas, diga que a ligação está
            com dificuldade e chame `transferir_para_atendente`" — publicar como nova versão do agente pelo Estúdio, com o
            tratamento de `sem_atendente` (retorno/WhatsApp) que o rascunho do M4.2 já tinha;
          - **contador no worker**, independente do modelo: por turno do paciente, marcar "incompreensível" quando a transcrição
            vier vazia/`??`, em outro idioma (heurística: `¿`, `¡`, palavras espanholas frequentes; ou detector de idioma leve),
            ou quando a resposta da IA contiver pedido de repetição ("pode repetir", "não entendi", "não consegui ouvir");
            N marcações (padrão 2) em sequência -> gatilho;
          - registrar cada marcação como evento `comprehension_miss` (com o texto) para calibrar.
        - **(c) Decisão e transferência**: gatilho de sinal (ex.: SNR < X dB por Y janelas seguidas, ou buracos > Z%) **ou** de
          compreensão -> o worker injeta na sessão uma instrução ("avise que a ligação está com interferência e que vai passar
          para um atendente") e chama o mesmo caminho da tool `transferir_para_atendente` (endpoint
          `/voice/worker/tools/transferir_para_atendente`, motivo `qualidade_audio` ou `compreensao`). Sem atendente
          disponível -> a resposta `sem_atendente` já existente faz a IA oferecer retorno (`agendar_callback`) ou WhatsApp
          (`enviar_whatsapp`), que em áudio ruim é o melhor caminho. Uma única transferência por chamada (não repetir o aviso).
          Na ficha do Painel 360, mostrar o motivo ("Transferida por áudio ruim — SNR 6 dB") para a atendente já começar
          sabendo.
        - **(d) Configuração por agente, versionada** (junto de modelo/voz/temperatura em `voice_agent_versions.settings`,
          editável no Estúdio > Configurações): `quality_guard` = `off | sombra | ativo`, `snr_min_db`, `janelas_seguidas`,
          `max_buracos_pct`, `max_incompreensoes`. Playground: métricas aparecem na tela (útil para testar com ruído de fundo),
          mas nunca transfere (sandbox).
        - **(e) Implantação em duas fases** (o risco principal é transferir demais e anular o valor da IA):
          1. **modo sombra**: só mede e grava (`audio_quality`, `comprehension_miss`), sem transferir; juntar 10–20 ligações
             reais variadas (ambiente silencioso, rua, viva-voz, carro, celular ruim) e calibrar os limites olhando os eventos;
          2. **modo ativo** com os limites calibrados; a regra de compreensão do prompt pode entrar já na fase 1 (é segura).
        - **(f) Opcional, avaliar depois da fase 1**: transcrição dedicada de telefonia **em paralelo** (ex.: Deepgram ou Google
          Speech-to-Text com modelo de telefonia/8 kHz) só para a transcrição exibida e para a triagem; a conversa continua no
          Gemini Live. Ataca o problema da 62 (triagem gravando nome errado), não a transferência. Custo extra por minuto a
          levantar antes.
        - **(g) Também possível, mais caro**: métricas de rede do trecho do provedor pelo **RTCP do Asterisk** (perda de pacotes,
          jitter reais da operadora) via AMI durante a ligação. Exige correlacionar o canal do Asterisk com a sala do LiveKit
          (Call-ID/cabeçalho SIP) e AMI acessível pela VPN (hoje só em loopback na EC2, ver seção 7.3). Deixar para depois da
          fase 1 mostrar se o problema é rede ou codec.
        - **Critérios de pronto**: fase 1 no ar com eventos gravados em ligação real; regra de compreensão publicada; limites
          propostos com base nas ligações de calibração; fase 2 provada com uma ligação real em ambiente barulhento sendo
          transferida (e outra, silenciosa, não).
        - **Estimativa**: 1–2 dias (fase 1 + regra do prompt + configuração); fase 2 depende de juntar as ligações de calibração.
        - Prompt de início da sessão da fase 1 (modo sombra): `voip/PROMPT-INICIO-M4.4.md` (26/09/2026).
        - **Fase 1 — andamento (26/09/2026)**. Decidido no início: nas ligações de calibração o modo sombra é ligado por
          variável de ambiente do worker (`VOICE_QUALITY_GUARD_FORCAR=sombra`, só na homologação), sem publicar versão.
          - [x] **6.1 Configuração**: chaves `quality_guard`, `snr_min_db`, `janelas_seguidas`, `max_buracos_pct`,
            `max_incompreensoes` em `VoiceAgentVersion::CAMPOS_CONFIG`. Detalhe da implementação: `validaConfig` descarta chave
            fora de `CAMPOS_CONFIG` e `configEfetiva` completava com colunas de `voice_agents`, que não têm essas chaves; agora
            `VoiceAgentVersion::valorPadrao()` usa `PADROES_QUALIDADE` (off, 10 dB, 2 janelas de 10 s, 5%, 2) para versão sem a
            chave (a v1 publicada tem `settings` nulo). Faixas validadas: SNR 0–40, janelas 1–30, buracos 0–100%,
            incompreensões 1–10. Runtime devolve `quality_guard: {mode, snr_min_db, janelas_seguidas, max_buracos_pct,
            max_incompreensoes}`. Estúdio > Configurações da sessão ganhou o grupo "Qualidade do áudio e compreensão" (texto de
            ajuda: limites provisórios; ativo ainda funciona como sombra) e os rótulos na comparação de versões. Prova (script
            em transação desfeita): inválido -> 422 com as mensagens; rascunho salvo com `sombra`/12,5 dB e chave intrusa
            descartada; runtime `?version=draft` devolve `sombra`; publicada continua `off` e `settings` NULL.
            Testado também no Chrome (26/09): grupo novo com os padrões, erro de faixa em vermelho, rascunho salvo e mantido
            ao recarregar, "Comparar" mostrando só os 2 campos alterados, abas Fluxo/Playground intactas; runtime publicado
            pela API real = `off`; "rascunho igual à publicada" (assinatura) certo nos dois sentidos; `playground_smoke.py`
            quick com o rascunho 3/3 (24/24 checks). Rascunho v2 (id 58, sombra/12 dB) mantido para a regra da 6.4.
            - **Bug antigo corrigido (M3)**: `draftSave` sem rascunho existente + configuração inválida criava o rascunho mesmo
              assim (o 422 era devolvido de dentro do `DB::transaction`, que confirmava). Agora lança
              `HttpResponseException` e a transação é desfeita. Prova: sem rascunho, inválido -> 422 e 0 rascunhos; válido -> 1.
            - **Achado: despacho recusado por CPU do PC**. O worker informa ao LiveKit a CPU da máquina (psutil, 0–1) como
              carga; com o PC perto de 1 (Chrome, gateway Java etc.) o LiveKit responde "no servers available (received 1
              responses)" e o job nem chega ao worker (sem "received job request" no log). Medido: carga 0,85–1,00 -> 0/4
              despachos; PC aliviado (0,27–0,56) -> 3/3. Causa provável do "despacho intermitente" do M3. Proposta para a 6.3:
              `load_fnc` fixo por variável de ambiente só na homologação (o `AgentServer` 1.8.2 aceita `load_fnc`).
            - Commitado em 26/09/2026: sysapi `df8551f`, sysweb `e1b89d78`.
          - [x] **6.2 Medição offline**: `voice-agent/qualidade.py` (numpy, declarado no `requirements.txt`).
            `MedidorQualidade` recebe PCM int16 mono 16 kHz em pedaços de qualquer tamanho e fecha janelas de 10 s com
            `fala_pct`, `fala_dbfs`, `ruido_dbfs`, `snr_db`, `clipping_pct` (|x| >= 32440), `buracos_qtd/ms/pct` (corridas de
            |x| <= 2 com >= 100 ms, medidas por amostra), `pico_dbfs`; `fecha()` devolve a janela parcial do fim (>= 2 s).
            Método (detalhes que só apareceram testando): piso de ruído = **percentil 10 dos quadros de 20 ms da própria
            janela** (a 1ª versão, piso adaptativo contínuo, começava no nível da fala e estragava a 1ª janela); fala acima de
            piso + 6 dB, sai abaixo de + 3 dB, 200 ms de sustentação (com + 10 dB a fala não era detectada em SNR <= 5 e a janela
            ruidosa passava como "sem fala"); SNR por subtração de potência; SNR só com >= 3% de fala. `ResumoQualidade`
            aplica os limites da versão e diz se o gatilho **teria** disparado (modo sombra): motivos `snr_baixa`, `buracos` e
            `ruido_alto_sem_fala` (sem fala detectável e ruído >= -30 dBFS — constante provisória, a calibrar); janela sem fala
            em ambiente silencioso não conta nem zera a sequência. Prova: `scripts/testa_qualidade.py` (14/14): limpo -> 59 dB;
            SNR 20/10/5 -> 19,5/9,4/3,8; SNR 0 -> todas ruins e gatilho na janela 2; fala baixa -38 dBFS SNR 15 -> -38,3/14,5;
            banda de telefone (SNR real 8,7 depois do filtro) -> 7,9; clipping = % calculado no sinal; 5x120 ms + 3x60 ms de
            buraco -> 5/janela, 6,0%; lacunas da seção 7.3 -> 1/janela, 1,2%; só ruído -> sem SNR; silêncio total -> 100%.
            Com voz real (gravação do agente no Playground + ruído branco): SNR 30/15/8/3 -> 29,1/14,1/7,2/2,0 (viés de ~-1 dB).
            Custo: ~1,6 ms de CPU por segundo de áudio (0,16% de um núcleo por chamada).
            Ajuste feito na 6.3 (visto no Playground): silêncio digital **> 1 s** não é buraco, vai para
            `silencio_digital_pct` e não marca a janela — é o paciente calado com supressão de silêncio (DTX) ou microfone
            sem envio; o smoke sem ruído chegava a "90% de buracos". Buraco = 100 ms a 1 s (quedas reais; as da seção 7.3
            têm ~0,12 s). Casos novos: silêncio total -> 100% silêncio digital, 0 buracos, janela não ruim; pausas de 3 s em
            zero -> 0 buracos. Prova final: 15/15.
          - [x] **6.3 Medição no worker** (`agent.py`): `GuardaQualidade` assina a 1ª trilha de áudio de participante que
            não é agente (SIP ou navegador) com `rtc.AudioStream.from_track(track, sample_rate=16000, num_channels=1)` — o
            `AudioFrame.data` é memoryview int16, `np.frombuffer` direto; publica `audio_quality` a cada 10 s (payload: as
            métricas + `motivos`, `ruins_seguidas`, `gatilho_dispararia`, `modo`; `turn_seq` atual) e, no encerramento do job
            (`add_shutdown_callback`), a janela parcial + `audio_quality_summary` (resumo + compreensão + `modo`, `origem`,
            `participante`, `sessao_s`, `cpu_processo_s/pct_nucleo`, `cpu_medicao_ms`). `publica_evento` = mesmo padrão do
            `publica_transcricao` (erro não derruba a ligação). Modo: `quality_guard.mode` da versão; `ativo` = sombra +
            aviso no log; `VOICE_QUALITY_GUARD_FORCAR` (off|sombra|ativo, só homologação) sobrepõe a versão (origem `env`).
            **Carga**: `VOICE_WORKER_CARGA_FIXA=0` no `voice-agent/.env` (só homologação) -> `AgentServer(load_fnc=...)`;
            sem a variável vale o padrão do SDK. Provas (`playground_smoke.py`, opções novas `--ruido-dbfs` = microfone com
            ruído branco contínuo e falas por cima, `--fala-ganho-db`, `--expect-quality`, modo `compreensao`):
            ruído -45 dBFS -> chega -49 (Opus), SNR 26,8, gatilho não; ruído -25 -> SNR 7,4, gatilho na janela 2 e a
            transcrição virou espanhol ("mi hermana y mi da Silva Souza"); ruído -20 -> SNR 2,4 e **o Gemini travou** (não
            fechou o turno do paciente, ficou sem responder: ruído contínuo alto também quebra a detecção de fala dele).
            CPU: no Windows os jobs são **threads** do processo do worker (`JobExecutorType.THREAD`), então o número é do
            processo: ~22–30% de um núcleo com 1 sessão (Gemini + áudio + HTTP), ~56–62% com 2 simultâneas (ambas 10/10
            checks); a medição em si: 16–250 ms de CPU por sessão de 40–130 s. Playground (sysweb `V_EstudioPlayground.vue`):
            `audio_quality`/`audio_quality_summary`/`comprehension_miss` saem da lista "Ferramentas chamadas" e viram uma
            linha "Qualidade do áudio" (última janela ou resumo, motivos, falas não entendidas) — não testado no navegador
            (Chrome automatizado sem microfone).
          - [x] **6.4 Compreensão**: `qualidade.py` — `motivos_paciente` (transcrição vazia/`??`/só pontuação; espanhol:
            `¿ ¡ ñ` ou 2+ palavras da lista com pelo menos uma "forte": usted, hola, buenos, necesito, puede, hablar...),
            `motivos_ia` (pedido de repetição por regex sem acento: "pode repetir", "não entendi", "não consegui ouvir",
            "ligação cortando", "falar mais alto", **"falar em português"**; IA com `¿ ¡`), `ContadorCompreensao`: incidente
            = sinais a até 6 s um do outro, **em qualquer ordem** (achado: o Gemini às vezes entrega a fala da IA antes da
            transcrição do paciente que ela respondeu), cada sinal vira um `comprehension_miss` (`incidente`, `mesclado`,
            `motivos`, textos, `seguidas`, `gatilho_dispararia`); resposta normal a uma fala boa zera. Prova offline 22/22.
            **Regra no prompt** (rascunho v2, id 58, NÃO publicado): bloco novo "Ligação com dificuldade" (conta como não
            entendida cada vez que pedir para repetir, falar mais alto ou **falar em português**; na 2ª seguida avisa e chama
            `transferir_para_atendente`, registrando antes o que já tiver) e a regra antiga "depois de duas tentativas siga em
            frente" trocada. A 1ª redação ("se não entender duas vezes") não bastou: o modelo "entendia" que era espanhol e
            pedia português indefinidamente. Prova (modo `compreensao`, 3 falas em espanhol): na 2ª resposta a IA disse "A
            ligação está com dificuldade. Vou passar para um atendente humano" e chamou `transferir_para_atendente`
            (sandbox -> `sem_atendente`). Contador: 4 incidentes para 3 trocas (a transcrição de uma fala chegou 12 s antes da
            resposta da IA) — conta um pouco a mais; calibrar. Observação: a v1 publicada não tem `agendar_callback` /
            `enviar_whatsapp` (as tools do M4.2 ficaram no rascunho descartado); com `sem_atendente` a IA só consegue seguir a
            orientação em texto. Incluí-las no rascunho antes de publicar é decisão do responsável.
          - [x] **6.5 Ficha do Painel 360** (`V_FichaChamada.vue`): `audio_quality`/`audio_quality_summary` saem da linha do
            tempo; `comprehension_miss` entra uma vez por incidente ("IA não entendeu o paciente (fala em espanhol, IA pediu
            para repetir) — 2ª seguida"); linha no cabeçalho "Áudio: SNR ~X dB · ruído ~Y dBFS · cortes Z% [· N fala(s) não
            entendida(s)] [· abaixo do limite]" (do resumo; durante a chamada, da última janela), com dica "medição em teste".
            Também ganharam rótulo `track_published`/`track_unpublished` (apareciam crus desde antes). Prova no Chrome
            (26/09, ligações 104–107 selecionadas pelo método do Painel, já que encerradas não aparecem na lista): 104 "Áudio:
            SNR ~49,2 dB · ruído ~-74,8 dBFS · cortes 2,7%"; 106 "... · 2 fala(s) não entendida(s) · abaixo do limite" e na
            linha do tempo "IA não entendeu o paciente (fala em espanhol)" + "... — 2ª seguida"; 107 "(IA pediu para
            repetir)"; nenhuma das 6–11 medições por chamada na linha do tempo.
            Corrigido em seguida (vistos neste teste, anteriores ao M4.4): (1) a ficha de chamada **encerrada** mostrava a
            duração contando até agora ("Encerrada · 08:53" numa ligação de 1 min 48 s) -> usa `ended_at` (104: 00:59,
            106: 01:47); (2) presença: sair do Painel pela navegação interna já gravava Indisponível (provado: aberto = 1,
            saiu = 2; o alarme anterior foi do meu teste), mas **fechar a aba/recarregar** não passava pelo
            `beforeDestroy` e o usuário ficava Disponível até o próximo login -> `pagehide` envia a presença 2 com `fetch`
            `keepalive` (`painel360.js::presencaAoFecharPagina`); provado: aberto = 1, navegação completa para fora = 2.
            Commitado: sysweb `6aba5392`.
          - [x] **6.6 Calibração (26/09/2026)** — 4 ligações reais de entrada do celular de teste para a IA (URA dígito 1,
            agente 1 v1 publicada; sombra por `VOICE_QUALITY_GUARD_FORCAR=sombra` no `voice-agent/.env`). Achados:
            o resumo chega ~20 s depois de desligar (fim do job = sala fechada pelo `departure timeout`); o **celular aplica
            supressão de ruído e controle de ganho** antes da operadora: o ruído de fundo quase não chega e a fala baixa chega
            no nível normal — a SNR ficou >= 27 dB em todas.

            | Ligação | Cenário | Janelas | SNR med. (mín.) | Ruído | Fala | Fala % med. | Buracos (ms) | Incompreensões | O que a IA errou | CPU processo |
            |---|---|---|---|---|---|---|---|---|---|---|
            | 104 | silêncio | 6 (57 s) | 49,2 (43,5) | -74,8 | -22,9 | 12% | 7 = 2,7% (308, 672 e outros; lista só a partir da 105) | 0 | nada | 15,6% |
            | 105 | TV alta | 8 (74 s) | 42,2 (30,1) | -71,3 | -26,9 | **95%** | 3 = 0,7% (252, 132, 119) | 0 | nome ("Bancas"), 1 dígito do CPF | 26,1% |
            | 106 | viva-voz | 11 (106 s) | 32,7 (27,5) | **-62,2** | -29,0 | 67% | 2 = 0,5% (322, 171) | 2 ("¿Qué?" x4) | nome ("Aribaldo"), CPF 1 vez | 23,7% |
            | 107 | fala baixa | 7 (70 s) | 46,1 (42,7) | -73,4 | -27,2 | 14% | 8 = 4,2% (112–930) | 1 (IA pediu repetição) | nome 1 vez; "Eso no es", "baja deudas" | 20,8% |

            Leitura: (1) a **SNR não separa** os cenários de telefone reais (só os extremos do Playground: -25 dBFS -> 7 dB,
            -20 dBFS -> 2 dB); (2) a **TV** apareceu como fala quase contínua (94–99,6% nas janelas 4–8; viva-voz até 88%,
            silêncio até 50%) -> motivo novo **`fala_continua`** (>= 90% da janela, constante provisória
            `FALA_CONTINUA_PCT`); (3) os **"buracos" de 300–930 ms são pausas cortadas pelo próprio celular** (fala baixa e
            silêncio), não queda de rede: com `max_buracos_pct` 5 a 107 dispararia (falso positivo) e a 104 teve janela
            ruim; (4) a **compreensão** foi o sinal mais útil (106: 2 incidentes; 107: 1) — "Eso no es"/"Eso es" não eram
            marcados: `eso` (forte) e `es`/`no`/`un` (fracas) entraram na lista (25/25 offline). Recalculado com as regras
            atuais sobre os eventos gravados: 105 dispararia na janela 5 (`fala_continua`); 104, 106 e 107 não (com buracos
            em 10%); 106 dispararia pelo gatilho de compreensão (2º incidente).
            **Proposta de limites (fase 2; publicar só com o responsável)**: `snr_min_db` **15** (só pega extremos; margem
            sobre o mínimo real de 27,5), `janelas_seguidas` **2**, `max_buracos_pct` **10** (e considerar buraco só até
            ~250 ms — as quedas da seção 7.3 têm ~120 ms — antes de dar peso a ele), `max_incompreensoes` **2**,
            `fala_continua` >= 90% (tornar configurável se ficar). Amostra pequena (4 ligações, 1 aparelho, 1 operadora):
            juntar mais ligações reais em sombra (o `FORCAR=sombra` continua ligado na homologação) antes da fase 2.
          - [x] **6.7 Acabamento (26/09/2026)**: estado deixado na homologação — `voice-agent/.env` com
            `VOICE_WORKER_CARGA_FIXA=0` e `VOICE_QUALITY_GUARD_FORCAR=sombra` (toda ligação real é medida; tirar/comentar
            para parar); rascunho v2 (id 58) do agente 1 com `quality_guard=sombra`, SNR 12 e a regra "Ligação com
            dificuldade" — **não publicado**; v1 publicada intacta. Dados: as ligações 104–107 e seus eventos ficam (material
            de calibração); os testes de Playground só geraram buffer Redis (TTL 1 h) e nenhuma `voice_calls`; scripts de
            prova do backend rodaram em transação desfeita. Commit das telas (Playground + ficha): sysweb `b8325097`.
        - **Falta para a fase 2** (depois de mais ligações em sombra e com o responsável): (1) decidir os limites
          (proposta acima) e o que entra no gatilho — sugestão: compreensão + `fala_continua` + SNR só para extremos;
          buracos sem peso até separar queda de rede de pausa (limitar a ~250 ms ou cruzar com RTCP, item (g));
          (2) tornar `fala_continua` configurável se ficar; (3) implementar o modo `ativo` (item (c)): uma transferência
          por chamada, instrução injetada na sessão, motivo `qualidade_audio`/`compreensao` na ficha; (4) publicar a
          versão com a regra do prompt (e decidir incluir `agendar_callback`/`enviar_whatsapp` para o caso
          `sem_atendente`); (5) provar com uma ligação barulhenta transferida e uma silenciosa não;
          (6) em produção (Linux, jobs em processo), remover `VOICE_WORKER_CARGA_FIXA` e reavaliar a CPU por chamada.
      - [ ] **M4.5 (estudo, não é compromisso da V1) Canal de voz em banda larga pelo WhatsApp**. Registrado em 25/09/2026, a partir
        da pergunta sobre provedores com qualidade acima de 8 kHz:
        - **Conclusão da pesquisa**: provedor SIP com G.722/Opus existe, mas ligação para **celular/fixo comum** passa pela
          interconexão entre operadoras, que no Brasil é G.711 (8 kHz); trocar de provedor não muda isso. O HD Voice das
          operadoras (VoLTE, AMR-WB/EVS) só vale dentro da rede móvel, não chega pelo tronco SIP. Banda larga de ponta a ponta
          só existe quando a ligação **não passa pela rede de telefonia**: navegador (WebRTC, já usamos no Playground/atendente)
          ou app — em especial o **WhatsApp**.
        - **WhatsApp Business Calling API**: disponível no Brasil (GA desde 01/07/2025), ligações VoIP dentro do WhatsApp,
          sinalização por **SIP** ou Graph API; não liga para rede de telefonia comum. O RAPIA já tem a integração de mensagens
          com a Meta (templates, sessões) — é o caminho natural.
        - **A levantar antes de decidir**: codec e requisitos do SIP da Meta (TLS/SRTP, Opus?) e se o LiveKit SIP ou o Asterisk
          aceitam direto ou precisam transcodificar (perderia parte do ganho se cair para G.711); regras de ligação iniciada pela
          empresa (permissão do usuário para receber ligação); preço por minuto no Brasil; se a conta/número da Meta do cliente
          já está habilitada para chamadas. Ferramenta útil: o MCP de desenvolvedor da Meta disponível nesta máquina.
        - **Uso na demonstração**: botão "Ligar pelo WhatsApp" no fim do handoff do M4.2 ou paciente ligando pelo WhatsApp da
          clínica direto para a IA — mostraria a IA com áudio de qualidade de app, sem o 8 kHz.
- [x] **M4.1 Fila de retornos com oferta ao primeiro atendente disponível (lock atômico)** (`sysapi` + `sysweb`). Feito em 25/09/2026:
      - **Backend**: migration `2026_09_25_100000_alter_voice_callbacks_m4` (estados `calling` e `discarded`; colunas `reason`, `note`,
        `skipped_users`; rodada só no `ipsys-rapia`). `VoiceCallbackService` (cria, oferta, aceita, passa, expira, descarta, conclui,
        presença), `VoiceCallbacksController` (`/voice/callbacks/accept|pass|discard|complete`), `JobVoiceCallbackTick`,
        `board()` passa a devolver `retornos` reais (abertos: pending/offered/calling), config `voice.callbacks.*`
        (oferta 45 s, 3 tentativas, 10 min entre elas).
      - **Tool `agendar_callback`** (catálogo interno; params opcionais `telefone` e `observacao`; cria o retorno, deduplica por telefone,
        sandbox no Playground pelo `simulaInterna`, sem criar nada).
      - **"Sem atendente" (decisão do responsável, 25/09/2026)** = nenhum SUPER ativo com `voice_status = 1`. A `transferir_para_atendente`
        agora **não enfileira** nesse caso e devolve `{ok:false, motivo:'sem_atendente', orientacao}` para a IA oferecer retorno (ou
        WhatsApp, quando o M4.2 existir). Antes enfileirava sempre.
      - **Abandono na fila** (paciente desliga com a chamada em `queued`, via webhook) vira retorno automático (`reason='abandonada'`).
      - **Frontend**: aba Retornos de `V_ListaChamadas.vue` (cartões com contagem regressiva da oferta, "Ligar agora", "Passar",
        "Descartar"; em ligação: "Atendeu" / "Não atendeu"), toast ao receber oferta, `retornoAcao` em `painel360.js`.
      - **Provado**: (1) tinker + HTTP in-process no endpoint do worker: sem atendente devolve `sem_atendente` e a chamada segue `ai`,
        sem entrada de fila; com atendente enfileira; `agendar_callback` (inválido, ok, repetido -> `ja_existia`); (2) **corrida real**:
        3 processos php disputando a mesma oferta -> exatamente 1 `GANHOU`; (3) expiração da oferta pelo job real na fila redis
        (`skipped=[9]`, sem reoferta ao mesmo atendente, evento `callback_offer_expired`); (4) aceitar por quem não recebeu é negado;
        2 "não atendeu" -> `failed` no limite de tentativas; "atendeu" -> `done`; descartar; abandono na fila cria retorno; sem número
        de origem não cria; (5) sandbox do Playground (sala `pg-api_9_*`): tools respondem sem criar retorno nem chamada; (6) **no
        Chrome, logado pelo usuário** (`/voice/painel`): oferta chegou por Pusher com toast, cartão e contagem, "Ligar agora" ->
        "Em ligação", "Atendeu" fechou o retorno e ofereceu o seguinte automaticamente, "Descartar" limpou a lista.
      - **NÃO verificado**: a ligação de retorno em si ("Ligar agora" só aceita a oferta; a atendente liga por fora e registra o
        resultado, até o discador do M4.3 originar de verdade); o modelo de voz usando a tool nova em conversa real (nenhuma versão do
        agente 1 ganhou `agendar_callback`: ao publicar, habilitar a tool e ajustar o prompt para tratar `sem_atendente`); o layout de
        celular; mais de um atendente real (só existe o usuário 9 como SUPER; a corrida foi provada com ids fictícios).
      - **Detalhes técnicos**: (a) a oferta usa lock Redis `NX EX 10` **e** `UPDATE ... WHERE status='pending'` (o UPDATE é quem garante;
        o lock evita trabalho repetido). (b) O relógio é o job com atraso (`JobVoiceCallbackTick`, ações `expirar` e `ofertar`), sem
        cron; depende do `queue:work redis`. O worker local roda `--once --sleep=3` em laço, então um job com atraso de 3 s leva
        ~5–10 s e o broadcast também é fila: não testar expiração esperando pouco. (c) O webhook do LiveKit não grava `session`; o
        tenant do broadcast vem de `request()->attributes['voice_tenant']` (`VoiceCallbackService::tenant()`). (d) **Divergência do
        TODO**: não existe evento `voice.callback.available`; tudo sai por `VoiceCallUpdated` com `op = callback.created|offered|updated`.
        (e) Rodízio: quem passa/deixa expirar entra em `skipped_users`; ao voltar a Disponível (presença) sai da lista. Um único
        atendente que deixa expirar não recebe a mesma oferta de novo até mudar a presença. (f) Atendente ocupado (chamada `human` ou
        outro retorno oferecido/em ligação) não recebe oferta.
- [x] **M4.2 Handoff para WhatsApp: template + vínculo da sessão com a triagem** (`sysapi`; sem front). Feito em 25/09/2026:
      - **Migration** `2026_09_25_110000_add_whatsapp_handoff_voice` (só `ipsys-rapia`): `voice_calls.session_id` + parâmetros
        `VOICE/VOICE_WHATSAPP_TEMPLATE_ID` (= 3, "PACIENTE - Postos de coleta", `open_new_aviso_postos`, template de teste; o
        responsável criará um próprio) e `VOICE/VOICE_WHATSAPP_QUEUE_ID` (= 1). Editáveis em Parâmetros do Sistema, sem deploy.
      - **`VoiceWhatsappService`** + tool `enviar_whatsapp` (params opcionais `template` e `telefone`). Reaproveita
        `WhatsTemplateController` (Graph API da Meta): **sem sessão aberta para o número** -> `sendTemplateWhats` cria sessão nova,
        pendente na fila (chat em massa, sem atendente); **com sessão aberta** (procura as duas grafias do número, com e sem o 9º
        dígito) -> `renewTemplateWhats` nela, para não duplicar a conversa. Grava `voice_calls.session_id`, a triagem em
        `sessions_variables` (`VOICE_CALL_ID`, `VOICE_ROOM`, `VOICE_TRIAGE_NOME|CPF|NASC|EM`) e o evento `whatsapp_sent`/`whatsapp_failed`.
        Idempotente por chamada (segunda chamada devolve `ja_enviado`, sem enviar).
      - **Escolha do agente (decisão do responsável)**: template padrão pelo parâmetro; o agente pode informar `template` (nome, `name_meta`
        ou id). Só são elegíveis templates aprovados, **categoria utilitária (marketing fora)**, cabeçalho texto, **sem variáveis nem
        botões**. Hoje só 1 é elegível (o 3); o `mkt_001_sem_sem_vars` (marketing) fica de fora. Inválido devolve `opcoes`.
      - **Sandbox** no Playground: valida igual e responde `modo:'simulado'`, sem enviar nem criar nada.
      - **Provado**: erros (`template_invalido` com marketing, `telefone_invalido`, `sem_telefone`), sandbox (padrão, por nome, por
        `name_meta`, inválido), e **UM envio real autorizado** para 5584988345243 com `open_new_aviso_postos`, pelo endpoint da tool:
        resposta `ok`, `modo:'renovada'`, sessão **1521** (tipo B, aberta desde 17/09, conta legada `558488345243`), mensagem
        `is_template=S` gravada e a Meta reportou `delivered`; `voice_calls.session_id`=1521; triagem gravada nas variáveis; segunda
        chamada não reenviou. Depois do teste removi o registro de variáveis da 1521 (não existia antes) e a chamada de teste; a mensagem
        real ficou no histórico da sessão. **Rascunho de teste no agente 1** (`voice_agent_versions` id 56, nota "ZZ Teste M4"): as 4 tools
        + passo de encerramento reescrito para tratar `sem_atendente` (WhatsApp ou retorno); a versão 1 publicada ficou intacta.
      - **NÃO verificado**: o **caminho de sessão nova** com envio real (o número de teste já tinha sessão aberta; falta um número sem
        sessão ou fechar a 1521); a IA decidindo por voz (Playground só simula; ligação real bloqueada); o paciente respondendo no
        WhatsApp e a resposta caindo na sessão vinculada; se algum atendente enxerga as variáveis `VOICE_*` na tela do chat (nenhuma tela
        foi alterada); botão "Enviar p/ WhatsApp" da ficha (não feito); tratamento de erro da Meta no `renewTemplateWhats`, que referencia
        `$insert_mensagem` indefinido no catch (existente, não alterado: o serviço captura a exceção e devolve `falha_envio`).
      - **Detalhes técnicos**: (a) o contato 1 (JOAO SOUSA) está ligado à conta legada sem o 9, por isso a renovação; (b) o serviço
        chama os métodos do controller com `Request` sintético, como o `JobProcessManualCampaign` faz; `is_manual_campaign=true` evita o
        cache de sessões humanas com `user_id` 0; (c) o texto gravado da mensagem é o corpo do template (`body`).
- **Pronto quando:** o cenário "sem atendente → WhatsApp → retorno" roda inteiro.

### M5 — Acabamento de demonstração (6–8 dias)
Prompt de início da sessão (26/09/2026): `voip/PROMPT-INICIO-M5.md` — 6 pontos em sequência (detalhe de chamada encerrada
mantido aberto com selo "Encerrada", resumo/tags, gravação + player, custo, dashboard, massa de dados + ensaio), commit
único no fim. **Commitado em 27/09/2026: sysapi `6824809`, sysweb `2b2242ba`** (sem push). Pendente do M5: ensaio 3x +
vídeo de backup (responsável), restringir a credencial S3 (**adiado de propósito, decisão de 29/09/2026: não mexer nesta
fase do módulo; corrigir antes de piloto real**), decisão "paciente na URA no Painel". Próxima sessão (robustez da demo,
decisão "Na URA", ensaio): `voip/PROMPT-INICIO-M5.1.md`.
- **Ferramenta de teste (M5)**: `voice-agent/scripts/chamada_teste.py` = ligação "de verdade" sem telefone. Cria a sala
  `call-api_849990000NN_*` pela API do LiveKit (EC2), despacha o agente publicado (`AgentDispatchService/CreateDispatch`,
  `{"agent_id":1}`), entra como `teste_paciente` e fala o roteiro com o TTS local (falas do `playground_smoke.py`);
  `--segurar N` deixa a ligação aberta para olhar o Painel, `--cortar` apaga a sala direto (ligação que cai),
  `--remover SALA` apaga a chamada de teste. Webhooks, `voice_calls`, transcrições e `room_finished` são os reais.
  Não passa pela URA nem pelo filtro de entrada (são do Asterisk). Participante não é SIP nem `user_*`: a chamada fica
  `ai` até a sala acabar e termina `ended`.
- [x] **Resumo e tags automáticos no pós-chamada** (26/09/2026). A IA do chat (Copilot, `COPILOT_ROUTE`) é um agente
      Flowise/n8n com base de conhecimento: não serve para resumo estruturado. Usado o **Gemini por REST**
      (`gemini-3.8-flash`, `VOICE_SUMMARY_MODEL`; chave `VOICE_GEMINI_API_KEY` no `sysapi/.env`, a mesma do worker) com
      `responseSchema` (`resumo`, `tags[]` de lista fechada, `desfecho`). Migration `2026_09_26_100000_add_resumo_tags_voice_calls`
      (`tags` json, `summary_at`, `summary_meta` json: fonte ia|regra, modelo, desfecho, tokens, erro; `summary` já existia).
      `VoiceSummaryService` + `JobVoiceCallSummary` (fila, atraso `VOICE_SUMMARY_DELAY`=25 s para chegarem as últimas falas
      e o `audio_quality_summary`), disparado pelo evento `updated` do `VoiceCall` ao virar ended/abandoned/failed (cobre
      webhook, botão encerrar e discador; o `falha()` do discador usa update em massa e chama `VoiceCall::agendaResumo`).
      Sem falas: resumo por regra (desligou na fila, saída não atendida, atendida por humano) sem chamar a IA. Broadcast
      `call.summary` recarrega a ficha aberta. Reprocessar: `php artisan voice:resumo <ids> | --sem-resumo --tenant=api`.
      Tags e desfechos em `config/voice.php` (`resumo.tags`, `resumo.desfechos`); o modelo expõe `tags_rotulos` e
      `desfecho_rotulo`. **Achado no teste (chamada 109)**: a tag "transferido" saía da tool `transferir_para_atendente`
      mesmo com `sem_atendente`, e a IA marcava "retorno" só porque a orientação da tool oferecia retorno. Agora
      transferido/retorno/whatsapp/dificuldade_audio vêm **só dos eventos** (tool com `ok`, `human_at`/`queued_at`,
      callback criado, incompreensões >= 2 ou gatilho de áudio) e saem do `enum` da IA. O resumo não repete CPF nem
      nascimento. Exibição: ficha (bloco "Resumo da chamada", "Gerando resumo..." enquanto não chega), Histórico (coluna
      Resumo; clicar na linha abre a mesma ficha num modal, só leitura) e histórico do contato (resumo + tags junto do
      WhatsApp). Provas: 104–107 reprocessadas (106/107 com "Dificuldade de áudio"), todas as encerradas antigas geradas
      (`--sem-resumo`), 109 e 110 (chamadas de teste) com resumo automático pela fila; no Chrome, a ficha aberta recebeu o
      resumo ~25 s depois do fim, o Histórico mostrou coluna e modal, `contactHistory` do contato 1 trouxe resumo e tags.
- [x] **Gravação** (27/09/2026): Egress **na stack da EC2** (a 7.1 foi escrita para a local; adaptação registrada lá),
      bucket `rapia-files`, prefixo `voz/gravacoes/{tenant}/{yyyy}/{mm}/{sala}-{hhmmss}.ogg`, ciclo de vida de 90 dias
      no prefixo (regra criada pelo responsável; retenção definitiva ainda a decidir antes de piloto real).
      `VoiceRecordingService::inicia` pede `Egress/StartRoomCompositeEgress` (`audio_only`, `DEFAULT_MIXED`, `file_outputs`
      OGG **sem credencial no pedido**: vale o `storage.s3` da config do egress) no webhook `participant_joined` do
      paciente (SIP, ou `teste_paciente` da chamada de teste), síncrono (pela fila perderia a saudação); uma gravação por
      chamada; `VOICE_RECORDING_ENABLED` liga/desliga. Webhooks `egress_started/updated/ended` (trazem `egressInfo`, sem
      `room`; o `VoiceWebhookTenant` passou a ler `egressInfo.roomName`) -> `voice_recordings` (migration
      `2026_09_26_110000_alter_voice_recordings_m5`: `status`, `mixing`, `started_at`/`ended_at` com ms = início real do
      arquivo, base do player; `error`; unique `egress_id`) + eventos `recording_active/ended/failed` + broadcast
      `call.recording`. **Mixagem: mono (`DEFAULT_MIXED`)**: com `DUAL_CHANNEL_AGENT` o atendente humano cairia no mesmo
      canal do paciente (só o agente fica separado), então não ajuda; provado na ligação real 125 que a voz do atendente
      entra na gravação ("Alô, aqui é o atendente... Bom dia"). Arquivo: Opus 48 kHz 2 canais (cópia), ~14 KB/s.
      **CPU do egress (t3a.medium)**: chamada de teste de 2 min média 10% / pico 19% de um núcleo; ligação real 124
      média 4% / pico 9%, ~40 MB de RAM: o egress 1.14 grava áudio pelo SDK, sem Chrome (existe
      `sdk_audio_room_composite_cpu_cost`). Imagem de 4,7 GB. **Achados**: (1) no egress 1.14 o destino é `storage: {s3:}`;
      com `s3:` na raiz ele ignora e tenta gravar no disco ("Local upload failed: mkdir /voz"); (2) o ensaio com chave
      falsa provou pedido -> webhook -> `failed` com o erro do S3 (403) antes de existir credencial.
      **Credenciais (pendência de segurança)**: a proposta era dois usuários IAM (escrita só no egress, leitura só no
      Laravel), cada um só no prefixo. Conferido em 27/09 sem exibir valores: os dois `.env` têm a **mesma** chave, e ela
      escreve e apaga **fora** de `voz/gravacoes/` (arquivos de teste criados e apagados na hora). Funciona, mas precisa
      restringir a política antes de qualquer piloto.
- [x] **Player sincronizado** (27/09/2026): `V_PlayerGravacao.vue` na ficha (Painel e modal do Histórico), só com a
      chamada encerrada. URL assinada de 15 min (`POST /voice/calls/recording-url`, disco `voz_gravacoes` com
      `VOICE_S3_*`; rotas de voz já são só SUPER; o `s3_key` não vai ao navegador; se a URL expira, pede outra e volta ao
      ponto). Transcrição com o tempo de cada fala na gravação (`spoken_at` - `started_at`; `spoken_at` é o **fim** da fala,
      então a fala atual é a primeira cujo fim não passou), realce e rolagem automática, clique na fala ou no marcador pula
      o áudio. Marcadores: aviso de gravação, tools chamadas, transferência, atendente entrou, incompreensão. Download:
      mesma URL com `Content-Disposition: attachment`. Prova: chamada 113 (132 s, 1,8 MB); o trecho 57–63 s do arquivo,
      transcrito à parte pelo Gemini, é exatamente a fala realçada ("Obrigado. Por último... data de nascimento").
- [x] Aviso de gravação falado pela IA no início da chamada (já está no prompt) e
      registro do consentimento na linha do tempo: a 1ª fala da IA com "grava" vira o evento `recording_notice`
      (`VoiceWorkerController::transcript`), exibido na linha do tempo e como marcador do player.
- [x] Dashboard simples (27/09/2026): Voz > Dashboard (`/voice/dashboard`, SUPER, `DashboardVoz.vue`;
      `POST /voice/dashboard {data}`, `VoiceDashboardController`): chamadas do dia (entrada/saída, por status), TME
      (espera na fila até alguém assumir, `voice_queue_entries`), % resolvido pela IA (chamadas com fala da IA que
      terminaram sem fila nem atendente), duração média, custo estimado (soma e média) e, marcados "em teste", SNR mediano
      e incompreensões do M4.4. Sem gráfico (dashboard simples). Conferido no Chrome pelo menu.
- [x] **Painel 360: detalhe de chamada encerrada fica aberto sem aviso** (achado na ligação real de saída de 25/09/2026, EC2).
      Decidido: **manter a ficha aberta** com selo "Encerrada" (ou Abandonada/Falhou) e botão "Fechar" (limpa a seleção e a
      transcrição). Feito em 26/09/2026 (`V_FichaChamada`: `encerrada`, "Transcrição ao vivo" vira "Transcrição", prop
      `fechavel`; `Painel360`: `fecharFicha`; encerrar pelo softphone recarrega a ficha em vez de limpar). Ações (transferir)
      só existem com status `human`; o softphone só abre com `human` (ou saída tocando): nenhum dos dois volta.
      Prova no Chrome com a chamada de teste 110: selecionada "Com a IA" com transcrição ao vivo; ao fim o card saiu da lista,
      a ficha ficou com "Encerrada · 01:10", transcrição e o resumo chegou sozinho; "Fechar" voltou para "Selecione uma
      chamada". **Achado**: ao sair do Painel apareceu "Não foi possível alterar sua disponibilidade" e a presença ficou 1:
      o Apache do WAMP às vezes responde com a config do LiveKit vazia ("LIVEKIT_API_KEY/LIVEKIT_API_SECRET não
      configurados", no log desde 25/09, intermitente, com requisições simultâneas; provável `env()` não seguro entre threads
      no Apache do Windows; `config:cache` resolveria, mas quebra os `env()` fora de config do projeto). Paliativo:
      `definirPresenca` tenta de novo uma vez. Na demonstração, conferir a presença ao sair do Painel.
- [x] **Custo estimado — feito em 27/09/2026.** Worker: `session_usage_updated` (acumulado por modelo do
      `ModelUsageCollector`, alimentado pelo `usage_metadata` de cada resposta do Gemini) -> um evento `ai_usage` no
      shutdown (`modelos[]` com `input/output_*_tokens`, `respostas`, `sessao_s`). sysapi: migration
      `2026_09_27_100000_add_custo_ia_voice_calls` (`ai_usage` json com o detalhe, `ai_cost_usd`, `ai_cost_brl`);
      `VoiceCostService::recalcula` ao chegar o `ai_usage` e ao gerar o resumo (o resumo também é Gemini: entra como 2ª
      linha); sem `ai_usage` não mostra custo (chamadas anteriores ao M5). Preços em `config/voice.php` (`custo`),
      página oficial em 27/09: `gemini-3.8-live` US$ 0,75 texto / 3,00 áudio de entrada, 4,50 texto / 12,00 áudio de
      saída por 1M; `gemini-3.8-flash` 0,75 / 3,75 (sobe para 1,50 / 7,50 em 01/01/2027); cache cobrado como entrada
      normal (conservador); cotação `VOICE_CUSTO_COTACAO` (padrão 5,40). Exibição: Histórico (coluna "Custo IA (est.)"),
      ficha (linha com o detalhe no title) e dashboard. Números: teste 114 (2 min 14 s) US$ 0,074 = R$ 0,40; real 124
      (2 min 20 s) R$ 0,49 (conversa 0,476 + resumo 0,009). ~US$ 0,03/min, acima do ~0,023 da seção 9 porque o Live
      recobra o contexto (prompt + histórico) a cada turno. **Limitações medidas**: (1) ligação que cai no meio de uma
      resposta: o uso dessa resposta não chega (o Gemini manda `usage_metadata` no fim do turno; teste cortado aos 5 s,
      na saudação = 0 token): subestima até uma resposta; (2) o plugin descarta uso sem geração ativa ("received server
      content but no active generation"); (3) `thoughts_token_count` não é somado (importa só no extended-thinking).
      Comparação com o console do AI Studio: não feita (opcional, responsável).
- [x] **Custo estimado do Gemini por ligação, em R$** (pedido em 25/09/2026; a desenvolver num passo futuro, fora do E6).
      Base: o Gemini Live devolve `usage_metadata` (tokens de entrada e de saída, separados em áudio e texto, mais os
      em cache) e o livekit-agents 1.8.2 do worker já o expõe (`RealtimeModelMetrics` por resposta e `session.usage`
      acumulado); hoje o `agent.py` não captura nada disso e o banco não tem coluna/tabela de uso ou custo.
      - Worker: ao encerrar a ligação, ler `session.usage` e enviar ao RAPIA (tokens por tipo + modelo) junto do evento de fim.
      - sysapi: guardar o uso por ligação (em `voice_calls` ou tabela própria, com o modelo usado).
      - Cálculo: tokens x preço por 1 milhão de tokens (por tipo e por modelo) x cotação do dólar; preços e cotação ficam em
        `config/voice.php` ou parâmetro de tela, porque a API **não devolve valor em dinheiro**.
      - Exibição: "custo estimado" no Histórico de Chamadas, no detalhe da ligação e no dashboard acima.
      - **É estimativa**: pode divergir da fatura do Google (tabela de preços vigente e câmbio). **Cobre só o Gemini**;
        LiveKit, tronco SIP e gravação têm custos próprios (entrariam como outras linhas, se quiserem o custo total).
      - **Ainda não provado**: só se leu o código da biblioteca. Validar com uma conversa de teste, imprimindo o `session.usage`
        e comparando com o console do Google AI Studio (inclusive ligação que cai no meio: os tokens vêm completos?).
- [x] Massa de dados fictícia (27/09/2026): `voip/scripts/massa-demo.php --status | --criar | --remover` (script, não
      migration: migration rodaria em qualquer banco "rapia", inclusive de cliente). Cria os 5 pacientes do ERP Demo como
      contatos (`obs` = "[DEMO-M5] massa de demonstração") com conta de WhatsApp (`accounts.account_origem` = DEMO-M5),
      12 atendimentos de WhatsApp encerrados (`protocol` DEMO...) com mensagens, e 8 chamadas encerradas
      (`call-api_{numero}_DEMO{8}`) cobrindo resolvida pela IA, transferida e assumida (TME 38 s), WhatsApp, abandonada
      na fila, retorno combinado, saída feita pela IA; com transcrição, triagem, tools, aviso de gravação, qualidade,
      `ai_usage` proporcional ao da chamada 114 (payload `demo: true`) e resumo/tags gerados pelo serviço real.
      A agenda já vem do ERP Demo (datas relativas a hoje). As chamadas "de hoje" são do dia em que o script rodou:
      recriar (`--remover` + `--criar`) no dia do ensaio. Criada em 27/09 e mantida.
- [ ] Ensaio: roteiro escrito (`voip/ROTEIRO-APRESENTACAO.md`: checklist de uma hora antes, passo a passo das 7 partes
      da seção 11 com o que mostrar em cada tela, plano B e pós-apresentação) — **falta** o ensaio "três vezes seguidas"
      e o **vídeo de backup** (responsável).
- **Achados das ligações reais do M5 (124 e 125, 27/09/2026)**:
  - [x] **A IA continuava na ligação depois que a atendente assumia** (defeito do M2, não do M5): ninguém tirava o
        agente da sala; ele seguia ouvindo o paciente e falava por cima da atendente. Corrigido no worker: participante
        `user_*` entrou -> evento `ai_left`, `ctx.shutdown` (a sala continua, `delete_room_on_close` é False; os
        shutdown callbacks mandam o uso e o resumo de qualidade). Prova na 125: atendente entrou 13:30:13, `ai_left`
        13:30:13, agente saiu 13:30:14, a ligação seguiu com a atendente.
  - [x] **Na fila, a IA repetia os dados do paciente até alguém assumir.** Duas mudanças: o `transferir_para_atendente`
        aceito devolve `orientacao` ("uma frase curta pedindo para aguardar, não repita os dados, depois não fale mais")
        e o worker, depois dessa fala (`agent_state_changed` -> listening), chama `session.input.set_audio_enabled(False)`
        e registra `ai_waiting`. Sem atendente (`ok=false`) nada muda. Prova sem telefone (`chamada_teste.py --insistir 2`):
        depois do `ai_waiting` o paciente falou mais duas vezes e a IA não respondeu. Não reprovado em ligação real.
  - [x] `voice_calls.agent_id` ficava nulo nas ligações reais: o worker agora manda `ai_session` (agente, versão, modelo)
        no início e o backend grava o `agent_id`.
  - [x] **Resumo pós-chamada por agente** (pedido do responsável): chave versionada `resumo_pos_chamada` S/N em
        `VoiceAgentVersion::CAMPOS_CONFIG` (padrão S para versões sem a chave: nada muda sem publicar), validada, no
        Estúdio > Configurações da sessão ("Resumo pós-chamada (IA)") e na comparação de versões. `N`: não chama a IA
        (sem custo), `summary` nulo, `summary_meta.fonte` = desativado, tags por regra continuam; a ficha diz "Resumo
        automático desativado para este agente". Vale a versão que atendeu (`ai_session`). Prova em transação desfeita:
        "X" -> 422; "N" salvo -> resumo desativado na 124; rascunho v2 (id 58) intacto depois.
  - [x] (M5.1, ver abaixo) **Paciente na URA não aparece no Painel 360** (observação do responsável): enquanto está no menu do Asterisk
        não existe sala no LiveKit (ela só nasce depois do dígito), então nada chega ao RAPIA. Para mostrar "Na URA" seria
        preciso o dialplan avisar o RAPIA na entrada (já há `CURL()` do filtro de números nesse ponto), um status novo
        em `voice_calls` e casar esse registro com a sala criada depois (número + horário). **Decisão pendente.**
  - Transcrição do paciente pelo telefone ainda troca português por espanhol ("¿Qué?", "Sí. Sí.", "Eso es"): assunto
        do M4.4 (calibração em sombra), gerou `comprehension_miss` e a tag "Dificuldade de áudio" nas duas.
- **Pronto quando:** a sequência da seção 1 roda três vezes seguidas sem intervenção.

### M5.1 — Fechamento e robustez da demonstração (29/09/2026; prompt em `voip/PROMPT-INICIO-M5.1.md`)
Decisões do responsável (29/09): A4 = limite só com a IA na sala + aviso + transferir; B = "Na URA" versão enxuta;
A1 = correção no código (não trocar o PHP do Apache nem `config:cache`); A3 = rotação ao fim do bloco A.
- [x] **A1. Erro intermitente "LIVEKIT_API_KEY/LIVEKIT_API_SECRET não configurados" (Apache).** O log tem 54
      ocorrências (a 1ª em **24/09** 14:32, não 25/09; a última em 27/09), sempre em rajadas de requisições simultâneas.
      O vhost `api.ipsys` roda em **mod_php 7.4.33 ZTS** (o `fcgid_module` está carregado, mas o vhost não o usa). Reproduzido
      com carga paralela (`POST /api/voice/livekit/webhook`, 30 em paralelo): **4 respostas 500 em 900**. **O `env()` da requisição
      inteira vinha vazio**, não só o LiveKit (o log também mostra "connection: mysql", o banco caindo no padrão). Causa provável:
      o Laravel 8 escreve o `.env` com `putenv()` (ambiente do PROCESSO, comum às threads) e, com threads escrevendo/lendo
      ao mesmo tempo, o `env()` de uma requisição vem vazio. Correção: `\Illuminate\Support\Env::disablePutenv()` logo
      depois do autoload em `sysapi/public/index.php` (o `env()` passa a ler `$_ENV`/`$_SERVER`, por thread); nada no
      projeto usa `getenv()`. Depois: **0 respostas 500 em 1.800** (2 rodadas de 900). `config:cache` continua descartado
      (275 `env()` em 80 arquivos, inclusive fora de `config/`). É evidência estatística (0,4% antes), não prova formal: se o
      erro voltar, o `laravel.log` mostra. O paliativo do front (`definirPresenca` tenta de novo) foi mantido.
- [x] **A2 (preparo). Transcrição do paciente em espanhol.** Achado no código instalado: o `livekit-plugins-google`
      1.8.2 usa `AudioTranscriptionConfig()` **vazio** (detecção automática de idioma da transcrição de entrada), e o
      `google-genai` aceita nesse objeto `language_codes` (dica BCP-47), `custom_vocabulary` (viés do ASR), `mode`
      (VERBATIM/SMART) e outros. O `language` do `RealtimeModel` só vai para o `speech_config` (voz de saída). Novas
      variáveis do worker (`agent.py`, `transcricao_entrada_kwargs`): `VOICE_TRANSCRICAO_IDIOMAS` (ex.: `pt-BR`) e
      `VOICE_TRANSCRICAO_VOCAB` (frases separadas por `|`); sem variável nada muda. **Não provado em ligação real**: só o
      telefone reproduz (o paciente sintético usa TTS limpo). Experimento proposto (mesmo roteiro, uma variável por vez):
      (1) controle sem variável, (2) `VOICE_TRANSCRICAO_IDIOMAS=pt-BR`, (3) `pt-BR` + vocabulário; medir
      `comprehension_miss` e conferir a transcrição. **Pendente: ligações do responsável.**
- [x] **A4. `max_call_seconds` em ligação real.** Achado: o Playground usa uma constante do backend
      (`VoicePlaygroundController::MAX_SEGUNDOS`); o `max_call_seconds` da versão chegava ao worker no runtime e **nunca era
      usado**. Agora (`agent.py`, `_limite_da_ligacao`), só em ligação real e só enquanto a IA está na sala (o job acaba quando a
      atendente assume): aviso falado `VOICE_LIMITE_AVISO_S` (60 s) antes, no limite `transferir_para_atendente`; aceita ->
      a IA pede para aguardar e fica muda (mesmo caminho do `ai_waiting`); sem atendente -> se despede e `ctx.delete_room()`
      (o `room_finished` real encerra a chamada). Eventos `ai_limite_tempo` (fase aviso/transferida/encerrada). Fala com tempo
      máximo (`_fala_limitada`, 15 s): o 2º teste mostrou que um `generate_reply` interrompido nunca resolve e travava o prazo.
      Prazo total contado desde o início da sessão. Provado sem telefone com `VOICE_MAX_CALL_SECONDS_FORCAR=70` (só homologação,
      variável de ambiente do worker; **não** deixar no `.env`): chamadas 127 (sem atendente: aviso 35 s, recusada, despedida,
      sala encerrada, `ai_usage` gravado) e o caminho com atendente Disponível (transferência aceita, `ai_waiting` equivalente). Limitações: o resumo
      automático pode dizer "encaminhada" mesmo quando a transferência foi recusada (a IA lê a fala do aviso); o custo do
      aviso entra normalmente no `ai_usage`.
- [x] **B. "Na URA" no Painel 360 (versão enxuta).** Migration `2026_09_29_100000_add_status_ivr_voice_calls` (enum `ivr`; rodada
      só no `ipsys-rapia` com `migrate --path`). Dialplan (`livekit-ec2/templates/asterisk/extensions.conf.tmpl`, publicado na
      EC2 + `render-config.sh` + `dialplan reload` em 29/09): em `[ura-menu]`, logo após o `Answer()`, `CURL()` para
      `GET /voice/ura/entrada?uid=${UNIQUEID}&from=&did=` (resposta ignorada, mesmos timeouts curtos) e extensão `h` chama
      `/voice/ura/saida?uid=`. Backend (`VoiceUraRuntimeController::entrada/saida`, mesmo `x-api-key`): `entrada` cria
      `voice_calls` `ivr` com `room_name` provisório `ura_{uniqueid}` e avisa o Painel; a sala que nasce depois do dígito
      **adota** a linha (`VoiceWebhookController::garanteChamada` -> `VoiceCall::uraDoNumero`: mesmo número, últimos 11
      dígitos, `JANELA_URA_S`=120) e mantém o horário em que o paciente ligou; `saida` com a linha ainda `ivr` = abandonada
      **sem retorno automático e sem IA** (`abandonaNaUra`: update em massa, resumo por regra, desfecho `abandonou_ura` em
      `config voice.resumo.desfechos_regra`, fora do enum da IA); `ivr` esquecida expira em `EXPIRA_URA_S`=180 (na entrada/no
      `board`). O Painel lista `ivr` em "Em curso" com o selo "Na URA" (lista, ficha, histórico, dashboard). Provado pelo HTTP
      real: entrada -> `ivr`; saída -> abandonada (2 s, resumo por regra); adoção pela sala da chamada de teste (mesma
      linha, sem duplicar); expiração. **Ainda não provado com telefone** (o `CURL()` no Asterisk real e o `h`): é a ligação do bloco C. Cuidados:
      o `CURL()` acrescenta uma ida ao ngrok antes do áudio do menu (medir na ligação real); o card "Na URA" não some sozinho
      no front se o Asterisk não avisar o fim (some na próxima recarga do board, no máx. após 3 min).
- [x] Melhoria: `chamada_teste.py --remover` apaga também o arquivo da gravação no S3.
- [ ] **A3. Rotação de segredos.** Autorizada (ao fim do bloco A), **bloqueada** pela ferramenta de permissões na etapa
      de localizar o valor atual do token (gravá-lo num arquivo para procurar cópias); nada foi rotacionado. Alvos: `VOICE_WORKER_TOKEN`
      (`sys_parametros`), `RAPIA_API_TOKEN` (`voice-agent/.env`) e `URA_API_TOKEN` (`.env` da EC2 + render + `dialplan reload`);
      a chave do Gemini (AI Studio) é do responsável. Ver a resposta da sessão para as opções.
- [ ] **C. Provas do responsável**: ligações do experimento A2; ligação de fila (IA calada até assumir e sai ao assumir);
      "Na URA" e desligar no menu com telefone; ensaio 3x e vídeo de backup (`ROTEIRO-APRESENTACAO.md`, atualizado).
- **Provas do responsável (05/10/2026, chamadas 133–139):**
  - A2: 133 (controle) com "cárie balão dentes" e erro `generate_reply timed out waiting for generation_created` (saudação
    ~20 s depois do `ai_session`, latência do Gemini no 1º turno; o timeout de 5 s é fixo no plugin); 134 e 135 (pt-BR, depois
    pt-BR + vocabulário) sem `comprehension_miss`; 136 (variáveis ativas) ainda teve um "¿Qué?" (`espanhol`). Amostra pequena,
    tendência favorável: variáveis mantidas no `.env`; sem `VOICE_TRANSCRICAO_IDIOMAS` o worker agora usa o `language` do agente (Estúdio).
  - Fila (136): IA calou e saiu ao assumir (ok). **Achado de produto**: pediu os dados antes de transferir porque a versão 1 publicada
    tem o prompt de teste ("coletar 3 dados e depois transferir"): a regra é do prompt do agente (Estúdio), não do código.
  - "Na URA" (137, 138): ok (card sumiu ao desligar, sem duplicar, áudio do menu imediato).
  - Limite (139, `FORCAR=20`): transferiu, mas **o paciente ficou no mudo**: `_estado` silenciava no primeiro `listening` depois de
    `transferida=True` e a frase do limite se perdia (aviso e fala final não aparecem na transcrição). Corrigido no worker
    (`agent.py`): frases com `allow_interruptions=False`, `interrupt()` antes, nova tentativa se interrompida, texto "o tempo do
    autoatendimento terminou, você será direcionado a um atendente" e só silencia **depois** da fala. **Não reprovado em ligação.**
    O tempo máximo por agente já existe no Estúdio (Configurações da sessão > "Tempo máx. (s)", mín. 30 s, vale após publicar);
    `VOICE_MAX_CALL_SECONDS_FORCAR` só sobrepõe para teste.
  - Painel 360: cabeçalho da ficha (selo "Encerrada" + Fechar) agora é `sticky` no scroll da coluna central (`V_FichaChamada.vue`).
  - **Chamada 141/143 (limite de tempo, 05/10/2026):** 141 repetiu a mensagem 3-4x (o aviso prometia a transferência e o modelo
    chamou `transferir_para_atendente` por conta própria); **143: IA muda perto do limite e, no encerramento, LEU TRECHOS DO PRÓPRIO
    PROMPT em voz alta** (inaceitável). Causa: no Gemini Live `generate_reply(instructions=...)` envia o texto como turno de modelo +
    "." de usuário; no meio da conversa o modelo ignora (mudo) ou recita o prompt. Correção no worker: o aviso e as despedidas do limite
    agora são **frases fixas pré-sintetizadas** (`frases_fixas.py`, sessão Live separada só de leitura, voz do agente, cache em
    `cache_frases/`) tocadas com `session.say(audio=...)`, **sem LLM no caminho**; sem áudio pronto o worker não fala (prefere o
    silêncio a pedir ao modelo); e `REGRA_SIGILO` é anexada a todo prompt. Síntese das 3 frases testada (voz Leda, 6-11 s cada);
    **ligação real ainda não provada** (reiniciar o worker). Defesa que NÃO existe e fica como risco aberto: detector de vazamento de
    prompt na fala da IA em conversas normais (interromper se a transcrição repetir trechos do prompt).
  - **Chamada 144 (limite 30 s, frases fixas):** as frases já eram as gravadas, mas (1) o aviso caiu no meio do nome do paciente
    (interrompeu a escuta; o nome saiu "Parque Barigui") e (2) a despedida foi **cortada em "O tempo do"** e a ligação caiu:
    `session.say(audio=...)` não é blindado (com detecção de turno no servidor o `allow_interruptions=False` é ignorado) e o código
    seguia para `delete_room` mesmo com a fala interrompida; o resultado foi `sem_atendente` (nenhum SUPER com `voice_status=1` naquele
    instante), caminho que desliga por desenho. Correções (`agent.py`): `_espera_vaga` (só toca com o paciente calado e a IA sem falar,
    até 12 s para o aviso e 3 s para as frases finais); `_fala_fixa` toca **direto na saída de áudio** da sessão
    (`session.output.audio.capture_frame/flush/wait_for_playout`), com a IA calada (interrupt + entrada de áudio desligada) enquanto
    toca e reabrindo a entrada depois (no aviso); despedida só desliga 1,5 s depois do fim do áudio; no caminho sem atendente agora
    **agenda o retorno de verdade** (`agendar_callback`), já que a frase promete retorno. **Não provado em ligação** (reiniciar o worker).
  - **Chamadas 145 (com atendente) e 146 (sem atendente), limite 30 s:** frases fixas tocaram inteiras; transferência/despedida e retorno
    agendado (callback 34) corretos. **Defeito restante:** depois do AVISO (antes do limite) a IA pedia de novo o que o paciente já
    dissera ("Eu falei meu nome"): o aviso corta a vez da IA e ela perde o fio. Decisão: **aviso desligado por padrão**
    (`VOICE_LIMITE_AVISO_S=0`; >0 reativa para experimento); a frase de transferência/despedida no limite continua sempre falada.
    Presença: o foco/minimizar do navegador não altera o status; só entrar (Disponível), sair do Painel e `pagehide` (Indisponível).
    Risco conhecido: sem heartbeat/TTL, aba congelada ou navegador encerrado à força deixa o status Disponível.
- [x] **Heartbeat de presença do atendente (aprovado e implementado em 05/10/2026, TTL 150 s; commitado: sysapi e sysweb, ver git log)** — texto da proposta abaixo; implementação: sysapi `VoicePresenceService`, `POST /voice/presence/ping`, `presence` apaga/renova o sinal, `usuariosVoz()` exige sinal vivo, `liberaOfertasSemSinal()`, `config voice.presenca.ttl` (`VOICE_PRESENCA_TTL`, 0 desliga); sysweb `Painel360.vue` (ping a cada 20 s por Web Worker, ao voltar o foco, aviso "Sem conexão" após 3 falhas, equipe no cabeçalho com selo vermelho SEM SINAL) e `painel360.js` (`pingPresenca`). Provado no serviço com Redis e banco reais (sem sinal -> sem_atendente; ping -> disponível; expira após o TTL; TTL 0 desliga; Indisponível apaga o sinal). **Falta provar no navegador e com fechamento forçado da aba.** Tela do supervisor = a equipe no cabeçalho do Painel 360 (todo SUPER ativo, estado efetivo). Proposta original: `users.voice_status` é só a
      preferência (1/2); a disponibilidade EFETIVA passa a exigir também um sinal recente da aba do Painel 360.
      (1) Front: `Painel360` envia `POST /voice/presence/ping` a cada 20 s enquanto montado (ping imediato ao abrir e ao voltar a
      foco); falha seguida de 3 pings mostra "Sem conexão com o servidor" no cabeçalho; ping que volta com `expired:true` reafirma a
      preferência. (2) Sysapi: chave Redis `voice:presenca:{tenant}:{user}` com TTL `VOICE_PRESENCA_TTL` (padrão 150 s; sem migration);
      `usuariosVoz()` (base de `haAtendenteDisponivel`/`atendentesDisponiveis`) filtra `voice_status=1` E chave viva; `ofereceProximo`
      devolve a oferta de quem perdeu o sinal; ping de quem está em `voice_status=2` não reabilita. TTL 0 = recurso desligado (compatibilidade
      até o front novo subir em todos os tenants). (3) Cuidado de navegador: aba oculta por mais de 5 min tem timers limitados a ~1/min
      (Chrome) e abas podem ser congeladas; por isso o TTL é 150 s e o ping sai de um Web Worker. Pusher/Ably não serve como fonte de
      presença (o `laravel-websockets` está desativado). (4) Provas: ping vivo -> transferência aceita; fechar a aba à força
      (Gerenciador de Tarefas) -> em até 150 s a transferência vira `sem_atendente`; aba em segundo plano 10 min continua válida.
      Estimativa 0,5 a 1 dia. Decisões do responsável: TTL, e se "sem sinal" aparece como estado visível para o supervisor.
  - **Chamadas 147 (com atendente) e 148 (sem), 05/10/2026, celular em viva-voz:** a IA repetia o início do prompt (saudação) várias vezes
    até a ligação ser transferida (147) ou até o paciente sair do viva-voz (148). Causa provável: `START_SENSITIVITY=HIGH` + ruído da sala/eco
    do viva-voz disparam turnos; como a instrução da saudação continua sendo o último turno do modelo, cada "turno" de ruído a repete.
    Medição (ai_session -> 1ª fala da IA, calls 133-148): 3 a 20 s (mediana ~10 s), a maior parte é a geração da saudação no Gemini
    (timeout fixo de 5 s do plugin). Mudanças (`agent.py`, `.env`): (1) `VOICE_START_SENSITIVITY=LOW` (antes HIGH); (2) **saudação
    protegida**: entrada de áudio desligada enquanto a saudação toca (reabre no fim, máx. 45 s); (3) **"Aguarde um instante, por favor"**
    pré-sintetizado (`frases_fixas.py`, cache) tocado direto na saída de áudio se a IA não começar a falar em 1,5 s
    (`VOICE_ESPERA_FALADA_S`; 0 toca já, negativo desliga), parando assim que a IA começa; evento `ai_espera_falada`.
    Provas sem telefone com um worker de teste à parte (`AGENT_NAME=rapia-voice-claude` + `CHAMADA_TESTE_AGENT_NAME`): saudação normal
    (3 falas) em 2 chamadas; filler forçado (`VOICE_ESPERA_FALADA_S=0`) tocou 29 quadros e a IA falou em seguida (log benigno
    "capture_frame called while flush is in progress" na troca). **Não provado em ligação real/viva-voz.** Limite do filler: ele só cobre a
    espera DEPOIS que o agente entrou na sala; o tempo até o agente entrar (webhook/despacho) não é coberto.
  - **Chamada 152 (05/10/2026):** resultado "muito bom" (sem repetição da saudação; em viva-voz foi preciso falar mais alto com
    `START_SENSITIVITY=LOW`: é o preço do ajuste, reavaliar com aparelho real fora do viva-voz).
  - **Música de espera (pedido do responsável, 05/10/2026):** paciente na fila com a IA calada ouve instrumental até a atendente assumir.
    `musica_espera.py`: faixa de `voice-agent/audio/espera.wav` (WAV PCM 16 bits, sua, com direito de uso) ou, sem ela, uma faixa GERADA
    (pad suave Am-F-C-G, 24 s, sem direitos autorais; salva em `audio/espera_gerada.wav`), em laço, baixa (`VOICE_MUSICA_ESPERA_GANHO`,
    padrão 0,2; `VOICE_MUSICA_ESPERA=0` desliga), tocada direto na saída de áudio da sessão como as frases fixas; começa quando o agente
    fica mudo (transferência aceita, pela IA ou pelo limite de tempo) e para quando a atendente entra (o job acaba). Evento `ai_musica_espera`.
    Provado sem telefone (worker de teste à parte + `chamada_teste.py`): música iniciou na fila e a chamada correu sem erros; **o som em si
    não foi ouvido por mim** (conferir o volume e o gosto em ligação real). A gravação (egress) inclui a música. Fora do escopo: música
    antes do agente entrar na sala e retornos/saída.
  - **Atenção:** `voice-agent/.env` está com `VOICE_MAX_CALL_SECONDS_FORCAR=30` (teste do limite): comentar antes de uso normal.
  - **Chamada 154 (05/10/2026):** música/espera ok; defeito: o "Aguarde um instante" ainda tocava quando a voz do Gemini começou e
    as duas se sobrepunham. Causa: o filler escrevia na saída de áudio até ~1 s à frente do relógio e só parava quando
    `agent_state` virava "speaking" (que só muda quando o áudio do modelo TOCA, depois do que já estava na fila), então os quadros dos
    dois eram intercalados. Correção: `_vigia_audio_do_modelo` envolve `capture_frame` da saída da sessão e marca o instante em que o
    MODELO escreve o 1º quadro (contextvar `_audio_nosso` separa o que é nosso); o filler escreve no ritmo do relógio (no máx. ~0,15 s à
    frente), PARA nesse instante e não faz flush. Prova sem telefone (worker de teste, `VOICE_ESPERA_FALADA_S=0`, 4 chamadas): as 4
    foram cortadas pelo modelo com 14 a 17 quadros e sem o erro de flush; evento `ai_espera_falada.cortada_pelo_modelo`. **Resíduo
    possível:** até ~0,15 s do filler antes da voz da IA (sequencial, não sobreposto). Reprovar em ligação real.
- Ambiente: neste dia o PC estava sem ngrok, `php -S`, fila e sysweb; sem ngrok o LiveKit não entrega webhook e a ligação
  não vira `voice_calls` (o teste "sumia"). Conferir o item 4 do checklist antes de qualquer teste.

**Total estimado: 36 a 50 dias úteis de desenvolvimento** (27–38 originais +
9–12 do M2.5, que não tinha entrado na análise original).

Com o modelo de trabalho escolhido (eu escrevo o grosso, você revisa e testa),
o plano original cabia em 6 semanas até 01/11/2026. **Com o M2.5, a data-alvo
fica em risco** — dá cerca de 2 semanas a mais, empurrando pra
meados/fim de novembro se nada mais escorregar:

| Semana | Período | Entrega |
|---|---|---|
| 1 | 22–26/09 | M0 — fundação, migrations, rotas, menu SUPER, API do ERP levantada |
| 2 | 29/09–03/10 | M1 — IA conectada ao RAPIA, adapter do ERP real |
| 3 | 06–10/10 | M2 — Painel 360 (concluído em 23/09, adiantado) |
| 4 | 13–17/10 | 🆕 M2.5 (parte 1) — URA no Asterisk, cadastro de troncos/fila padrão |
| 5 | 20–24/10 | 🆕 M2.5 (parte 2) — ramais SIP, bridge pro LiveKit, presença do atendente |
| 6 | 27–31/10 | M3 — Estúdio do Agente com as duas abas |
| 7 | 03–07/11 | M4 — discador, retornos, WhatsApp |
| 8 | 10–14/11 | M5 — gravação, dashboard, ensaio |

Folga real: nenhuma. Se algo escorregar, o corte na ordem é: player de gravação →
aba de visualização do fluxo → discador manual → (dentro do M2.5) bridge de
ramal pro LiveKit vira ramal físico simples (opção B que não foi escolhida,
mas fica como plano B de escopo se o prazo apertar).

**Recomendação:** decidir com o cliente/stakeholder se a data de 01/11 é fixa
(e aí o M2.5 encolhe ou sai da V1 de apresentação, voltando pra seção 8) ou se
pode deslizar ~2 semanas.

### 7.1 Egress (gravação) na stack local — modo somente áudio

> **Adaptação feita no M5 (27/09/2026): o egress roda na stack da EC2** (`voip/livekit-ec2`), não na
> `livekit-local`. Serviço `egress` no `docker-compose.yml` com `network_mode: host` (não há rede `voz` nem IP
> `172.30.0.14`), perfil `gravacao` (`COMPOSE_PROFILES=gravacao` no `.env` da EC2), `cap_add: SYS_ADMIN`, config em
> `/etc/egress.yaml` via `EGRESS_CONFIG_FILE`, health em `127.0.0.1:8082` (nada a abrir no Security Group). Template
> `extras/egress.yaml.tmpl`, gerado pelo `render-config.sh` só quando `S3_BUCKET` está preenchido (valida
> `S3_REGION/S3_ACCESS_KEY/S3_SECRET`); `.env.example` com as variáveis novas. Depois de mudar a config:
> `docker compose restart egress` (o `up -d` não recria). O restante desta seção vale como descrito; o que mudou na
> implementação está no bloco M5 (destino em `storage.s3`, credencial fora do pedido, mixagem mono, CPU medida).

O **Egress** é o serviço do LiveKit que grava a chamada: um container que entra na
sala como participante invisível, mistura o áudio e envia o arquivo final ao S3.
Decisão: **reaproveitar o bucket atual (`rapia-files`) com o prefixo
`voz/gravacoes/`**, migrando para bucket dedicado quando sair da fase de demo.

**Por que somente áudio:** o modo *room composite* com vídeo sobe um Chrome
headless e custa cerca de 3,0 CPU por gravação; com `audio_only` custa 0,5–1,0 CPU.
Ligação telefônica não tem vídeo, e a máquina local também roda Docker, Laravel,
Vue e o worker durante a demonstração.

**Tarefas**
- [x] (na EC2, ver a nota acima) Serviço `egress` em `voip/livekit-local/docker-compose.yml`, na rede `voz`
      (IP fixo `172.30.0.14`), sem portas publicadas, com `cap_add: SYS_ADMIN` e a
      config montada em `/etc/egress.yaml` (nome do arquivo e variável a conferir
      na imagem, como ocorreu com o SIP)
- [x] (EC2: `extras/egress.yaml.tmpl`, `ws://127.0.0.1:7880`, destino em `storage.s3`) Template `templates/egress.yaml.tmpl` com `api_key`/`api_secret`, `ws_url:
      ws://livekit:7880`, `redis` (mesmo do LiveKit) e `insecure: true`
- [x] (EC2: `render-config.sh`, sem `S3_PREFIX`: o prefixo vem do Laravel) Variáveis no `.env.example`: `S3_BUCKET`, `S3_REGION`, `S3_PREFIX`,
      `S3_ACCESS_KEY`, `S3_SECRET`; `render-config.ps1` passa a validá-las
- [ ] **Parcial**: criado usuário IAM, mas a mesma chave está no egress e no Laravel e não é restrita ao prefixo (ver M5). Credenciais S3: **usuário IAM dedicado com política restrita** a
      `s3:PutObject` em `rapia-files/voz/gravacoes/*` (e `GetObject`/`ListBucket`
      só para o Laravel). Evitar copiar a chave de uso geral do `sysapi/.env`
- [x] (no `participant_joined` do paciente; sem `S3Upload` no pedido) Laravel: `VoiceRecordingService` chama `StartRoomCompositeEgress` na abertura
      da sala com `audio_only=true`, `EncodedFileOutput` em **OGG** (menor e nativo
      do Opus), `filepath = voz/gravacoes/{tenant}/{yyyy}/{mm}/{room_name}-{time}`
      e `S3Upload` com bucket/região
- [x] (decidido: mono, ver M5) Mixagem: avaliar `audio_mixing = DUAL_CHANNEL_AGENT` (canais separados)
      **versus** mono padrão. Testar a troca IA → atendente humano dentro da mesma
      gravação antes de decidir, porque a atribuição de canal muda nesse momento
- [x] Webhook `egress_ended` grava caminho, duração e tamanho em `voice_recordings`
- [x] Player usa **URL assinada** (mesma técnica do `TESTE_PRESIGNED_URL.md` do
      projeto); o arquivo nunca fica público
- [x] (EC2: média 4%, pico 9% numa ligação real) Teste de carga leve: uma chamada gravada com a demo inteira rodando, medindo
      CPU do container `egress`

**Observação de segurança/LGPD:** gravação de ligação de paciente é dado sensível.
Aviso falado no início da chamada é obrigatório, a retenção precisa ser definida
antes de qualquer piloto real, e o acesso ao player fica restrito a SUPER na V1.

### 7.2 URLs e multi-tenant (regra do `loadConfig()` do sysweb)

| | Local (V1) | Produção |
|---|---|---|
| Backend / frontend / worker | **Fixo:** `http://api.ipsys/api` | `https://{tenant}.api.{dominio}/api` |
| Tenant | subdomínio `api` (o `CheckSubDomain` já resolve) | 1º rótulo do host (o `CheckSubDomain` já resolve) |
| Webhook do LiveKit | `http://api.ipsys/api/voice/livekit/webhook` | host único `voice.api.{dominio}`; tenant pelo **nome da sala** |
| Nome da sala | `call-api_{numero}_{aleatorio}` | `call-{tenant}_{numero}_{aleatorio}` |
| WS do LiveKit p/ o navegador | vem do backend (`/voice/token`) | idem |
| Modo | `VOICE_TENANT_MODE=fixed` (padrão) | `VOICE_TENANT_MODE=room` |

**Por que o webhook é o único caso especial:** o LiveKit tem uma lista única de URLs
e envia cada evento para todas. Uma URL por tenant vazaria evento entre clientes.
Frontend e worker, ao contrário, chamam o host do tenant e usam o fluxo normal.

**Feito:** `extra_hosts: api.ipsys:host-gateway` no serviço `livekit` da stack local
(testado: o container alcança o Apache do WAMP). **A fazer no M0:** rota do webhook,
middleware de resolução por sala (modo `room`, desligado localmente), chaves
`VOICE_TENANT_MODE`, `RAPIA_API_URL` e `RAPIA_API_URL_TEMPLATE`.

**Formato da sala (confirmado em ligações reais):** `{roomPrefix}_{numero}_{12 aleatórios}`,
com `roomPrefix = call-{tenant}`. Exemplos: `call-api_84988345243_N845UuDPHnQG` e,
sem número, `call-api_anonymous_DkbK6GuexzVh`. O número no nome da sala vem em
formato nacional (sem +55) e pode ser `anonymous`; o telefone confiável está no
atributo `sip.phoneNumber` do participante SIP. Parser:
`/^call-([a-z0-9]+)_([^_]*)_([A-Za-z0-9]+)$/`.

**Tenant:** subdomínios só têm letras e números (sem `_` nem `-`), então `_` é um
delimitador seguro. Sem pendências nesta seção.

### 7.3 Ambiente de homologação (EC2) — no ar desde 25/09/2026

Criado para tirar o NAT do Docker Desktop do caminho (achado do M2.5) e destravar
ligações reais de entrada, URA e saída. Roteiro original: `voip/PROMPT-EC2-HOMOLOGACAO.md`.

| Item | Valor |
|---|---|
| Instância | `sa-east-1`, Ubuntu 24.04, t3a.medium, gp3; IP privado `172.31.11.133`, Elastic IP `54.20.82.110` |
| Acesso | `ssh -i ~/.ssh/srv_ipsys_web_sp ubuntu@172.31.11.133` (pela OpenVPN; chave convertida do `SRV_IPSYS_WEB_SP.ppk`, fica só no PC) |
| Stack | `~/livekit-ec2` = pacote `voip/livekit-ec2/` (redis, livekit, sip, asterisk; todos `network_mode: host`) |
| Na EC2 | LiveKit Server, LiveKit SIP, Redis, Asterisk (registrado na sobreip) |
| No PC | sysweb, sysapi (`php -S 127.0.0.1:8000`), worker de IA, `queue:listen`, ngrok `apiflowip.ngrok.app` -> `localhost:8000` |
| PC -> EC2 | OpenVPN (UDP); a EC2 vê a origem `172.31.34.163`; RTT ~64 ms. `NODE_IP` do LiveKit = IP privado |
| EC2 -> PC | ngrok: webhook do LiveKit e `CURL()` do dialplan (URA e filtro de números) |
| Security Group | 5060 + RTP 20000-20099/udp só para os IPs do provedor; o IP público do usuário tem tudo liberado; 7880/7881/7882 alcançáveis pela VPN. Não abrir 5080, 6379, 5038, 8081, 10000-19999 (loopback / uso interno) |

Trunks e regras (criados por `scripts/provisiona-sip.sh`, a partir de `sip/*.json`):
IA `+558431901994` ST_Qpxx2umwBfYQ / SDR_bFYvyXkft6wM (`call-api_*` + `rapia-voice`, agent_id 1);
fila direta `9990101` ST_QCvwr8AbZxoE / SDR_yd6hBpGZijHM; fila padrão `9990102` ST_CBCpFzoqBT9N /
SDR_NEeYmQbS8Vpz; ramais ST_tF35tMWyr7jx / SDR_NPEm5E6QUHf5; saída ST_EkKWGzGVyyFj (`127.0.0.1:5060`).

**Provas (25/09/2026)**: 4 serviços `running`, `Registered`, health do SIP OK; do PC, `curl` na 7880
pela VPN OK; Playground do Estúdio com fala nos dois sentidos (usuário); webhook pelo ngrok com
assinatura válida (`room_started`/`room_finished`, sala `pg-*`); worker registrado no LiveKit remoto;
ligação real de entrada direto para a IA (chamada 40, ~2.000 pacotes RTP em cada sentido, 7 falas);
URA (ver M2.5); saída pelo trunk para o celular do usuário com caller ID = DID
(`lk sip participant create` + `lk dispatch create` com o agente; chamada 45, ~1.800/1.600 pacotes).

**Arquivos locais apontados para a EC2** (backups em `voip/backup-env-pre-ec2/`): `sysapi/.env`
(`LIVEKIT_URL`, `LIVEKIT_WS_URL`, key/secret) e `voip/voice-agent/.env` (`LIVEKIT_URL`, key/secret).
A stack `voip/livekit-local` está **parada** (`docker compose stop`). **Não rodar `voip/iniciar.ps1`**
enquanto a EC2 estiver em uso: ele sobe o Asterisk local (a conta aceita UM registro) e roda o
`dispatch.py` contra `localhost`.

**Subir / derrubar**: na EC2, `cd ~/livekit-ec2 && docker compose up -d` / `docker compose down`
(trunks e regras ficam em `data/redis`). Depois de mudar o `.env` de lá: `./scripts/render-config.sh`
e `dialplan reload` (Asterisk) ou `docker compose restart livekit sip`. **Parar a instância** quando
não estiver em uso (o Elastic IP continua cobrando), lembrando que o sysapi e o worker dependem dela.

**Reversão para o ambiente local**: (1) `docker compose down` na EC2 (libera o registro SIP);
(2) restaurar `sysapi/.env` e `voice-agent/.env` a partir de `voip/backup-env-pre-ec2/` — mas
**manter `GEMINI_VOICE=Leda`** no worker; (3) reiniciar o worker; (4) `cd voip\livekit-local ;
.\scripts\render-config.ps1 ; docker compose start` e conferir `pjsip show registrations` = Registered. O dialplan local já tem o
`[ura-menu]`, o filtro e o `Hangup(17)`, mas o `URA_ATIVA` do `.env` local continua `0` (no Docker
Desktop a URA segue muda).

**Não verificado / pendências**:
- Timeout da URA (não digitar nada -> fila padrão) em ligação real.
- Ligação real recusada pelo filtro depois da troca para `Hangup(17)`; ligação real depois da
  correção do idioma.
- **Ramais pela EC2**: o Laravel gera `pjsip_ramais.conf` no disco local e recarrega o Asterisk via AMI
  em `127.0.0.1:5038`; na EC2 a AMI só escuta em loopback e o arquivo está vazio. Exige AMI pela VPN e
  sincronização do arquivo.
- **Latência**: com o worker no PC o áudio faz provedor -> EC2 -> VPN -> PC -> Gemini -> volta, e o
  LiveKit SIP espera o worker para atender (~1,3 s). Serve para desenvolver; não representa produção.
- **Segurança**: rotacionar o `URA_API_TOKEN`/`VOICE_WORKER_TOKEN` (mesmo valor; apareceu em resultado
  de ferramenta em 25/09/2026). Trocar em `sys_parametros`, no `voice-agent/.env` e no `.env` da EC2
  (render + `dialplan reload`).
- No áudio recebido do provedor há lacunas de ~0,12 s a cada 10 s (saída de 25/09/2026); observar.
- `max_call_seconds` da versão do agente ainda não é aplicado em ligação real.
- Qualidade de voz no telefone: o provedor só oferece PCMU/PCMA/G.729 (8 kHz); o "Ouvir" do Estúdio é
  24 kHz. Não é defeito da stack.

---

## 8. Fora da V1 (dizer ao cliente que está no roadmap)

- Agendamento autônomo ponta a ponta (cenário 1 completo) — a V1 lê do ERP real
  (paciente e agenda), mas **não grava** agendamento
- Multi-tenant de verdade (troncos e números **por instituição/cliente** —
  diferente do cadastro de troncos do M2.5, que é só pro tenant único da demo)
- Relatórios e indicadores completos, QA de chamadas, avaliação de agentes
- Voz pelo WhatsApp (Connectors), que hoje exige LiveKit Cloud
- 🆕 DTMF pra capturar CPF (alternativa a falar o CPF em voz) continua fora —
  diferente do DTMF de menu da URA (M2.5), que agora está dentro da V1
- Discagem preditiva, campanhas de voz ativa
- Alta disponibilidade, failover de operadora, escala horizontal

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| **Demo na máquina local** (decisão 2): queda de link, IP dinâmico, notebook | Alto | Testar o ambiente 1h antes com o checklist; 4G como plano B; vídeo gravado; manter a stack `livekit-ec2` pronta para subir em cerca de 1 hora se a apresentação for remota ou com plateia grande |
| **ERP real fora do ar na hora da demo** | Alto | Modo de contingência do adapter (M1), que cai para dados fictícios sem quebrar a chamada |
| `livekit-client` não compilar no Webpack 3 | Alto | Bundle UMD; resolver no primeiro dia da M2 |
| Latência da IA em demo ao vivo | Alto | Medir na M1; ensaiar; vídeo de backup |
| Egress consumindo CPU da sua máquina durante a demo | Médio | Gravar só o áudio da sala (sem composição de vídeo) e testar com a demo inteira rodando |
| Reconhecimento de CPF falado | Médio | Validação de dígito verificador (já feita); DTMF na V2 |
| Cliente pedir integração com o ERP dele na hora | Médio | Mostrar o cadastro de integração HTTP funcionando com o ERP Demo |
| Internet/telefonia do local da apresentação | Médio | 4G como plano B, número alternativo, vídeo gravado |
| 🆕 Barge-in mal calibrado em áudio de telefone (IA não para quando interrompida, ou para com ruído) | Médio | Calibração dedicada no M1 (ver seção 7); testar com ligação real, não só navegador |
| Custo de IA por minuto | Baixo na demo | 🆕 Preço oficial (set/2026): ~US$ 0,005/min de áudio de entrada + ~US$ 0,018/min de saída (≈ US$ 1,38/hora de conversa cheia). Confirmar na M1 com o uso real da demo e levar para a conversa comercial |
| LGPD (dado de saúde) | Alto no cliente real | Aviso de gravação, dados fictícios na demo, DPA antes de piloto |

---

## 10. Decisões tomadas (20/09/2026)

| # | Decisão | Escolha | Efeito no plano |
|---|---|---|---|
| 1 | Estúdio do Agente | Editor por blocos **+ aba de visualização do fluxo (Drawflow, somente leitura)** | M3 passa de 4–6 para 6–9 dias |
| 2 | Onde roda a demo | **Máquina local** (`voip/livekit-local`) | Sem custo de infra; vira o maior risco da apresentação (ver seção 9) |
| 3 | Número | **+55 84 3190-1994**, o atual | Nada a fazer |
| 4 | Dados da demo | **ERP real do cliente-alvo**, com credenciais já em mãos | M1 cresce para 4–6 dias e ganha modo de contingência |
| 5 | Gravação | **Completa**: Egress → S3 + player sincronizado | M5 passa de 3–4 para 6–8 dias; exige bucket, credenciais e política de retenção |
| 6 | Time | **Você conduz, eu escrevo o grosso** | Revisão e teste a cada marco |
| 7 | Prazo | **6 semanas — alvo 01/11/2026** | Cronograma da seção 7 |

### Pendências que essas decisões criaram

- [ ] Confirmar **qual cliente-alvo e qual ERP** (nome, ambiente de teste, contato técnico)
- [x] (M5: `rapia-files`, prefixo `voz/gravacoes/`) Criar o **bucket S3** das gravações e as credenciais (ou IAM Role) para o Egress
- [ ] Definir a **política de retenção** das gravações (homologação: 90 dias no prefixo) e o texto do aviso falado (já no prompt)
- [ ] Verificar se o **IP fixo** da sua internet se mantém estável nas próximas 6 semanas
- [ ] Checklist de pré-apresentação (link, IP, stack no ar, ERP respondendo, vídeo de backup pronto)
- [ ] 🆕 Calibração de barge-in feita e documentada (ver M1) antes do ensaio final

---

## 11. Roteiro sugerido para a apresentação (12 minutos)

1. (1 min) O RAPIA hoje: WhatsApp oficial, filas, IA no chat.
2. (3 min) **O prospect liga do celular dele.** A IA atende, faz a triagem.
3. (2 min) Painel 360: a chamada na fila com os dados já preenchidos e a transcrição ao vivo.
4. (2 min) A atendente assume em um clique e conversa com ele.
5. (1 min) Encerramento: resumo automático, tags e histórico unificado com o WhatsApp.
6. (2 min) Estúdio do Agente: muda uma regra, publica, liga de novo e ouve a mudança.
7. (1 min) Roadmap e as perguntas: **o que falta para isso servir na sua operação?**

---

## 12. Fontes consultadas na revisão de 22/09/2026

- [LiveKit vs. Pipecat vs. Twilio em produção, 2026](https://www.reactify-solutions.com/articles/voice-ai-agents-production-2026)
- [7 alternativas ao LiveKit para voice AI, 2026](https://www.cekura.ai/blogs/livekit-alternatives)
- [Turn detection: VAD, endpointing e detecção por modelo — LiveKit](https://livekit.com/blog/turn-detection-voice-agents-vad-endpointing-model-based-detection)
- [Guia de barge-in e turn-taking, 2026](https://futureagi.com/blog/voice-ai-barge-in-turn-taking-2026/)
- [LiveKit Agents: observabilidade de agente (produto gerenciado)](https://livekit.com/products/agent-observability)
- [LiveKit Agents e MCP tools](https://www.assemblyai.com/blog/mcp-voice-agent-openai-livekit)
- [Preços oficiais do Gemini API](https://ai.google.dev/gemini-api/docs/pricing)
