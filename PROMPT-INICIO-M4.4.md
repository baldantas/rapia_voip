## 1. Contexto

Projeto: plataforma de atendimento (clínicas/hospitais/laboratórios). Backend `sysapi` (Laravel 8, PHP 7.4),
frontend `sysweb` (Vue 2.5 + Webpack 3 + Vuex), módulo de voz em `voip/` (SIP + LiveKit + Gemini Live).
Leia `CLAUDE.md` da raiz e **`voip/TODO-RAPIA-VOICE-V1.md`** (fonte da verdade). Leia com atenção, no bloco
**"M4 — Saída: discador, retornos e WhatsApp"**: o **M4.4 inteiro** (itens (a)–(g), critérios de pronto e estimativa), os
"Achados da chamada 62" do **M4.3.2** e o andamento do **M4.3.3** (a correção do atendimento pelo navegador). Leia também a
**seção 7.3** (ambiente EC2 e as lacunas de áudio de ~0,12 s a cada 10 s) e, no M3, o que é o Playground (sala `pg-*`, buffer
Redis, tools em sandbox) e como as configurações do agente são **versionadas** (`voice_agent_versions.settings`).

Estado (todos na `main`, **sem push**): M0–M3, M4.1, M4.2 e **M4.3 completo** commitados. Últimos commits:

| Repo | Commit | O quê |
|---|---|---|
| sysapi / sysweb | `5c4bef9` / `1eb6a475` | M4.3.3 (a)+(b): discador na tela, modo humano |
| sysapi / sysweb | `779e952` / `60e7f235` | M4.3.3 (c)+(d): "Ligar agora" disca, resultado automático, atendimento pelo navegador, histórico |

`voip/` **não é repositório git** (worker, scripts, TODO e este prompt ficam só no disco).

**Sua tarefa: M4.4 — qualidade do áudio e compreensão -> atendimento humano, FASE 1 (modo sombra)**:
- **(a)** métricas de sinal no `agent.py` (ruído de fundo, nível de fala, SNR estimada, clipping, buracos), publicadas como eventos;
- **(b)** sinais de compreensão: contador no worker (`comprehension_miss`) e a regra no prompt (rascunho pelo Estúdio);
- **(d)** configuração por agente, versionada (`quality_guard` = `off | sombra | ativo` + limites), editável no Estúdio > Configurações;
- início da **calibração** com ligações reais autorizadas.

Fora deste passo (não construir): **(c) transferência automática / modo `ativo`** (só depois da calibração, decisão do
responsável), (f) transcrição paralela Deepgram/Google STT, (g) RTCP do Asterisk via AMI, detecção de caixa postal (AMD),
M4.5 (WhatsApp Calling), dashboard do M5.

## 2. Como trabalhar (regras do usuário — obrigatórias)

1. **Comece devolvendo um PLANO curto** (subpontos da seção 6, o que vai provar em cada um) e **espere o "ok"**.
2. Pontos pequenos e verificáveis. Ao fim de cada um: rode o que for possível, **mostre o resultado e PARE**.
3. Se algo deste prompt ou do TODO estiver errado diante do código real, **avise e proponha o ajuste**; não obedeça cegamente.
4. Ao concluir cada ponto: atualize o TODO (M4.4 + detalhes técnicos que só apareceram na implementação) e
   **PERGUNTE se pode commitar** cada repositório afetado (o usuário pode autorizar um commit único no fim; siga o que ele disser).
5. **Git**: nunca `git push`; sempre na `main`, nunca criar branch; **nenhum commit sem autorização explícita a cada vez**.
   Só `git add` de arquivos específicos. Commits terminam com as linhas de co-autoria que o ambiente indicar.
   **No PowerShell 5.1, mensagem de commit com aspas duplas quebra** (`pathspec ... did not match`): grave a mensagem num
   arquivo do scratchpad e use `git commit -F <arquivo>`.
6. Respostas em português do Brasil, curtas. Sem emojis. Não criar documentos que não foram pedidos.
7. **Nunca digite senha nem faça login por mim.** Para testar no navegador: abra `http://localhost:8080/login` e me peça para
   logar. Ao navegar depois do login pode aparecer um `alert` "O campo email é obrigatório" (resto da tela de login): só aceitar.
8. **Ligação real só com minha autorização**, sempre para o meu celular de teste (**+55 84 98834-5243**, contato 1 "JOAO SOUSA").
   Eu atendo e falo (inclusive com ruído proposital: TV, rua, viva-voz); você confere eventos e log.
   **Atenção**: recusar a ligação no meu celular desvia para a **caixa postal**, que atende (ligação 103 do M4.3.3).
9. **Nunca publique versão do agente** sem eu pedir: trabalhe em **rascunho** pelo Estúdio. A versão 1 publicada do agente 1 é a
   que atende as ligações reais.
10. Antes de terminar: nenhum processo `agent.py` órfão (só o par launcher `.venv` + filho Python311 do worker) e dados de teste limpos.

## 3. Ambiente (homologação na EC2 — já no ar)

- **LiveKit, LiveKit SIP, Redis e Asterisk rodam na EC2** (`sa-east-1`, IP privado `172.31.11.133`, acesso pela OpenVPN).
  sysapi, sysweb, worker e fila rodam no PC; EC2 -> PC pelo ngrok `apiflowip.ngrok.app`. **Não rode `voip/iniciar.ps1`**
  (sobe o Asterisk local = 2º registro no provedor). Tronco de saída `VOICE_OUTBOUND_TRUNK_ID=ST_EkKWGzGVyyFj`.
- **Worker de IA** (`voip/voice-agent/agent.py`, ~340 linhas; `livekit-agents[google]~=1.8`, `aiohttp`; **numpy 2.4.6 já está
  no `.venv`** como dependência transitiva — se for usar, declare no `requirements.txt`). Roda `agent.py dev` numa janela própria;
  PID da janela em `voip/.agente.pid`; log `voip/voice-agent/agent.log` em **UTF-16** (o Grep lê; `Get-Content -Encoding Unicode`
  também). **Não recarrega sozinho**: reiniciar = matar a árvore do PID do arquivo + órfãos `agent.py` e subir
  `powershell -NoExit -Command "& '<voice-agent>\.venv\Scripts\python.exe' agent.py dev 2>&1 | Tee-Object -FilePath agent.log"`
  com `-WorkingDirectory` no `voice-agent`, gravando o novo PID. **Neste passo você mexe no worker**: reinicie depois de cada edição.
- Pontos do `agent.py` que importam: `parametros_do_job` (metadata: `agent_id`, `version_id`, `playground`, `max_seconds`,
  `direction`/`motivo`), `busca_runtime` (`GET /voice/agents/{id}/runtime`, devolve prompt, tools e as configurações da versão),
  `espera_atendimento` (saída: espera `sip.callStatus=active`), `turno["seq"]` (turn_seq incrementado a cada fala, usado para
  correlacionar eventos), `publica_transcricao` (`POST /voice/worker/transcript`), tools por `POST /voice/worker/tools/{name}`.
  **Eventos genéricos**: `POST /voice/worker/event {room, type, payload, turn_seq}` (x-api-key) grava em `voice_call_events`; em
  sala `pg-*` vai para o buffer Redis do Playground (sem `voice_calls`). Não precisa de endpoint novo para `audio_quality`.
- **Áudio**: telefone chega em 8 kHz (G.711) pelo tronco; o Playground é navegador (Opus 48 kHz, áudio limpo) — **as métricas do
  Playground não servem para calibrar limites de telefone**; use o Playground só para provar que o código mede e publica. Não há
  cancelamento de ruído disponível (Krisp só no LiveKit Cloud). A qualidade de conexão do LiveKit não serve (SIP e servidor na
  mesma EC2). Para assinar a trilha do participante SIP em paralelo à sessão do Gemini, um `rtc.AudioStream` próprio no mesmo
  track funciona (pode pedir `sample_rate`/`num_channels`); confira na versão instalada do SDK antes de assumir.
- **CPU**: o worker roda no PC na homologação; medir o custo por chamada (e com 2 sessões simultâneas: ligação + Playground).
- Fila: `php artisan queue:listen --tries=1` numa janela própria (broadcasts e jobs dependem dela; é lenta: um `--once` por job).
  **Depois de mudar o `sysapi/.env`, reinicie o `queue:listen`.**
- API: `php -S 127.0.0.1:8000` (atende **uma requisição por vez**: nunca bloqueie uma requisição esperando áudio/toque).
- Front: `http://localhost:8080` (webpack-dev-server com hot reload já rodando). Tenant `api` -> banco `ipsys-rapia`.
- **CLI/tinker usa o banco `ipsys`, não o do tenant.** Em scripts PHP de teste, replique o `CheckSubDomain`:
  ```php
  $d = App\Models\SysConnect::where('subdominio','api')->first();
  config(['database.connections.'.$d->db_instancia => ['driver'=>'mysql','host'=>$d->db_host ?? env('DB_APP_HOST'),'database'=>$d->db_instancia,'username'=>$d->db_usr ?? env('DB_APP_USER'),'password'=>$d->db_pwd ?? env('DB_APP_PWD'),'charset'=>'utf8mb4','collation'=>'utf8mb4_unicode_ci','prefix'=>'','strict'=>false]]);
  config(['database.default' => $d->db_instancia]);
  session(['instancia_subdominio' => 'api']);
  ```
  Rode scripts com `php arquivo.php` (bootstrap: `require vendor/autoload.php; $app = require bootstrap/app.php;
  $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();`). Dados de teste: prefira transação desfeita no fim.
- Consultas rápidas: `C:\wamp64\bin\mysql\mysql8.0.27\bin\mysql.exe --no-defaults -uroot ipsys-rapia` (o `--no-defaults` é
  obrigatório). Com aspas/JSON no SQL, use heredoc no Bash. `voice_call_events.payload` é JSON (`JSON_EXTRACT`).
- Teste headless de voz existente: `voip/voice-agent/scripts/playground_smoke.py` (modos quick/full/erp). **Microfone
  simulado precisa de ruído de fundo**: silêncio digital faz o SDK do LiveKit reconectar sozinho (achado do M3/E4). O Chrome
  automatizado não tem microfone.
- Migrations: só as do módulo, **apenas no `ipsys-rapia`**: `Artisan::call('migrate', ['--database'=>$d->db_instancia,
  '--path'=>'database/migrations/<arquivo>.php'])`. **Nunca `migrate:all`**. Toda migration com a checagem do `CLAUDE.md`
  (`strpos($databaseName, 'rapia') !== false`). Sem seeders. Provavelmente **não precisa de migration** (settings é JSON).

## 4. Como o código está hoje (confira antes de mudar)

- **Configurações versionadas**: `voice_agent_versions.settings` (JSON: modelo, voz, temperatura, idioma…), 1 rascunho + 1 publicada
  por agente; `VoiceAgentRuntimeController::show` monta o runtime a partir de `$version->settings` (versões antigas com `settings`
  nulo usam os campos do agente). Confira **onde as chaves de `settings` são validadas/filtradas** no salvamento do rascunho
  (controller de versões do Estúdio) antes de acrescentar `quality_guard` e os limites — chave não prevista pode ser descartada.
- **Estúdio (sysweb)**: `EstudioAgente.vue`, `V_Estudio*.vue` (aba Configurações, Playground `V_EstudioPlayground.vue`), `estudio.js`.
- **Transferência** (para quando o modo `ativo` existir, fora deste passo): tool `transferir_para_atendente`
  (`/voice/worker/tools/transferir_para_atendente`), resposta `{ok:false, motivo:'sem_atendente', orientacao}` quando ninguém está
  Disponível; a IA então oferece retorno (`agendar_callback`) ou WhatsApp (`enviar_whatsapp`).
- **Ficha do Painel 360** (`V_FichaChamada.vue::descricaoEvento`): tipos de evento desconhecidos aparecem com o nome cru na linha
  do tempo — um `audio_quality` a cada 10 s poluiria a ficha: trate (ex.: não listar, ou resumir) se a ficha for tocada.
- **Rascunho de teste antigo**: `voice_agent_versions` id 56 ("ZZ Teste M4", agente 1) tem as tools do M4 e o encerramento
  com `sem_atendente`; confira se ainda existe antes de criar outro rascunho (1 rascunho por agente).

## 5. Decisões já tomadas (não reabrir)

- Fase 1 = **só mede e grava**, nunca transfere. `ativo` fica no enum mas não é implementado agora (tratar como `sombra` + aviso no log).
- Métricas no próprio worker, Python puro + numpy, sem dependência pesada nova.
- Eventos em `voice_call_events` pelo `/voice/worker/event` existente: `audio_quality` (~10 s, com `turn_seq` atual), um resumo
  no fim da chamada, e `comprehension_miss` (com o texto que motivou).
- Configuração por agente e **versionada** junto das demais (`voice_agent_versions.settings`), editável no Estúdio > Configurações.
- Regra de compreensão no prompt ("se não entender duas vezes seguidas…") entra **em rascunho**; publicar só com o responsável.
- Playground mede e pode mostrar as métricas, mas **nunca transfere** (sandbox).

## 6. Escopo e ordem sugerida (PARE ao fim de cada subponto)

- **6.1 Configuração**: `quality_guard` (`off|sombra|ativo`, padrão `off`), `snr_min_db`, `janelas_seguidas`, `max_buracos_pct`,
  `max_incompreensoes` em `settings`; runtime devolve; Estúdio > Configurações edita (com valores iniciais propostos e texto de
  ajuda dizendo que são provisórios até a calibração). Prova: salvar no rascunho, runtime do rascunho devolve, publicada intacta.
- **6.2 Medição de sinal (offline primeiro)**: módulo/função pura no worker que recebe quadros PCM e devolve as métricas por janela
  (RMS/dBFS de fala e de ruído com histerese, SNR, clipping, buracos >= 100 ms de silêncio digital). Prova **sem ligação**: script
  em `voice-agent/scripts/` alimentando WAVs gerados (tom + ruído em SNR conhecida, clipping, buracos inseridos) e conferindo os
  números.
- **6.3 Ligar no worker**: com `quality_guard != off`, assinar a trilha do participante SIP (ou do navegador no Playground) em
  paralelo, publicar `audio_quality` a cada ~10 s e o resumo no fim; custo de CPU medido. Prova: Playground (evento no buffer) e
  `playground_smoke.py` com ruído; log sem erro; sessão do Gemini sem atraso perceptível.
- **6.4 Compreensão**: contador no worker (transcrição vazia/`??`, sinais de espanhol `¿ ¡`/palavras frequentes, IA pedindo
  repetição "pode repetir", "não entendi", "não consegui ouvir"), evento `comprehension_miss`; N seguidas só registradas (sem
  gatilho). Regra do prompt num **rascunho** do agente 1. Prova: Playground falando baixo/longe/em espanhol.
- **6.5 Ficha**: `audio_quality`/`comprehension_miss` não poluem a linha do tempo; opcional: um resumo "Áudio: SNR ~X dB,
  ruído ~Y dBFS" na ficha. Prova no Chrome (eu logo).
- **6.6 Calibração (ligações reais autorizadas)**: 3–5 ligações de entrada para a IA com o agente em `sombra` (silêncio, TV alta,
  rua/viva-voz, fala baixa), conferindo os eventos. **O agente que atende a entrada usa a versão publicada**: combine comigo como
  ativar `sombra` para essas ligações sem publicar mudanças de prompt (ex.: publicar uma versão só com a configuração, ou um
  interruptor por variável de ambiente no worker só na homologação — proponha no plano). Registre no TODO uma tabela das
  ligações com as métricas e uma proposta de limites.
- **6.7 Acabamento**: TODO (M4.4 fase 1 + tabela de calibração + o que falta para a fase 2), limpeza de dados de teste,
  conferência de órfãos.

Critério de pronto desta sessão: fase 1 no ar com `audio_quality`/`comprehension_miss` gravados em ligação real; regra de
compreensão em rascunho; limites propostos com base nas ligações de calibração. A fase 2 (transferência) fica para depois.

## 7. Dados de teste e cuidados

- Ligações de entrada: o filtro de números permitidos (`VOICE_FILTRO_ENTRADA`/`VOICE_NUMEROS_PERMITIDOS`) deve incluir o meu
  celular; confira antes de pedir para eu ligar. URA de entrada fica sempre ativa na homologação.
- Eventos das ligações reais podem ficar no banco (são o material de calibração); apague só o que for teste sintético.
- Provas reais antigas ainda pendentes (M4.1–M4.3) estão na memória do projeto; **não** são parte desta sessão.

## 8. Primeira resposta esperada

Um plano curto (até ~15 linhas): confirme o que leu (TODO/estado), liste 6.1–6.7 com o que provará em cada um, proponha como
ativar o modo `sombra` nas ligações reais sem publicar prompt novo (6.6), dê os valores iniciais propostos para os limites,
aponte divergências entre este prompt e o código real (em especial: validação das chaves de `settings`, API de `AudioStream`
da versão instalada) e **espere meu "ok"**.
