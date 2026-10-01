# PROMPT DE INÍCIO — M4.3.3 (c) e (d): "Ligar agora" do retorno discando de verdade + histórico com resultado

Cole este texto como primeira mensagem de uma sessão nova do Claude Code aberta em
`C:\wamp64\www\Infoprime\rapia`. Ele é autossuficiente: a sessão nova não viu nada do que veio antes.

---

## 1. Contexto

Projeto: plataforma de atendimento (clínicas/hospitais/laboratórios). Backend `sysapi` (Laravel 8, PHP 7.4),
frontend `sysweb` (Vue 2.5 + Webpack 3 + Vuex), módulo de voz em `voip/` (SIP + LiveKit + Gemini Live).
Leia `CLAUDE.md` da raiz e **`voip/TODO-RAPIA-VOICE-V1.md`** (fonte da verdade). Leia com atenção, no bloco
**"M4 — Saída: discador, retornos e WhatsApp"**: o **M4.1** (fila de retornos, com os "detalhes técnicos"), o **M4.3.2**
(discador no backend) e o **M4.3.3** inteiro (itens (a)–(d), critérios de pronto e o "Andamento 25/09/2026").
Leia também a **seção 7.3** (ambiente EC2).

Estado (todos na `main`, **sem push**):

| Repo | Commit | O quê |
|---|---|---|
| sysapi / sysweb | `7162dbf` / `120f33b9` | M4.1 fila de retornos (oferta atômica, rodízio, tentativas, aba Retornos) |
| sysapi | `24b87ad` | M4.2 handoff para WhatsApp |
| sysapi / sysweb | `696606b` / `d3e1d3cc` | M4.3.1 sala de saída `out-*`, `direction='outbound'`, accessor `VoiceCall::patient_number` |
| sysapi | `d38392f` | M4.3.2 discador no backend (`VoiceDialerService`, `JobVoiceDialWatch`, `POST /voice/dialer/call`) |
| sysapi / sysweb | `5c4bef9` / `1eb6a475` | M4.3.3 (a)+(b): `V_Discador.vue`, modo humano no softphone, busca de contato, cancelar durante o toque |

`voip/` **não é repositório git** (worker, scripts, TODO e este prompt ficam só no disco).

**Sua tarefa: M4.3.3 itens (c) e (d)** do TODO:
- **(c)** o "Ligar agora" da aba Retornos passa a **originar a ligação de verdade** (hoje só aceita a oferta e a atendente liga
  por fora e registra "Atendeu"/"Não atendeu" à mão), com vínculo retorno ↔ ligação de saída e **resultado automático**;
- **(d)** Histórico de Chamadas com filtro por direção e coluna "Resultado"; ficha com "Ligação feita por…".

Fora deste passo (não construir): M4.4 (qualidade do áudio → humano), M4.5 (WhatsApp Calling), discagem em massa, gravação.

## 2. Como trabalhar (regras do usuário — obrigatórias)

1. **Comece devolvendo um PLANO curto** (subpontos da seção 6, o que vai provar em cada um) e **espere o "ok"**.
2. Pontos pequenos e verificáveis. Ao fim de cada um: rode o que for possível, **mostre o resultado e PARE**.
3. Se algo deste prompt ou do TODO estiver errado diante do código real, **avise e proponha o ajuste**; não obedeça cegamente.
4. Ao concluir cada ponto: atualize o TODO (item (c)/(d) do M4.3.3 + detalhes técnicos que só apareceram na implementação) e
   **PERGUNTE se pode commitar** cada repositório afetado.
5. **Git**: nunca `git push`; sempre na `main`, nunca criar branch; **nenhum commit sem autorização explícita a cada vez**.
   Só `git add` de arquivos específicos. Commits terminam com as linhas de co-autoria que o ambiente indicar.
   **No PowerShell 5.1, mensagem de commit com aspas duplas quebra** (`pathspec ... did not match`): grave a mensagem num
   arquivo do scratchpad e use `git commit -F <arquivo>`.
6. Respostas em português do Brasil, curtas. Sem emojis. Não criar documentos que não foram pedidos.
7. **Nunca digite senha nem faça login por mim.** Para testar no navegador: abra `http://localhost:8080/login` e me peça para
   logar. Ao navegar depois do login pode aparecer um `alert` "O campo email é obrigatório" (resto da tela de login): só aceitar.
8. **Ligação real só com minha autorização**, sempre para o meu celular de teste (**+55 84 98834-5243**, contato 1 "JOAO SOUSA").
   Eu atendo e falo; você confere o banco.
9. Antes de terminar: nenhum processo `agent.py` órfão (só o par launcher `.venv` + filho Python311 do worker) e dados de teste limpos.

## 3. Ambiente (homologação na EC2 — já no ar)

- **LiveKit, LiveKit SIP, Redis e Asterisk rodam na EC2** (`sa-east-1`, IP privado `172.31.11.133`, acesso pela OpenVPN).
  sysapi, sysweb, worker e fila rodam no PC; EC2 → PC pelo ngrok `apiflowip.ngrok.app`. **Não rode `voip/iniciar.ps1`**
  (sobe o Asterisk local = 2º registro no provedor). Tronco de saída: `VOICE_OUTBOUND_TRUNK_ID=ST_EkKWGzGVyyFj` (já no `sysapi/.env`).
- Worker de IA: `agent.py dev` numa janela própria; PID da janela em `voip/.agente.pid`; log `voip/voice-agent/agent.log` em
  **UTF-16** (o Grep lê; `Get-Content -Encoding Unicode` também). Não recarrega sozinho: reiniciar = matar a árvore do PID do
  arquivo + órfãos `agent.py` e subir `powershell -NoExit -Command "& '<voice-agent>\.venv\Scripts\python.exe' agent.py dev 2>&1 | Tee-Object -FilePath agent.log"`
  com `-WorkingDirectory` no `voice-agent`, gravando o novo PID. Neste passo você provavelmente **não** mexe no worker.
- Fila: `php artisan queue:listen --tries=1` numa janela própria (o `JobVoiceDialWatch` e os broadcasts dependem dela).
  **Depois de mudar o `sysapi/.env`, reinicie o `queue:listen`**: os `queue:work --once` filhos herdam o ambiente antigo
  (foi o que fez a chamada 55 ser marcada `failed` com `LIVEKIT_URL=localhost`).
- API: `php -S 127.0.0.1:8000` (atende **uma requisição por vez**: nunca bloqueie uma requisição esperando o toque).
- Front: `http://localhost:8080` (webpack-dev-server com hot reload já rodando). Tenant `api` → banco `ipsys-rapia`.
- **CLI/tinker usa o banco `ipsys`, não o do tenant.** Em scripts PHP de teste, replique o `CheckSubDomain`:
  ```php
  $d = App\Models\SysConnect::where('subdominio','api')->first();
  config(['database.connections.'.$d->db_instancia => ['driver'=>'mysql','host'=>$d->db_host ?? env('DB_APP_HOST'),'database'=>$d->db_instancia,'username'=>$d->db_usr ?? env('DB_APP_USER'),'password'=>$d->db_pwd ?? env('DB_APP_PWD'),'charset'=>'utf8mb4','collation'=>'utf8mb4_unicode_ci','prefix'=>'','strict'=>false]]);
  config(['database.default' => $d->db_instancia]);
  session(['instancia_subdominio' => 'api']);
  ```
  Rode scripts com `php arquivo.php` (bootstrap: `require vendor/autoload.php; $app = require bootstrap/app.php;
  $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();`). Se o script chamar o middleware mais de uma vez,
  restaure `database.default` antes de cada chamada (o `SysConnect` vive na conexão padrão).
- Consultas rápidas: `C:\wamp64\bin\mysql\mysql8.0.27\bin\mysql.exe --no-defaults -uroot ipsys-rapia` (o `--no-defaults` é
  obrigatório: o `my.ini` tem uma opção que o cliente não aceita). Com aspas/JSON no SQL, use heredoc no Bash.
- **Teste de lógica sem discar**: já existe o padrão de um `LiveKitService` falso (subclasse que sobrescreve `call()`,
  registrada com `app()->instance(LiveKitService::class, $falso)`) + `Queue::fake()` + `Event::fake([VoiceCallUpdated::class])`.
  Cuidado: criar sala **real** no LiveKit dispara o webhook real pelo ngrok e cria linha em `voice_calls`.
- Migrations: só a do módulo, **apenas no `ipsys-rapia`**: `Artisan::call('migrate', ['--database'=>$d->db_instancia,
  '--path'=>'database/migrations/<arquivo>.php'])`. **Nunca `migrate:all`**. Toda migration com a checagem do `CLAUDE.md`
  (`strpos($databaseName, 'rapia') !== false`). Sem seeders. Exemplo recente: `2026_09_25_100000_alter_voice_callbacks_m4.php`.

## 4. Como o código está hoje (confira antes de mudar)

**Retornos (M4.1)** — `app/Services/Voice/VoiceCallbackService.php`, `VoiceCallbacksController`, `JobVoiceCallbackTick`:
- Estados: `pending` → `offered` (a um atendente, 45 s) → `calling` (aceitou) → `done` | `pending` de novo (sem resposta, +10 min)
  | `failed` (3 tentativas). `discarded`/`expired` finais. `VoiceCallback::ABERTOS = pending|offered|calling`.
- `aceita()` faz `offered → calling` e **incrementa `attempts`**; `conclui($callback, $user, 'done'|'no_answer')` **exige que o
  `$user` seja quem recebeu a oferta** (não serve para fechamento automático sem usuário: crie uma variante interna ou extraia a regra).
- `voice_callbacks.call_id` = a chamada **de origem** (a que gerou o retorno). Não existe vínculo com a ligação de saída.
- `registra()` grava os eventos do retorno em `voice_call_events` **da chamada de origem**.
- `abertos()` alimenta a aba Retornos (`board()` do `VoiceCallsController`).
- Front: `V_ListaChamadas.vue` (cartões: "Ligar agora"/"Passar"/"Descartar"; em `calling`: "Ligue para X" + "Atendeu"/"Não
  atendeu"), `Painel360.vue::acaoRetorno` (toast "Ligue para … e registre o resultado"), `painel360.js::retornoAcao`.

**Discador (M4.3.2/M4.3.3)** — `app/Services/Voice/VoiceDialerService.php`:
- `disca(User, numero, 'humano'|'ia', ?motivo, ?contactId): VoiceCall` — lança `RuntimeException` com mensagem pronta
  (número inválido, saída aberta para o número, atendente já em ligação, discador não configurado, erro do LiveKit → chamada
  `failed`/`erro_originar`). Cria `voice_calls` `outbound`/`ringing` (`user_id` no humano), sala `out-{tenant}_{numero}_{aleatorio}`,
  `CreateSIPParticipant` **sem** `wait_until_answered`, enfileira `JobVoiceDialWatch`.
- **Atendimento**: `confereAtendimento()` (job a cada 2 s) → `answered_at`, status `human`/`ai`, evento `call_answered`,
  broadcast `call.answered`. **Falha**: `falha($call, motivo)` (`nao_atendeu`, `cancelada`, `erro_originar`,
  `sem_resposta_livekit`) → `failed`, evento `dial_failed`, broadcast `call.ended`. O **webhook** também marca `failed` +
  `dial_failed`/`nao_atendeu` quando o participante SIP sai sem atender (`VoiceWebhookController::tratarParticipanteSaiu`).
  Ou seja, **o fim de uma ligação de saída hoje é decidido em 3 lugares** — o gancho do retorno precisa pegar todos (ver 6.2).
- `cancela($call, $user)` é usado pelo `/voice/calls/end` quando a saída ainda toca.
- Corrida conhecida: se o paciente atende e desliga antes da próxima conferência do job, o webhook marca `failed` uma ligação
  que foi atendida (registrado no TODO; não é para resolver aqui, mas não piore).

**Front do discador**: `V_Discador.vue`, `Painel360.vue` (`onDiscou` seleciona a chamada; `mostrarSoftphone` inclui a saída
própria em `ringing`), `V_Softphone.vue` ("Chamando…/Em ligação", "Cancelar"). Eventos Pusher chegam em `tratarEventoVoz`
(recarrega o board e, para a chamada selecionada, a ficha em `call.answered`/`call.ended`/`participant_left`/`room_finished`).

**Histórico**: `pages/rapia/voz/HistoricoChamadas.vue` (colunas Data, Sentido, De, Para, Status, Duração) +
`VoiceCallsController::listAll` (filtros montados com `whereRaw` a partir de `filters` — **não** passe texto do usuário cru
para ele; prefira um parâmetro próprio validado para `direction`). `voice_calls.from_number/to_number` são **literais**
(quem ligou / quem recebeu); o paciente é `patient_number`.

## 5. Decisões já tomadas (não reabrir)

- Vínculo: **coluna nova `voice_callbacks.dial_call_id`** (FK opcional para `voice_calls.id`), não reaproveitar `call_id`.
- "Ligar agora" disca no **modo humano** (a atendente fala). `motivo` da discagem: `"Retorno: " . reason` (+ `note` se houver).
- Erro ao discar (409/LiveKit) → o retorno **volta para `offered` com a mesma atendente**, sem consumir tentativa
  (desfazer o `attempts + 1` do aceite) e a mensagem do discador aparece na tela.
- "Atendeu"/"Não atendeu" manuais continuam como plano B, mas **somem** enquanto houver ligação de saída viva para o retorno.
- `accept` com `{discar: true}` (padrão `true` na tela). Sem `discar`, comportamento antigo (útil se o discador estiver fora).

## 6. Escopo e ordem sugerida (PARE ao fim de cada subponto)

- **6.1 Migration + modelo**: `voice_callbacks.dial_call_id` (nullable, index, FK `voice_calls` `nullOnDelete`), `fillable`,
  relação `dialCall()`; `abertos()` devolve `dial_call_id` e o status da ligação de saída (`dial_status`, `dial_answered_at`).
  Prova: coluna existe só no `ipsys-rapia`; `board` devolve os campos.
- **6.2 Resultado automático (backend)**: um **ponto único** — ex. `VoiceCallbackService::resultadoDaDiscagem(VoiceCall $call)` —
  chamado quando a ligação de saída é atendida ou falha (`confereAtendimento`, `falha`, caminho `failed` do webhook).
  **Recomendação** (confirme comigo no plano): considerar `done` **no atendimento** (o paciente foi alcançado; se esperar o fim,
  a corrida do job pode transformar atendida em `failed`). Falha → mesma regra do "Não atendeu" (volta para `pending` com
  `next_attempt_at`, ou `failed` no limite) **sem exigir `$user`**. Idempotente (dois ganchos para a mesma chamada = um efeito só).
  Eventos no retorno (`callback_result` com `origem: 'discador'`) e broadcast `callback.updated`.
  Prova: script com LiveKit falso cobrindo atendeu → `done`; não atendeu → `pending`/`next_attempt_at`; 3ª falha → `failed`;
  cancelada → mesma regra de falha (confirme comigo se "cancelada" deve contar tentativa); gancho repetido não duplica.
- **6.3 `accept` discando**: `VoiceCallbacksController::accept` com `discar` → `aceita()` + `VoiceDialerService::disca(...,
  'humano', motivo, $callback->contact_id)` + grava `dial_call_id`; erro → reverte para `offered` (mesma atendente, `attempts - 1`)
  e devolve a mensagem (409). Resposta inclui a chamada criada. Prova: LiveKit falso (sucesso, erro do LiveKit, atendente já em
  ligação, número inválido no retorno).
- **6.4 Front da aba Retornos**: "Ligar agora" chama `accept` com `discar:true`, seleciona a chamada criada (softphone entra em
  "Chamando…", igual ao discador; reaproveite `onDiscou`); com ligação viva o cartão mostra "Em ligação…"/"Chamando…" em vez
  dos botões manuais; ao voltar para `pending` mostra "Não atendeu — nova tentativa às HH:MM"; toast do `acaoRetorno`
  ajustado. Checar microfone antes (mesma função do `V_Discador`; considere extrair para um utilitário comum).
  Prova no Chrome (eu logo) + **ligação real autorizada** (eu atendo; depois outra em que eu recuso).
- **6.5 (d) Histórico e ficha**: filtro Entrada/Saída/Todas em `HistoricoChamadas.vue` (parâmetro próprio no `listAll`), coluna
  "Resultado" (motivo do `dial_failed`: `nao_atendeu` → "Não atendeu", `cancelada` → "Cancelada", `erro_originar` → "Erro ao
  discar", `sem_resposta_livekit` → "Sem resposta do servidor"; atendida → "Atendida"; entrada → vazio ou o status), e "Paciente"
  usando `patient_number` (manter De/Para literais). Ficha (`V_FichaChamada.vue`): "Ligação feita por <atendente>" /
  "Ligação feita pela IA — motivo: …" (motivo em `dial_requested.payload.motivo`). Evite N+1: traga o resultado numa
  subconsulta/join ou num campo calculado no `listAll`.
- **6.6 Acabamento**: TODO (itens (c) e (d) + critérios de pronto do M4.3.3), limpeza de dados de teste, conferência de órfãos.

Critério de pronto (do TODO): retorno com "Ligar agora" → paciente atende → retorno `done` **sem clicar em mais nada**;
retorno → não atende → volta para a fila com nova tentativa; histórico mostra direção e resultado.

## 7. Dados de teste

- Não há retorno aberto hoje. Para criar um, via script: uma `voice_calls` de origem `inbound` com `from_number` =
  `+5584988345243`, `status` `ended`, e `VoiceCallbackService::cria($call, 'ia', 'Teste M4.3.3')`; com o usuário 9 "ADMIN SYS"
  (único SUPER ativo) **Disponível** no Painel 360, a oferta chega por Pusher. Apague retorno, chamada de origem, ligações de
  saída e eventos ao final (as de ligações reais que eu fizer podem ficar, mas avise quais ficaram).
- Contato 1 "JOAO SOUSA" = meu celular. Há contatos com número mascarado (ex. 13 "(84) 98829-6353"): não disque para eles.
- O `JobVoiceCallbackTick` agenda ofertas/expirações com atraso: com o `queue:listen` local, espere 5–10 s além do atraso.

## 8. Primeira resposta esperada

Um plano curto (até ~15 linhas): confirme o que leu (TODO/estado), liste 6.1–6.6 com o que provará em cada um, responda às duas
decisões marcadas "confirme comigo" (`done` no atendimento; "cancelada" conta tentativa?) com a sua recomendação, aponte
divergências entre este prompt e o código real, e **espere meu "ok"**.
