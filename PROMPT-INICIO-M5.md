## 1. Contexto

Projeto: plataforma de atendimento (clínicas/hospitais/laboratórios). Backend `sysapi` (Laravel 8, PHP 7.4),
frontend `sysweb` (Vue 2.5 + Webpack 3 + Vuex), módulo de voz em `voip/` (SIP + LiveKit + Gemini Live).
Leia `CLAUDE.md` da raiz e **`voip/TODO-RAPIA-VOICE-V1.md`** (fonte da verdade). Leia com atenção: a **seção 1** (a sequência
que a demonstração precisa rodar), a **seção 11** (roteiro de 12 minutos), o bloco **"M5 — Acabamento de demonstração"**
inteiro, a **seção 7.1** (Egress/gravação — escrita para a stack local, hoje a homologação é a EC2), a **seção 7.3**
(ambiente EC2) e, no M4.4, o "Fase 1 — andamento" (o que o worker já mede e publica, e o estado deixado na homologação).

Estado (todos na `main`, **sem push**): M0–M3, M4.1–M4.3 e **M4.4 fase 1 (modo sombra)** commitados. Últimos commits:

| Repo | Commit | O quê |
|---|---|---|
| sysapi / sysweb | `df8551f` / `e1b89d78` | M4.4 6.1: `quality_guard` versionado + Estúdio |
| sysweb | `b8325097` | M4.4 6.3–6.5: qualidade do áudio no Playground e na ficha |
| sysweb | `6aba5392` | Painel 360: duração da chamada encerrada (`ended_at`) e presença Indisponível no `pagehide` |

`voip/` **não é repositório git** (worker, scripts, TODO e este prompt ficam só no disco).

**Sua tarefa: M5 — acabamento da demonstração, 6 pontos em sequência** (seção 6). O M4.4 fase 2 (transferência automática)
**não** faz parte: espera mais ligações em sombra e decisão do responsável. M4.5 (WhatsApp Calling) também não.

## 2. Como trabalhar (regras do usuário — obrigatórias)

1. **Comece devolvendo um PLANO curto** (os 6 pontos, o que vai provar em cada um, divergências achadas no código) e
   **espere o "ok" só desta vez**.
2. Depois do "ok", **execute os 6 pontos em sequência, sem pedir autorização para passar ao seguinte**. Ao fim de cada ponto:
   rode as provas possíveis, atualize o TODO (item do M5 + detalhes técnicos que só apareceram na implementação) e siga.
   **Pare e pergunte apenas quando for necessário**: ligação real, login no navegador, credencial/ação na AWS, publicar
   versão do agente, decisão de produto que o TODO não fecha, ou algo do prompt/TODO que esteja errado diante do código.
3. Se algo deste prompt ou do TODO estiver errado diante do código real, **avise e proponha o ajuste**; não obedeça cegamente.
4. **Commit só no fim dos 6 pontos**: mostre o resumo, os arquivos por repositório e as mensagens, e **peça a autorização
   uma vez** (um commit por repositório afetado). Nenhum commit no meio.
5. **Git**: nunca `git push`; sempre na `main`, nunca criar branch. Só `git add` de arquivos específicos. Commits terminam com
   as linhas de co-autoria que o ambiente indicar. **No PowerShell 5.1, mensagem de commit com aspas duplas quebra**: grave a
   mensagem num arquivo do scratchpad e use `git commit -F <arquivo>` (no Bash funciona igual).
6. Respostas em português do Brasil, curtas. Sem emojis. Não criar documentos que não foram pedidos.
7. **Nunca digite senha nem faça login por mim.** Para testar no navegador: abra `http://localhost:8080/login` e me peça para
   logar. Ao navegar depois do login pode aparecer um `alert` "O campo email é obrigatório": só aceitar.
8. **Ligação real só com minha autorização**, sempre do/para o meu celular de teste (**+55 84 98834-5243**, contato 1
   "JOAO SOUSA"). Eu atendo e falo; você confere eventos e log. Recusar a ligação no meu celular cai na **caixa postal**.
9. **Nunca publique versão do agente** sem eu pedir. A v1 publicada do agente 1 atende as ligações reais; o rascunho v2
   (id 58) tem a regra "Ligação com dificuldade" do M4.4 e **não** deve ser publicado nem descartado.
10. Antes de terminar: nenhum processo `agent.py` órfão (só o par launcher `.venv` + filho Python311), dados de teste
    limpos (dados de demonstração do ponto 6 ficam, identificados) e **minha presença de voz Indisponível** (abrir o
    Painel 360 me marca Disponível: saia pela navegação interna ou pelo seletor e confira `users.voice_status` do id 9 = 2).

## 3. Ambiente (homologação na EC2 — já no ar)

- **LiveKit, LiveKit SIP, Redis e Asterisk rodam na EC2** (`sa-east-1`, IP privado `172.31.11.133`, Elastic IP `54.20.82.110`,
  acesso pela OpenVPN; SSH `ssh -i ~/.ssh/srv_ipsys_web_sp ubuntu@172.31.11.133`, stack em `~/livekit-ec2`, pacote em
  `voip/livekit-ec2/`). sysapi, sysweb, worker e fila rodam no PC; EC2 -> PC pelo ngrok `apiflowip.ngrok.app` (webhooks do
  LiveKit chegam por ele). **Não rode `voip/iniciar.ps1`** (sobe o Asterisk local = 2º registro no provedor).
  **O Egress (gravação) tem de subir na EC2**, junto da stack de lá, não na `livekit-local` (a seção 7.1 foi escrita antes da
  EC2: adapte e registre). A t3a.medium tem 2 vCPU: meça o custo do `egress` durante uma ligação.
- **Worker de IA** (`voip/voice-agent/agent.py` + `qualidade.py`): roda `agent.py dev` numa janela própria; PID em
  `voip/.agente.pid`; log `voip/voice-agent/agent.log` em **UTF-16** (`iconv -f UTF-16 -t UTF-8` no Bash). **Não recarrega
  sozinho**: reiniciar = matar a árvore do PID do arquivo + órfãos `agent.py` e subir
  `powershell -NoExit -Command "& '<voice-agent>\.venv\Scripts\python.exe' agent.py dev 2>&1 | Tee-Object -FilePath agent.log"`
  com `-WorkingDirectory` no `voice-agent`, gravando o novo PID; conferir `registered worker` no log.
  No `voice-agent/.env` (só homologação): `VOICE_WORKER_CARGA_FIXA=0` (sem isso o LiveKit recusa despacho quando a CPU do PC
  passa de ~0,9 — "no servers available") e `VOICE_QUALITY_GUARD_FORCAR=sombra` (toda ligação real grava `audio_quality`
  a cada 10 s, `audio_quality_summary` no fim — chega ~20 s depois de desligar — e `comprehension_miss`).
  No Windows os jobs são **threads** do processo do worker (`JobExecutorType.THREAD`): CPU medida é do processo inteiro.
  O livekit-agents é o **1.8.2**; o Gemini Live expõe uso (`session.usage` / métricas por resposta) — confira na versão
  instalada antes de assumir nomes (ponto 4).
- Pontos do `agent.py` que importam: `parametros_do_job`, `busca_runtime`, `espera_atendimento` (saída), `turno["seq"]`,
  `publica_transcricao`, `publica_evento` (`POST /voice/worker/event {room, type, payload, turn_seq}` grava em
  `voice_call_events`; sala `pg-*` vai para o buffer Redis do Playground), `GuardaQualidade.encerra` (shutdown callback: é o
  lugar natural para mandar também o uso/custo no fim da ligação).
- Fila: `php artisan queue:listen --tries=1` numa janela própria (broadcasts e jobs dependem dela; lenta: um `--once` por
  job; às vezes para sozinha — confira se está rodando). **Depois de mudar o `sysapi/.env`, reinicie o `queue:listen`.**
- API: `php -S 127.0.0.1:8000` (**uma requisição por vez**) e também `http://api.ipsys/api` (Apache do WAMP, é o que o worker
  e o front usam). Front: `http://localhost:8080` (webpack-dev-server com hot reload; para conferir compilação:
  `curl -s http://localhost:8080/app.js | grep -c "Module build failed"`). Tenant `api` -> banco `ipsys-rapia`.
- **CLI/tinker usa o banco `ipsys`, não o do tenant.** Em scripts PHP de teste, replique o `CheckSubDomain`:
  ```php
  $d = App\Models\SysConnect::where('subdominio','api')->first();
  config(['database.connections.'.$d->db_instancia => ['driver'=>'mysql','host'=>$d->db_host ?? env('DB_APP_HOST'),'database'=>$d->db_instancia,'username'=>$d->db_usr ?? env('DB_APP_USER'),'password'=>$d->db_pwd ?? env('DB_APP_PWD'),'charset'=>'utf8mb4','collation'=>'utf8mb4_unicode_ci','prefix'=>'','strict'=>false]]);
  config(['database.default' => $d->db_instancia]);
  session(['instancia_subdominio' => 'api']);
  ```
  Rode com `php arquivo.php` (bootstrap: `require vendor/autoload.php; $app = require bootstrap/app.php;
  $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();`). Controllers podem ser chamados direto com
  `Request::create(...)` + `setUserResolver` (usuário 9 "ADMIN SYS", único SUPER). Dados de teste: prefira transação
  desfeita no fim.
- Consultas rápidas: `C:\wamp64\bin\mysql\mysql8.0.27\bin\mysql.exe --no-defaults -uroot --default-character-set=utf8mb4
  ipsys-rapia` (`--no-defaults` obrigatório; SQL com `$` ou aspas: heredoc no Bash). `voice_call_events.payload` é JSON.
- Migrations: só as do módulo, **apenas no `ipsys-rapia`**: `Artisan::call('migrate', ['--database'=>$d->db_instancia,
  '--path'=>'database/migrations/<arquivo>.php'])`. **Nunca `migrate:all`**. Toda migration com a checagem do `CLAUDE.md`
  (`strpos($databaseName, 'rapia') !== false`). Sem seeders (dados de demonstração do ponto 6: migration própria ou
  script documentado, a decidir no plano).
- Teste headless de voz: `voip/voice-agent/scripts/playground_smoke.py` (modos quick/full/erp/compreensao; `--ruido-dbfs`,
  `--expect-quality`). O Playground não cria `voice_calls` (sala `pg-*`): para testar pós-chamada, gravação e custo numa
  ligação "de verdade" sem telefone, avalie no plano uma forma de gerar uma `voice_calls` de teste (ex.: sala `call-*`
  criada pela API do LiveKit + webhook) ou peça ligação real.
- **Chrome**: o automatizado não tem microfone. Chamadas encerradas não aparecem na lista do Painel 360; para abrir a ficha
  de uma chamada antiga use o próprio método do Painel pelo console (achar o componente com `selecionarChamada` e chamar
  `selecionarChamada({id})`). A captura de rede da extensão do Chrome falhou em registrar XHR nesta máquina: prove pelo banco.
- **CPU do PC**: com navegador/IDE pesados a carga passa de 0,9; o `CARGA_FIXA` evita a recusa de despacho, mas a resposta da
  IA fica lenta. Se algo de voz falhar sem motivo, meça a carga antes de depurar.

## 4. Como o código está hoje (confira antes de mudar)

- **Painel 360** (`sysweb/src/pages/rapia/voz/Painel360.vue`, `V_ListaChamadas.vue`, `V_FichaChamada.vue`,
  `V_Contato360.vue`, `V_Softphone.vue`, `functions/rapia/voz/painel360.js`): `selecionarChamada` carrega o detalhe
  (`functions.detail`); o board vem por broadcast (Echo); a ficha já esconde `audio_quality*`, mostra "Áudio: SNR…" e usa
  `ended_at` na duração. Achado (M5, 25/09): ao encerrar, o card sai da lista mas o painel central continua com o detalhe
  como se estivesse ativo.
- **Histórico de chamadas**: rota `/voice/historico` (M4.3.3 (d): filtro e coluna Resultado). **Contato**: `V_Contato360`
  mostra o histórico do contato — confira como o WhatsApp entra nele antes de acrescentar o resumo da ligação.
- **Gravação**: tabela `voice_recordings` já existe (M0); não há Egress nem `VoiceRecordingService`. Webhook do LiveKit:
  `VoiceWebhookController` (já trata `room_finished` etc.; `egress_ended` a acrescentar). Técnica de URL assinada:
  `TESTE_PRESIGNED_URL.md` do projeto (procure o arquivo).
- **IA para resumo/tags**: descubra no `sysapi` qual integração de IA o RAPIA já usa no chat (resumo de conversa, classificação)
  e **prefira reaproveitar** em vez de criar outra; se for preciso chamar o Gemini do backend, a chave está no
  `voice-agent/.env` (o usuário autorizou copiar segredos entre `.env` sem exibir). Proponha no plano.
- **Custo**: nada captura uso hoje; o TODO (M5, "Custo estimado do Gemini por ligação") já detalha worker -> sysapi ->
  cálculo (preço por milhão de tokens por tipo/modelo × cotação, em `config/voice.php` ou parâmetro) -> exibição.

## 5. Decisões já tomadas (não reabrir)

- Ponto 1: **manter a ficha aberta** quando a chamada selecionada encerra, com **selo "Encerrada"** e botão **"Fechar"**
  (sem fechar sozinha); ações de chamada ativa (transferir, softphone) somem/ficam desabilitadas.
- Gravação: **somente áudio** (`audio_only`), OGG, bucket `rapia-files` prefixo `voz/gravacoes/{tenant}/{yyyy}/{mm}/`,
  URL assinada, player só para SUPER; credencial S3 = **usuário IAM dedicado com política restrita** (quem cria na AWS sou
  eu ou autorizo explicitamente; não reutilize a chave geral do `sysapi/.env`).
- Custo: é **estimativa** e cobre só o Gemini; a API não devolve valor em dinheiro.
- Aviso de gravação já está no prompt do agente (saudação); registrar o consentimento/aviso como evento na linha do tempo.
- Nada de M4.4 fase 2, M4.5 ou publicar o rascunho v2.

## 6. Escopo e ordem (seguir sem parar entre os pontos; parar só no que exigir intervenção)

1. **Painel 360 — detalhe de chamada encerrada**: ao encerrar a chamada selecionada (broadcast), a ficha continua aberta
   com selo "Encerrada", duração final, resumo/transcrição legíveis e botão "Fechar" (limpa a seleção); ações de chamada
   ativa desabilitadas; softphone não reabre. Prova no Chrome (eu logo) com uma chamada que termina com a ficha aberta
   (Playground não aparece no Painel: use ligação real autorizada ou uma `voice_calls` de teste encerrada pela API).
2. **Resumo e tags automáticos no pós-chamada**: ao encerrar (`room_finished`/status ended), job na fila gera resumo curto
   e tags a partir de `voice_transcripts` (+ triagem/eventos); grava na chamada (migration se precisar, com a checagem
   `rapia`); aparece na ficha, no Histórico e no histórico do contato (junto do WhatsApp). Prova com as ligações reais
   104–107 (reprocessar) e uma nova.
3. **Gravação (Egress na EC2) + player sincronizado**: subir o `egress` na stack da EC2 (config, rede, `cap_add`), credencial
   IAM restrita (**parar e pedir** para eu criar/autorizar), `VoiceRecordingService` (`StartRoomCompositeEgress`
   `audio_only`, OGG, S3), webhook `egress_ended` -> `voice_recordings`, decisão mono x `DUAL_CHANNEL_AGENT` testando a troca
   IA -> atendente, player com URL assinada, transcrição rolando junto, marcadores de eventos (tools, transferência,
   aviso de gravação) e download. Medir CPU do `egress` na EC2. Prova com ligação real autorizada.
4. **Custo estimado do Gemini por ligação (R$)**: capturar o uso no worker (confirmar os campos no 1.8.2; validar com uma
   conversa de Playground e, se possível, comparar com o AI Studio), enviar no fim (evento ou endpoint), guardar por
   ligação, calcular com preços/câmbio configuráveis, exibir no Histórico, na ficha e no dashboard. Ligação que cai no
   meio: conferir se o uso vem completo.
5. **Dashboard simples**: chamadas do dia, TME (espera na fila), % resolvido pela IA (sem transferência), duração média,
   custo estimado; opcional: indicadores do M4.4 (SNR mediana, incompreensões) marcados como "em teste". Tela SUPER no
   menu de voz. Prova no Chrome.
6. **Massa de dados fictícia + ensaio**: pacientes, agenda, histórico de WhatsApp e algumas chamadas encerradas com resumo,
   para nenhuma tela aparecer vazia (identificáveis e removíveis; decidir no plano migration x script). Roteiro escrito da
   seção 1/11 com o passo a passo de cada tela e o que conferir antes da apresentação. O ensaio completo ("a sequência da
   seção 1 roda três vezes seguidas") e o **vídeo de backup** dependem de mim: deixe o roteiro pronto e me peça.

Critério de pronto desta sessão: os 6 pontos implementados e provados (o que depende de ligação real/AWS, provado comigo),
TODO atualizado, commits únicos por repositório autorizados no fim.

## 7. Dados de teste e cuidados

- Ligações reais 89, 101, 103, 104–107 são registro real (104–107: calibração do M4.4) — não apague; pode reprocessar
  resumo/tags nelas.
- Filtro de entrada (`sys_parametros` VOICE: `VOICE_FILTRO_ENTRADA`=S, `VOICE_NUMEROS_PERMITIDOS` com o meu celular);
  URA sempre ativa na homologação; dígito 1 = IA (agente 1), 2 = fila.
- Provas reais antigas pendentes (M4.1–M4.3) estão na memória do projeto; não fazem parte desta sessão.
- Gravação é dado sensível (LGPD): nada público, player só SUPER, retenção a definir antes de piloto real (registrar).

## 8. Primeira resposta esperada

Um plano curto (até ~20 linhas): confirme o que leu (TODO/estado), liste os 6 pontos com o que provará em cada um e onde vai
precisar de mim (login, ligações, AWS), proponha: (a) como gerar uma `voice_calls` de teste sem telefone, (b) qual IA usar
para resumo/tags, (c) migration x script para a massa de dados; aponte divergências entre este prompt e o código real e
**espere meu "ok"** — depois disso, siga até o fim do ponto 6 parando só no que exigir intervenção.
