# Prompt de início — Rapia Voice V1, Marco M1 (IA conectada ao RAPIA)

> Cole o bloco abaixo numa sessão nova do Claude Code aberta em
> `C:\wamp64\www\Infoprime\rapia`. Ele é autossuficiente: não depende do
> histórico da sessão que fez o M0, mas assume que o M0 já está commitado
> (sysapi 7a4f00b, sysweb 454c725f) e funcionando.

---

```text
Vamos iniciar o Marco M1 do módulo RAPIA VOICE — IA conectada ao RAPIA. Antes de
escrever qualquer código, leia nesta ordem:

  1. CLAUDE.md (raiz do projeto)
  2. voip/TODO-RAPIA-VOICE-V1.md   (plano completo; M1 está na seção 7, com os
     "detalhes técnicos que só apareceram na implementação" do M0 — leia com
     atenção, evita redescobrir o que já foi mapeado)
  3. voip/COMANDOS.md e voip/iniciar.ps1  (como o ambiente sobe e para)
  4. voip/voice-agent/agent.py e prompt.md (o worker atual — prompt e tools
     fixos no código; é isso que este marco muda)
  5. sysapi: app/Services/Voice/LiveKitService.php,
     app/Http/Controllers/Rapia/Voice/*, config/voice.php,
     database/migrations/2026_09_22_*  (o que o M0 construiu — não refaça)

============================================================================
REGRAS DE PRIORIDADE ALTA — valem para TODA a sessão
============================================================================

GIT
  - NUNCA execute `git push`. Em nenhuma circunstância, com nenhuma flag.
  - `git commit` só depois de ME PERGUNTAR se pode commitar o ponto
    desenvolvido e eu responder que sim. A autorização vale para aquele ponto;
    no seguinte, pergunte de novo. Sem resposta afirmativa, não commite.
  - Antes de perguntar, mostre o que mudou (arquivos e resumo) para eu decidir.
  - sysapi e sysweb são DOIS repositórios git separados (a raiz `rapia/` não é
    repo). Trate os commits de cada um independentemente.
  - Não crie branch, tag, stash nem faça reset/rebase sem eu pedir.

PROJETO (do CLAUDE.md, reforçado pela experiência do M0)
  - Ignore /sysapi/GL, /sysapi/IPGestor, /sysweb/gl, /sysweb/ipgestor.
  - Migrations: SEMPRE com a checagem do banco RAPIA, sem seeders:
        $databaseName = DB::connection()->getConfig('database');
        if (strpos($databaseName, 'rapia') !== false) { ... }
  - Rode migrations com `php artisan migrate:all` (App\Console\Commands\
    MigrateBases) — itera sys_connect com status='A'. Local, só o banco
    `ipsys-rapia` (subdomínio 'api') tem 'rapia' no nome; confirmado no M0 que
    os demais (`ipsys`, `ipsys-02`) ficam intocados pelo guard.
  - Backend: Laravel 8 / PHP 7.4. NADA de sintaxe do PHP 8: sem propriedade
    promovida em construtor, sem match, sem named arguments, sem enums, sem
    nullsafe `?->`, sem str_starts_with/str_contains (use strpos ===0 /
    strpos()!==false). O M0 cometeu esse erro 3 vezes e corrigiu depois de
    escrever — rode `php -l` em CADA arquivo assim que terminar de escrevê-lo,
    não só no fim.
  - Frontend: Vue 2.5 / Webpack 3 / Babel 6. async/await e default params já
    são usados no projeto (funciona); nada de optional chaining `?.` ou `??`.
  - Escreva no estilo do que já existe ao redor (nomenclatura, comentários,
    idioma). Veja os arquivos que o M0 criou como referência de estilo.
  - Não instale dependência nova sem avisar e justificar.

VERIFICAÇÃO (não presuma — o M0 só considerou algo pronto depois de testar de
verdade, e isso vale de novo aqui)
  - `php -l` em todo PHP novo.
  - Teste as tools chamando o endpoint HTTP de verdade (curl) antes de plugar
    no worker.
  - Depois de plugar no worker, faça uma ligação REAL (ou pelo menos originada
    via `.\scripts\asterisk.ps1 teste`, que já dispensa custo de IA) e confira
    o resultado no banco.
  - ANTES de testar qualquer ligação com IA de verdade, rode
    `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object
    { $_.CommandLine -like '*agent.py*' }` e mate qualquer processo esquecido.
    No M0 sobraram dois processos de uma sessão anterior, a dispatch rule
    estava em modo "agente" e uma chamada de teste chegou a ser atendida de
    verdade pelo Gemini por alguns segundos sem eu perceber na hora. Verifique
    também `.\scripts\dispatch.py listar` antes de começar, e deixe em modo
    "teste" ao terminar cada sessão de trabalho, a menos que eu peça o contrário.

============================================================================
O QUE JÁ EXISTE E FUNCIONA (não refaça; construído e testado no M0)
============================================================================

Backend (sysapi, commit 7a4f00b):
  - Tabelas voice_calls, voice_call_events (com turn_seq e livekit_event_id
    para idempotência), voice_queue_entries, voice_callbacks,
    voice_transcripts (com turn_seq), voice_recordings.
  - LiveKitService::accessToken() / ::call() / ::validateWebhook(). NÃO
    reescreva a validação de assinatura — já foi calibrada contra um webhook
    real: Authorization traz o JWT SEM "Bearer ", claim `sha256` =
    base64(sha256(corpo bruto)).
  - VoiceWebhookController grava a chamada e a linha do tempo sozinho a partir
    dos webhooks do LiveKit (room_started/participant_joined/participant_left/
    room_finished). Detecta automaticamente quem entrou na sala:
      kind === 'SIP'                -> paciente (attributes['sip.phoneNumber'])
      kind === 'AGENT'              -> agente de IA (identity "agent-AJ_...")
      identity começa com 'user_'   -> atendente humano (VoiceTokenController)
    Você NÃO precisa duplicar essa lógica no worker; o worker só publica o que
    só ele sabe (transcrição, qual tool rodou, resultado).
  - Endpoints já prontos e testados por curl, esperando o worker:
      POST /voice/worker/event      {room, type, payload, turn_seq?}
      POST /voice/worker/transcript {room, role, text, turn_seq?}
    Autenticados por header x-api-key = sys_parametros(modulo=VOICE,
    param=VOICE_WORKER_TOKEN). O valor já está em voip/voice-agent/.env como
    RAPIA_API_TOKEN (e RAPIA_API_URL=http://api.ipsys/api). Local é fixo,
    igual o resto do sysweb (loadConfig()) — não invente lógica de subdomínio
    dinâmico aqui, só em produção (ver TODO 7.2).
  - GET (via API do worker) para configuração do agente NÃO EXISTE ainda —
    é o primeiro item deste marco (ver escopo abaixo).

Frontend (sysweb, commit 454c725f):
  - Menu "Voz" e as 4 rotas, restritas a SUPER. Nada muda aqui neste marco.

Worker (voip/voice-agent, ainda não tocado por nenhum marco):
  - agent.py: prompt e as 2 tools (registrar_dados_paciente,
    transferir_para_atendente) são FIXOS no código e em prompt.md. Isso é
    exatamente o que este marco substitui por configuração vinda do RAPIA.
  - livekit-agents 1.8, modelo gemini-3.8-live. TENANT=api no .env (usado por
    scripts/dispatch.py para montar o roomPrefix "call-{tenant}").

============================================================================
ESCOPO DO M1 — o que entregar
============================================================================

Objetivo do marco: a IA atende puxando prompt e ferramentas do RAPIA (não mais
fixos no agent.py), registra a triagem de verdade no banco, e o worker publica
transcrição/eventos nos endpoints que o M0 já deixou prontos. Interface rica
(Estúdio do Agente) é M3 — aqui a configuração pode existir só como registro
direto no banco (migration com dado de exemplo, ou endpoint simples), o
importante é o CONTRATO entre worker e RAPIA funcionar.

A) Modelagem mínima do agente (migrations + models, sysapi)
   - voice_agents: id, name, description, status, model (default
     'gemini-3.8-live'), voice (default 'Kore'), temperature, language,
     greeting_instructions (texto livre — a instrução inicial que hoje está
     hardcoded em agent.py::generate_reply), max_call_seconds, default_queue_id.
   - voice_agent_versions: id, agent_id, prompt (o texto que hoje é
     prompt.md, com os placeholders {{clinica}} etc.), status (draft/
     published), published_at, created_by.
   - voice_agent_tools: id, agent_version_id, name (o nome da function, ex.
     registrar_triagem), description (o que vai no docstring/JSON Schema para
     o modelo), parameters_schema (JSON Schema dos parâmetros), kind (internal
     | http), endpoint (nullable, usado quando kind=http), enabled.
   - Antes de desenhar close demais: decida e documente na migration se
     reaproveita a tabela cad_agentes_ia já existente (tem name/description/
     status/prompt) ou cria voice_agents em paralelo. O TODO (seção 5.2)
     sugeria avaliar isso — decida e justifique no comentário da migration,
     não deixe em aberto.
   - Migration de dado: publique 1 agente "Triagem Central" com 1 versão
     publicada cujo prompt seja a migração do conteúdo atual de
     voip/voice-agent/prompt.md (adapte os placeholders), e 2 tools internas:
     registrar_triagem (nome novo do que hoje é registrar_dados_paciente) e
     transferir_para_atendente. Isso dá ao worker algo real para carregar
     desde o primeiro teste.

B) Endpoint de runtime (sysapi)
   - GET /voice/agents/{id}/runtime (ou POST, se preferir corpo com o contexto
     da chamada) — autenticado por voice.worker.api (mesmo middleware do M0).
     Devolve: prompt já com variáveis resolvidas (clínica, data/hora), voz,
     modelo, temperatura, e a lista de tools habilitadas na versão publicada
     (nome, description, JSON Schema).
   - Cache curto (ex.: 30–60s, Cache::remember) por agent_id: evita bater no
     banco a cada chamada, mas não trava a "IA não pode ficar sem responder no
     M1" — decida o TTL você mesmo e justifique.

C) Executor de tools no lado do RAPIA (sysapi)
   - Tools internas do M1 (mínimo): registrar_triagem (grava em
     voice_calls.triage, JSON, e cria/vincula o contato — reaproveite
     App\Models\Rapia\Contacts, buscando por telefone antes de criar) e
     transferir_para_atendente (por ora, só registra o evento
     'transfer_requested' em voice_call_events — a fila de verdade e o Painel
     360 são M2; não invente UI aqui).
   - Essas duas tools são chamadas pelo WORKER (via /voice/worker/event, tipo
     'tool_called'/'tool_result') OU diretamente pelo worker fazendo a
     validação e persistência ele mesmo via um endpoint dedicado de execução
     de tool (ex.: POST /voice/worker/tools/{name}) — ESCOLHA UMA abordagem e
     justifique. Recomendo o endpoint dedicado (mais fácil de auditar e de
     estender para tools HTTP externas no M3), mas decida você à luz do que
     encontrar.
   - Todo tool call e resultado precisa virar uma linha em voice_call_events
     (isso já é possível com o endpoint /voice/worker/event existente).

D) Worker (voip/voice-agent) — aqui SIM mexe no agent.py
   - No início da chamada (dentro de atender(ctx)), buscar a config do agente
     via GET /voice/agents/{id}/runtime usando RAPIA_API_URL e
     RAPIA_API_TOKEN do .env. O agent_id vem dos metadados do dispatch (hoje
     a dispatch rule não passa agent_id — ajuste
     voip/voice-agent/scripts/dispatch.py para incluir
     room_config.agents[0].metadata com {"agent_id": N}, e leia isso em
     ctx.job.metadata ou nos metadados da sala; confirme o formato real
     olhando os campos que o LiveKit realmente entrega, não presuma).
   - Montar o Agent dinamicamente: instructions = prompt vindo do runtime;
     as function_tools do agent.py viram genéricas, construídas em runtime a
     partir da lista de tools (nome + JSON Schema) — não um método fixo por
     tool. Cada chamada de tool do modelo vira uma requisição HTTP para o
     RAPIA (ver item C) e devolve o resultado ao modelo.
   - Publicar transcrição: usar o evento `conversation_item_added` que já
     está sendo logado no console (ver agent.py) para também mandar um POST
     /voice/worker/transcript a cada fala. Cuidado para não travar a
     conversa esperando essa requisição — dispare em background
     (fire-and-forget com tratamento de erro, sem bloquear o áudio).
   - `sala` (room_name) já é enviada pelo worker hoje para compor o JSON local
     (coletas.jsonl); use o mesmo valor para os campos `room` dos dois
     endpoints do worker.
   - Calibração de barge-in (revisão de 22/09 do TODO, seção 2.5): teste a
     interrupção da IA com uma ligação de verdade (telefone real, não só
     softphone de navegador) e ajuste `realtime_input_config` do
     google.realtime.RealtimeModel até parar de falar quando interrompida sem
     cortar por ruído de linha. Documente o valor escolhido e por quê.
   - coletas.jsonl pode continuar existindo como log local de depuração, mas
     não é mais a fonte de verdade — o banco é.

E) Modo de contingência do ERP (fica pendente até o M0/prompt-M1 saber qual
   cliente-alvo)
   - Se eu já tiver te passado a documentação da API do ERP (pasta voip/erp/
     ou informação direta), implemente o adapter de buscar_paciente/
     cadastrar_paciente/consultar_agenda como tool nova, com fallback: se o
     ERP não responder em ~3s, cai para um retorno "indisponível no momento"
     que a IA sabe contornar (o prompt deve orientar isso), e registra o
     evento de falha.
   - Se eu ainda NÃO tiver passado nada, não invente endpoint de ERP: apenas
     me avise que essa pendência trava essa parte específica e siga com o
     resto do M1 (registrar_triagem e transferir_para_atendente não dependem
     de ERP nenhum).

============================================================================
COMO TRABALHAR
============================================================================

  1. Comece me devolvendo um PLANO curto do M1: a decisão de A (reaproveitar
     cad_agentes_ia ou criar voice_agents do zero) e de C (endpoint genérico de
     evento vs. endpoint dedicado por tool), arquivos que vai tocar, dúvidas.
     Espere meu "ok" antes de escrever código.
  2. Trabalhe em pontos pequenos e verificáveis, nesta ordem: A → B → C → D.
     O item E só depois de D estar testado, e só se o ERP já estiver definido.
  3. Ao fim de cada ponto: rode o que for possível, mostre o resultado e pare
     para eu revisar.
  4. Se algo do plano estiver errado ou desatualizado diante do código real
     (inclusive o que este prompt presume sobre o LiveKit), avise e proponha o
     ajuste; não obedeça cegamente.
  5. Ao terminar o M1, atualize as caixas do M1 em voip/TODO-RAPIA-VOICE-V1.md
     com os mesmos detalhes de "o que só apareceu na implementação" que o M0
     deixou registrado, liste tudo que mudou nos DOIS repositórios (sysapi e
     sysweb, se tocar) e PERGUNTE se pode commitar cada um. Não dê push.

============================================================================
CRITÉRIO DE PRONTO DO M1
============================================================================

  [ ] Prompt e tools vêm do banco (GET /voice/agents/{id}/runtime), não mais
      fixos em agent.py/prompt.md
  [ ] Uma ligação real (ou via asterisk.ps1 teste, se ainda sem custo de IA
      nesse passo específico) resulta em voice_calls.triage preenchido e um
      contato criado/vinculado
  [ ] Transcrição aparece em voice_transcripts durante/depois da ligação
  [ ] Eventos de tool (chamada e resultado) aparecem em voice_call_events
  [ ] Barge-in testado e calibrado com ligação real, valor documentado
  [ ] Nenhum processo agent.py órfão ao final da sessão; dispatch rule
      devolvida ao modo "teste"
  [ ] Nenhum `git push` executado; nenhum commit sem minha autorização
```
