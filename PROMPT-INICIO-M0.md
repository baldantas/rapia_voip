# Prompt de início — Rapia Voice V1, Marco M0 (Fundação)

> Cole o bloco abaixo numa sessão nova do Claude Code aberta em
> `C:\wamp64\www\Infoprime\rapia`. Ele é autossuficiente: não depende do histórico
> desta conversa.

---

```text
Vamos iniciar o desenvolvimento do módulo RAPIA VOICE (atendimento por voz com IA),
Marco M0 — Fundação. Antes de escrever qualquer código, leia nesta ordem:

  1. CLAUDE.md (raiz do projeto)
  2. voip/TODO-RAPIA-VOICE-V1.md   (plano completo; o M0 está na seção 7)
  3. voip/COMANDOS.md              (como o ambiente de voz sobe e para)
  4. voip/livekit-local/README.md e voip/voice-agent/README.md (só para entender a base)

============================================================================
REGRAS DE PRIORIDADE ALTA — valem para TODA a sessão
============================================================================

GIT
  - NUNCA execute `git push`. Em nenhuma circunstância, com nenhuma flag.
  - `git commit` só depois de ME PERGUNTAR se pode commitar o ponto desenvolvido
    e eu responder que sim. A autorização vale para aquele ponto; no seguinte,
    pergunte de novo. Sem resposta afirmativa, não commite.
  - Antes de perguntar, mostre o que mudou (arquivos e resumo) para eu decidir.
  - Não crie branch, tag, stash nem faça reset/rebase sem eu pedir.

PROJETO (do CLAUDE.md)
  - Ignore /sysapi/GL, /sysapi/IPGestor, /sysweb/gl, /sysweb/ipgestor.
  - Migrations: SEMPRE com a checagem do banco RAPIA, sem seeders:
        $databaseName = DB::connection()->getConfig('database');
        if (strpos($databaseName, 'rapia') !== false) { ... }
    Dados iniciais (permissões, parâmetros) entram por migration, nunca por seeder.
  - Backend: Laravel 8 / PHP 7.4 (nada de sintaxe do PHP 8: sem match, sem
    propriedades tipadas em construtor promovido, sem named arguments, sem enums,
    sem nullsafe `?->`). Frontend: Vue 2.5 / Webpack 3 / Babel 6.
  - Escreva o código no estilo do que já existe ao redor: mesma densidade de
    comentários, nomenclatura e idioma (o projeto mistura português e inglês;
    siga o arquivo vizinho).
  - Não instale dependência nova sem me avisar e justificar.

============================================================================
CONTEXTO DO QUE JÁ EXISTE E FUNCIONA (não refaça)
============================================================================

  - Stack local em voip/livekit-local (Docker): Asterisk registra na conta SIP do
    provedor, LiveKit SIP, LiveKit Server, Redis. Sobe com `voip/iniciar.ps1`.
  - Worker Python em voip/voice-agent (livekit-agents 1.8, modelo gemini-3.8-live)
    que atende, coleta nome/CPF/nascimento e chama duas tools. HOJE o prompt e as
    tools são fixos no código; o M1 é que os leva para o banco. No M0 o worker
    NÃO muda.
  - LiveKit em http://localhost:7880; a chave/segredo estão em
    voip/livekit-local/.env (LIVEKIT_API_KEY / LIVEKIT_API_SECRET).
  - Ligação real já foi testada com sucesso pelo número +55 84 3190-1994.

URLs E TENANT (definido por mim, com base no loadConfig() de sysweb/src/main.js)
  - LOCAL: o backend é SEMPRE http://api.ipsys/api/ (subdomínio 'api'). Fixe isso;
    não crie lógica dinâmica para o desenvolvimento local.
  - PRODUÇÃO: https://{tenant}.api.{dominio_projeto}/api/ (ex.: clienteA.api.rapia.app).
  - O middleware `subdominio` (CheckSubDomain) pega o 1º rótulo do Host, procura em
    SysConnect.subdominio e troca a conexão do banco. Portanto tudo que chega no
    host DO TENANT já funciona sem mudança: frontend, e o worker de IA (que chama
    a URL do tenant).
  - O ÚNICO ponto que não chega pelo host do tenant é o WEBHOOK DO LIVEKIT: o
    LiveKit tem UMA lista de URLs e envia cada evento para TODAS elas, então não
    dá para cadastrar uma URL por tenant (vazaria evento entre clientes).
    Solução: webhook em host único e o tenant vem do NOME DA SALA.
  - Nome de sala (FORMATO CONFIRMADO em ligações reais, ver
    voip/voice-agent/coletas.jsonl e a dispatch rule em scripts/dispatch.py):
        {roomPrefix}_{numero_do_chamador}_{12 caracteres aleatórios}
    O LiveKit acrescenta o "_" depois do prefixo. A regra 'agente' usa
    roomPrefix = `call-{tenant}` (tenant do .env do worker; local = 'api'). Exemplos
    reais/observados:
        call-api_84988345243_N845UuDPHnQG      chamador com número
        call-api_anonymous_DkbK6GuexzVh        sem número: vira o texto "anonymous"
    Regex do parser (tenant só letras/números, sem "_" nem "-"):
        /^call-([a-z0-9]+)_([^_]*)_([A-Za-z0-9]+)$/
    O 2º grupo NÃO é confiável como telefone: pode ser "anonymous" e vem em formato
    nacional, sem "+55" (84988345243). Para o telefone do chamador use os atributos
    do participante SIP (`sip.phoneNumber`) e normalize para E.164 (default +55
    quando vier com 10 ou 11 dígitos). O número da central está em
    `sip.trunkPhoneNumber` (+558431901994). O nome da sala contém o telefone do
    paciente: não o copie para logs de aplicação sem necessidade.
  - Modo por configuração, com padrão FIXO (config/voice.php + .env):
        VOICE_TENANT_MODE=fixed   # padrão. Usa o que o CheckSubDomain já resolveu
                                  # (localmente, o banco do subdomínio 'api')
        VOICE_TENANT_MODE=room    # produção. Resolve o tenant pelo nome da sala
    No modo 'room', crie um middleware NOVO (ex.: VoiceTenantFromRoom) — não altere
    o CheckSubDomain. Ele deve: (1) validar a assinatura do webhook ANTES de confiar
    em qualquer campo; (2) extrair o tenant do nome da sala; (3) confirmar que
    existe em SysConnect.subdominio; (4) aplicar a mesma troca de conexão que o
    CheckSubDomain faz; (5) para tenant desconhecido, responder 200, logar e ignorar
    (não 500, senão o LiveKit reenvia). Deixe o código pronto e testado por curl
    forçando VOICE_TENANT_MODE=room, mas o padrão local continua 'fixed'.
    O subdomínio de tenant tem só letras e números (nunca "_" nem "-"), então o
    "_" é um delimitador seguro.
  - Worker de IA: URL do backend por variável, sem código específico de ambiente:
        RAPIA_API_URL=http://api.ipsys/api                    # local (fixo)
        RAPIA_API_URL_TEMPLATE=https://{tenant}.api.rapia.app/api   # produção
    Se o TEMPLATE existir, o worker troca {tenant} pelo tenant da chamada; senão
    usa RAPIA_API_URL. (Implementação no M1; no M0 só documente as chaves.)
  - A URL do WebSocket do LiveKit para o navegador (ex.: ws://localhost:7880 local,
    wss://livekit.rapia.app produção) vem do BACKEND, na resposta de /voice/token.
    O frontend não deve ter URL do LiveKit escrita no código.

Convenções do backend que já levantei e que você deve seguir:

  - Rotas em sysapi/routes/api.php. As rotas de usuário logado ficam dentro de
    `Route::middleware(['api', 'valid.token'])->group(...)` (perto da linha 150),
    dentro do grupo externo `Route::middleware('subdominio')`. São `Route::post`
    com controller em `App\Http\Controllers\Rapia\...`.
  - Chamada máquina-a-máquina (worker → RAPIA) usa o middleware `agentes_ia.api`
    (arquivo app/Http/Middleware/AgentesIAApi.php): header `x-api-key` validado
    contra SysParametrosController::getParametroByValue('AGENTE_IA', ...). Reuse
    esse padrão para as rotas que o worker vai chamar, criando um parâmetro próprio
    (ex.: grupo 'VOICE', chave 'VOICE_WORKER_TOKEN'), por migration.
  - SUPER: coluna `super` ('S'/'N') no model User. Backend: `$user->super == 'S'`
    (ver UserRapiaController.php:54). Frontend: getter `getSuperUser` (ver Menu.vue).
  - Permissões: tabela `sys_permissoes_funcs` (colunas projeto_id, user_type, cod,
    descricao, status) com vínculos em `sys_permissoes_funcs_users` e
    `sys_permissoes_funcs_grupos`. Modelo a seguir:
    database/migrations/2026_09_10_090200_insert_permissao_acolher_solicitacao.php
    e 2025_03_18_152302_insert_permissoes_rapia_0.php (projeto_id '5' = RAPIA).
  - Eventos em tempo real: Pusher com canais privados em routes/channels.php
    (padrão dos eventos em app/Events/Flow/RefreshChatPrivate.php).
  - JWT: firebase/php-jwt já está no vendor. Confirme a versão instalada e use a
    API dessa versão (compatível com PHP 7.4). NÃO instale SDK do LiveKit.
  - S3: disco 's3' já configurado (bucket rapia-files, sa-east-1).
  - Migrations recentes seguem o nome 2026_MM_DD_HHMMSS_descricao.php. Use a data
    de hoje.

============================================================================
ESCOPO DO M0 — o que entregar
============================================================================

Objetivo do marco: uma ligação real aparece gravada no banco do RAPIA, com sua
linha do tempo, e existe um menu "Voz" visível só para SUPER que abre uma tela
provisória. Nada de interface rica aqui: isso é o M2.

A) Banco (migrations + models em app/Models/Rapia/)
   Tabelas (prefixo voice_), todas com a checagem 'rapia':
     - voice_calls: id, room_name (único), direction (inbound/outbound),
       origin (pstn/whatsapp/web), from_number, to_number, status
       (ringing, ai, queued, human, ended, abandoned, failed), contact_id
       (nullable, FK lógica para contacts), agent_id (nullable), user_id
       (atendente, nullable), triage (JSON nullable), summary (text nullable),
       queued_at, answered_at, human_at, ended_at, duration_seconds, created_at,
       updated_at. Índices em status, room_name e created_at.
     - voice_call_events: id, call_id, turn_seq (inteiro nullable — sequencial por
       chamada, preenchido a partir do M1 para correlacionar evento/transcrição/
       tool de um mesmo turno de fala; no M0 fica null), type (string), payload
       (JSON nullable), occurred_at. Índice em (call_id, occurred_at).
     - voice_transcripts (abaixo) também recebe `turn_seq` pelo mesmo motivo.
     - voice_queue_entries: id, call_id, queue_id (nullable), priority, entered_at,
       picked_at (nullable), abandoned_at (nullable).
     - voice_callbacks: id, call_id (origem), contact_id, phone, queue_id, status
       (pending/offered/done/failed/expired), attempts, next_attempt_at,
       offered_to_user_id, created_at, updated_at.
     - voice_transcripts: id, call_id, role (ai/patient/agent), text, spoken_at.
     - voice_recordings: id, call_id, egress_id, s3_key, duration_seconds,
       size_bytes, created_at. (Criar já; o Egress só entra no M5.)
   Escolha os tipos e tamanhos como o resto do projeto; use engine/collation
   iguais às das tabelas vizinhas (confira uma migration recente).
   Os models com $fillable, casts de JSON e relações (call->events, ->transcripts).

B) Permissões e parâmetros (migrations de dados)
   - Criar em sys_permissoes_funcs, projeto_id '5': RAPIAVOICEPAINEL,
     RAPIAVOICEESTUDIO, RAPIAVOICEADMIN. Na V1 quem vê é SUPER; as permissões
     existem para o futuro. Não conceda a ninguém automaticamente.
   - Criar o parâmetro do token do worker (VOICE / VOICE_WORKER_TOKEN) com um
     valor aleatório gerado na própria migration e me diga onde lê-lo; ele vai
     para voip/voice-agent/.env no M1.
   - Parâmetros de LiveKit (URL da API, WS, key, secret, webhook key): siga o
     padrão de config já usado no projeto (config/ + .env). Documente as chaves
     novas em sysapi/.env.example (não edite meu .env com segredos reais sem
     avisar; se precisar, me diga o que acrescentar).

C) Backend (controllers em app/Http/Controllers/Rapia/Voice/, serviços em app/Services/)
   - VoiceAccess: um trait/helper único que decide "usuário pode usar o módulo de
     voz" (super == 'S' OU permissão RAPIAVOICE*). Todas as rotas /voice/* passam
     por ele e devolvem 403 em JSON caso contrário. Esconder o menu NÃO basta.
   - LiveKitService (app/Services/Voice/): 
       * gerar JWT de acesso (HS256, iss=API key, sub=identity, exp curto) com
         grants de sala; perfis: 'atendente' (publica e assina), 'supervisor'
         (só assina, hidden), 'playground';
       * chamar a API Twirp do LiveKit via Guzzle (já instalado): ListRooms,
         ListParticipants, RemoveParticipant, DeleteRoom, CreateSIPParticipant
         (este último só o método, o discador é o M4). Autenticar com JWT de
         admin de vida curta.
       * validar a assinatura dos webhooks (header Authorization com JWT, e o
         hash SHA256 do corpo no claim `sha256`).
   - VoiceTokenController: POST /voice/token {room, role} → token + URL do
     WebSocket. Só SUPER.
   - VoiceWebhookController: POST /voice/livekit/webhook (SEM login; autenticada
     pela assinatura). Trata room_started, participant_joined, participant_left,
     room_finished. Deve ser IDEMPOTENTE (o LiveKit reenvia) e resiliente: nunca
     devolver 500 por evento desconhecido.
       - room_started de sala que case com o regex acima cria voice_calls
         (status 'ringing'); sala fora do padrão (ex.: 'teste-sip') é ignorada.
       - participant_joined: SIP → inbound/from_number a partir dos atributos
         do participante (sip.phoneNumber, sip.trunkPhoneNumber); agente
         (identity iniciando com 'agent') → status 'ai'; atendente web → 'human'.
       - room_finished fecha a chamada, calcula duração.
       - Cada evento vira uma linha em voice_call_events.
     A rota fica FORA do middleware 'valid.token' (a autenticação é a assinatura)
     e DENTRO do grupo 'subdominio', para o modo local funcionar como está. Siga a
     seção "URLs E TENANT": no modo 'fixed' nada extra; no modo 'room' entra o
     middleware de resolução do tenant pelo nome da sala.
   - VoiceCallsController (só leitura por enquanto):
       POST /voice/calls/list {status?, page}, POST /voice/calls/detail {id}
     devolvendo a chamada com eventos e transcrições.
   - Endpoints do worker (grupo com middleware agentes_ia.api), mínimos no M0:
       POST /voice/worker/event  {room, type, payload}  → grava em voice_call_events
       POST /voice/worker/transcript {room, role, text} → grava em voice_transcripts
     (O worker só passa a usá-los no M1; deixe testáveis por curl.)
   - Evento de broadcast VoiceCallUpdated em canal privado do tenant, disparado
     quando a chamada muda de status. Registre o canal em routes/channels.php.
     Ainda não há consumidor no front; só o backend emite.

D) Frontend (sysweb)
   - Menu.vue: bloco "Voz" com o padrão já usado
        v-if="['1','5'].includes(getConfig.projeto_id) && getSuperUser == 'S'"
     com subitens: Painel 360, Estúdio do Agente, Números e Troncos, Histórico
     de Chamadas. Copie a estrutura de um bloco vizinho (ex.: o de IA/Mapa).
   - router/index.js: 4 rotas novas com guarda que impeça a URL direta por quem
     não é SUPER (veja como as rotas existentes fazem `beforeEnter`/meta; se não
     houver padrão, proponha um mínimo).
   - 4 páginas provisórias em pages/rapia/voz/ (Painel360.vue, EstudioAgente.vue,
     NumerosTroncos.vue, HistoricoChamadas.vue). No M0 só o Histórico faz algo:
     lista simples de voice_calls (data, número, status, duração) chamando
     /voice/calls/list. As outras três mostram título e "em desenvolvimento".
     Use TemplateAdmin e os componentes de tabela/paginação já existentes, como
     nas páginas de cadastro vizinhas.
   - Não implemente livekit-client nem softphone agora (M2).

E) Configuração do webhook no LiveKit local
   - JÁ FEITO por mim: o serviço `livekit` do voip/livekit-local/docker-compose.yml
     tem `extra_hosts: api.ipsys:host-gateway` (testei: o container alcança o
     Apache do WAMP com Host api.ipsys e recebe 401 sem login, como no host).
     O .env.example já documenta as duas URLs.
   - Falta: quando a rota existir, preencher LIVEKIT_WEBHOOK_URL no MEU
     voip/livekit-local/.env com http://api.ipsys/api/voice/livekit/webhook, rodar
     .\scripts\render-config.ps1 e `docker compose up -d --force-recreate livekit`,
     e comprovar com uma ligação real que o evento chegou. Se não chegar,
     investigue (log do container livekit, Apache, firewall) antes de mexer em
     qualquer coisa; não gambiarre.

F) Levantamento do ERP (só pesquisa, sem código)
   - Vou colocar a documentação da API do ERP do cliente-alvo em
     voip/erp/. Se a pasta existir, leia e devolva um resumo de: autenticação,
     endpoints de paciente (buscar por CPF, cadastrar) e de agenda, limites,
     formato de erro e ambiente de teste. Se não existir, apenas liste o que
     preciso te entregar.

============================================================================
COMO TRABALHAR
============================================================================

  1. Comece me devolvendo um PLANO curto do M0 (ordem dos passos, arquivos que
     vai criar/alterar, dúvidas). Espere meu "ok" antes de escrever código.
  2. Trabalhe em pontos pequenos e verificáveis, nesta ordem: A → B → C → D → E.
     Ao fim de cada ponto: rode o que for possível, mostre o resultado e pare
     para eu revisar.
  3. Verifique de verdade, não presuma:
       - Rode com `php artisan migrate:all` (App\Console\Commands\MigrateBases):
         itera todo sys_connect com status='A' e migra cada banco na sua própria
         conexão. O guard `strpos($databaseName, 'rapia')` faz nossas migrations
         só pegarem de verdade nos bancos com "rapia" no nome (localmente,
         `ipsys-rapia`, atrás do subdomínio 'api'); nos demais (`ipsys`,
         `ipsys-02`...) o `up()` roda e não faz nada. Confirmado em 22/09/2026:
         `ipsys` e `ipsys-02` ficam sem as tabelas voice_*, só `ipsys-rapia` as
         recebe. Teste o rollback também (`migrate:rollback --database=` do
         banco certo, ou repita o `migrate:all` depois de conferir a subida);
       - `php -l` em todo PHP novo (PHP 7.4);
       - `php -l` em todo PHP novo (PHP 7.4);
       - teste o webhook com curl usando um JWT assinado por você com a mesma
         key/secret, incluindo assinatura inválida (deve dar 401) e evento
         repetido (não pode duplicar);
       - teste as rotas /voice/* com usuário SUPER e com usuário comum (403);
       - suba a stack com voip/iniciar.ps1 -Modo teste, faça uma ligação real e
         confirme que voice_calls e voice_call_events foram preenchidas.
  4. Se algo do plano estiver errado ou desatualizado diante do código real,
     avise e proponha o ajuste; não obedeça cegamente ao TODO.
  5. Ao terminar o M0, atualize as caixas do M0 em voip/TODO-RAPIA-VOICE-V1.md,
     liste tudo que mudou e PERGUNTE se pode commitar. Não dê push.

============================================================================
CRITÉRIO DE PRONTO DO M0
============================================================================

  [ ] Migrations sobem e descem sem erro, só no banco 'rapia'
  [ ] Uma ligação real gera voice_calls + voice_call_events (via webhook)
  [ ] Webhook rejeita assinatura inválida e é idempotente
  [ ] Local funciona com URL fixa http://api.ipsys/api (VOICE_TENANT_MODE=fixed)
  [ ] Modo 'room' testado por curl: tenant válido, tenant desconhecido (200 e
      ignorado) e assinatura inválida (401)
  [ ] Rotas /voice/* respondem 403 para quem não é SUPER
  [ ] Menu "Voz" só aparece para SUPER; URL direta bloqueada para os demais
  [ ] Página Histórico lista as chamadas
  [ ] Token do LiveKit emitido pelo Laravel é aceito pelo servidor
      (validar com http://localhost:7880/rtc/validate?access_token=...)
  [ ] Nenhum segredo real versionado; .env.example documentado
  [ ] Nenhum `git push` executado; nenhum commit sem minha autorização
```

---

## Notas para quem vai colar o prompt

- **Tempo estimado do M0:** 3–4 dias de desenvolvimento (ver seção 7 do TODO).
- **O que você precisa ter em mãos:** a documentação da API do ERP em
  `voip/erp/` (pode ser PDF, Postman ou link) e o cliente-alvo definido.
- **Ponto de atenção resolvido:** o webhook do LiveKit não passa pelo host do
  tenant. Local usa a URL fixa `http://api.ipsys/api`; produção usa host único e
  resolve o tenant pelo nome da sala (modo `room`, desligado por padrão).
- **O que fica de fora de propósito:** softphone, `livekit-client`, Estúdio do
  Agente, discador, gravação (Egress) e mudanças no worker. Vêm nos marcos M1 a M5.
