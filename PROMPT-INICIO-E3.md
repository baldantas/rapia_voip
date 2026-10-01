# PROMPT DE INÍCIO — M3 · E3 (Estúdio do Agente: editor de blocos, versões e ferramentas — frontend)

Cole este texto como primeira mensagem de uma sessão nova do Claude Code aberta em
`C:\wamp64\www\Infoprime\rapia`. Ele é autossuficiente: a sessão nova não viu nada do que veio antes.

---

## 1. Contexto

Projeto: plataforma de atendimento (clínicas/hospitais/laboratórios). Backend `sysapi` (Laravel 8),
frontend `sysweb` (Vue 2.5 + Webpack 3 + Vuex + bootstrap-vue), módulo de voz em `voip/`
(SIP + LiveKit + Gemini Live). Leia `CLAUDE.md` da raiz e **`voip/TODO-RAPIA-VOICE-V1.md`**
(fonte da verdade: leia o bloco **"M3 — Estúdio do Agente"**, "Construção do Estúdio (E1…E6)",
"Detalhes técnicos … (Estúdio)" e "(Playground)" antes de qualquer coisa).

Estamos no **M3 — Estúdio do Agente**. Já feito e commitado (todos na `main`, **sem push**):

| Repo | Commit | O quê |
|---|---|---|
| sysapi | `94fc66e` `1767c76` `8e700d6` | P1–P4: runtime aceita rascunho, sessão do Playground, buffer/tools em sandbox |
| sysapi | `f56b9ea` | **E1** — API de versões (rascunho/publicar/comparar/reverter) |
| sysapi | `a4da7c9` | **E2** — catálogo de tools, tools HTTP, "Testar ferramenta", ERP Demo |
| sysweb | `39f7070f` | guarda no Painel 360 para ignorar eventos `playground.*` |

`voip/` **não é repositório git** (worker, scripts e TODO ficam só no disco).

**Sua tarefa: E3 — o frontend do Estúdio.** Hoje `sysweb/src/pages/rapia/voz/EstudioAgente.vue`
é um placeholder de 34 linhas. Rota e menu já existem (`/voice/estudio`, só SUPER, guarda
`guardaVoiceSuper` em `router/index.js`). Todo o backend necessário **já existe e está testado**
(seção 4); não é para mexer nele, salvo bug real (avise antes).

Fora do E3 (não construir): Playground na UI (E4), aba "Visão do fluxo"/Drawflow (E5),
seletor de voz com pré-escuta e "publicar e ouvir a diferença" (E6), tela para **criar** agente
(não há endpoint; ver seção 8).

## 2. Como trabalhar (regras do usuário — obrigatórias)

1. **Comece devolvendo um PLANO curto** do E3 (subpontos da seção 6, o que vai provar em cada um) e **espere o "ok"**.
2. Trabalhe em pontos pequenos e verificáveis. Ao fim de cada um: rode o que for possível,
   **mostre o resultado e PARE** para eu revisar.
3. Se algo do plano/TODO estiver errado ou desatualizado diante do código real, **avise e proponha
   o ajuste**; não obedeça cegamente.
4. Ao concluir cada ponto: atualize o TODO (caixas do E3 + "detalhes técnicos que só apareceram na
   implementação") e **PERGUNTE se pode commitar** cada repositório afetado.
5. **Git**: nunca `git push`; sempre na `main`, nunca criar branch; **nenhum commit sem autorização
   explícita a cada vez** (a autorização de um ponto não vale para o seguinte). Só `git add` de
   arquivos específicos. Commits terminam com as linhas de co-autoria que o ambiente indicar.
6. Respostas em português do Brasil, curtas. Sem emojis. Não criar documentos que não foram pedidos.
7. **Nunca digite senha nem faça login por mim.** Para testar no navegador: abra `http://localhost:8080/login`
   e me peça para logar; depois siga. Chrome automatizado **não tem microfone**.
8. Antes de terminar, confirme que **não sobrou processo `agent.py` órfão** (deve haver só o par
   launcher+filho do worker) e limpe dados de teste que você criar.

## 3. Ambiente (o que já está no ar)

- Stack Docker (LiveKit/SIP/Asterisk/Redis) e o worker `agent.py dev` rodando; PID do worker em
  `voip/.agente.pid`; log em `voip/voice-agent/agent.log` (**UTF-16**: `iconv -f UTF-16 -t UTF-8`).
  Você **não precisa** mexer no worker no E3. Se precisar reiniciar: matar a árvore do PID do arquivo e
  subir `powershell -NoExit -Command "& '<venv>\python.exe' agent.py dev *>&1 | Tee-Object -FilePath agent.log"`
  numa janela própria, gravando o novo PID no arquivo.
- Frontend em dev: `http://localhost:8080` (webpack-dev-server com hot reload já rodando; há outro em 8082).
  Em `localhost` o front usa `http://api.ipsys/api/` e `window.subdomain = "api"` (tenant `api` → banco `ipsys-rapia`).
- `php artisan queue:work redis` precisa estar no ar para broadcasts (já está).
- PHP: `C:\wamp64\bin\php\php7.4.33\php.exe` (PHP 7.4 — não use `match`, `?->`, propriedades tipadas com union).
- **CLI/tinker usa o banco `ipsys`, não o do tenant.** Para consultar/criar dados de teste, replique o
  `CheckSubDomain` no início do script tinker:
  ```php
  $i = App\Models\SysConnect::where('subdominio','api')->first();
  config(['database.connections.tn'=>['driver'=>'mysql','host'=>$i->db_host ?? env('DB_APP_HOST'),'database'=>$i->db_instancia,'username'=>$i->db_usr ?? env('DB_APP_USER'),'password'=>$i->db_pwd ?? env('DB_APP_PWD'),'charset'=>'utf8mb4','collation'=>'utf8mb4_unicode_ci','prefix'=>'','strict'=>false]]);
  config(['database.default'=>'tn']);
  ```
  e rode com `php artisan tinker --execute="$(cat arquivo.php)"` (grave o arquivo com a ferramenta de escrita,
  não com heredoc no bash — já quebrou por causa de aspas).
- Migrations: só as do módulo, **rodadas apenas no banco `ipsys-rapia`** com `Artisan::call('migrate',
  ['--database'=>'tn','--path'=>'database/migrations/<arquivo>.php'])`; **não use `migrate:all`** (percorre
  `ipsys-02`/`ipsys` e dispararia migrations pendentes de outros projetos). Sem seeders. (No E3 provavelmente não há migration.)

## 4. Contrato da API (tudo `POST`, JSON, `Authorization: Bearer <users.token>`)

No front: `this.$axios.post('/voice/studio/...', corpo, { headers: { Authorization: 'Bearer ' + this.$store.getters.getUserToken } })`.
Resposta: `{status:true, data}` · erro de negócio `{status:false, message}` (404/409/422) · validação
`{status:false, validacao:true, erros}` (422) — `erros` vem como `{blocks:[msg…]}`, `{settings:[msg…]}`,
`{tool:[msg…]}` ou o bag do Laravel. **Padrão do projeto**: camada `src/functions/rapia/voz/*.js`
(ver `painel360.js`: `AlertUtils.preventDuplicate/executeWithRetry`, `content.$toastr.e(...)`), componentes
`src/components/componentes/rapia/voz/V_*.vue`, layout `TemplateAdmin`.

**Modelo de versões**: cada agente tem no máx. **1 rascunho** (`draft`), **1 publicada** (`published`) e o
histórico `archived`. Uma versão guarda blocos do prompt + prompt compilado + **settings** (modelo, voz,
temperatura, idioma, saudação, tempo máx.) + tools. Publicar troca tudo de uma vez. "Reverter" =
copiar uma versão para o rascunho (`restore`); nunca publica sozinho. Toda edição vai para o **rascunho**
(criado a partir da publicada quando não existe). Ligações reais só enxergam a publicada.

- `/voice/studio/options` `{}` → `{models[], voices[], languages[], variables:[{name,token,description,example}], limits:{max_blocks,max_title,max_block_chars,max_prompt_chars}}`
- `/voice/studio/agents/list` `{}` → `[{id,name,description,status, published:{id,number,published_at}|null, draft:{id,number,updated_at}|null}]`
- `/voice/studio/agents/detail` `{agent_id}` → `{agent, published:Detalhe|null, draft:Detalhe|null, versions:[Resumo]}`
- `/voice/studio/versions/list` `{agent_id}` · `/versions/detail` `{version_id}` → Detalhe
- `/voice/studio/draft/save` `{agent_id, blocks?, settings?, notes?, expected_updated_at?}` → Detalhe do rascunho.
  `blocks` é a lista **completa e ordenada** (substitui); o 1º bloco de chave `identidade` é o único sem cabeçalho no
  prompt; `key:''` → o servidor gera. `settings`: só os campos enviados mudam. **409** se `expected_updated_at` ≠ o atual.
- `/voice/studio/draft/discard` `{agent_id}` · `/versions/restore` `{version_id}` (substitui o rascunho atual)
- `/voice/studio/publish` `{agent_id, notes?}` → Detalhe da nova publicada; **422** "igual à publicada" se nada mudou.
- `/voice/studio/versions/compare` `{a, b}` → `{a,b (Resumo), blocks:[{key,title,title_before?,status:same|changed|added|removed,diff:[{t:same|add|del,text}]}], settings:[{field,before,after}], tools:[{name,status,enabled,changes:[{field,before,after}]}], has_changes}`
- **Resumo** = `{id,agent_id,number,status:draft|published|archived,notes,created_by:{id,name},published_by,published_at,created_at,updated_at}`
- **Detalhe** = Resumo + `{blocks:[{key,title,content}], settings:{model,voice,temperature,language,greeting_instructions,max_call_seconds}, prompt, prompt_resolved, prompt_chars, tools:[…], warnings:[{type:'unknown_variables', items:[{block,variable}]}]}`

Ferramentas (todas alteram o **rascunho**; aceitam `expected_updated_at` → 409):
- `/voice/studio/tools/list` `{agent_id, version_id?}` → `{version:Resumo, tools:[{name,description,kind:internal|http,endpoint,enabled,parameters_schema,http}], catalog:[{name,title,description}]}`
  (`catalog` = tools internas ainda não presentes na versão)
- `/tools/toggle` `{agent_id,name,enabled}` · `/tools/add-internal` `{agent_id,name}` · `/tools/delete` `{agent_id,name}` → mesma visão da `list`
- `/tools/save` `{agent_id, original_name?, tool:{name,description,enabled?,parameters_schema,http}}` — HTTP: definição completa;
  **interna: só `description` muda**. `original_name` permite renomear.
  - `parameters_schema`: `{type:'object', properties:{<nome minúsculo/_>:{type:string|number|integer|boolean, description, enum?}}, required:[…]}` (plano, sem aninhamento, ≤15)
  - `http`: `{method:GET|POST|PUT|PATCH|DELETE, url, headers:[{name,value,secret}], query:[{name,value}], body:[{name,value}], timeout_seconds:1..10, response_map:[{name,path}], playground:'live'|'simulate', sample_response:{…}|null}`.
    Valores aceitam `{{parametro}}` (só parâmetros declarados). GET não tem `body`. **Segredos**: na leitura vêm `value:null, has_value:true`;
    salvar com `value:''` e `secret:true` **mantém** o segredo já gravado.
- `/tools/test` `{agent_id, name | tool, arguments:{…}, mode?:'live'|'simulate', confirm_live?}` →
  `{name,kind,mode,ok,stage?,request:{method,url,headers(mascarados),body}|null,response:{status,body,…}|null,duration_ms,result_for_model,errors[],note?}`.
  Tool HTTP **que não é GET** sem `confirm_live:true` (e sem `mode:'simulate'`) → **422 com `requires_confirmation:true`**: a UI deve pedir confirmação explícita
  ("isto pode escrever no sistema externo"). Aceita a definição ainda **não salva** do formulário (`tool`).
- **ERP Demo** para testar tool HTTP (dados fictícios, nada é gravado): `GET http://api.ipsys/api/voice/demo-erp/patients?cpf=52998224725`,
  `GET …/appointments?patient_id=1001`, `POST …/callbacks {phone,reason}`; header `x-demo-key: rapia-demo` (marcar como **secret**).
  Exemplo de `response_map`: `[{name:'nome',path:'data.name'},{name:'plano',path:'data.plan'}]`.

## 5. Comportamentos/armadilhas que já custaram caro (respeite)

- Vue 2.5: **sem `?.` nem `??` em template** (nem no script se o Babel do projeto não transpilar — confira antes de usar).
- Guarda o **`updated_at` do rascunho** recebido e reenvie como `expected_updated_at`; em **409** recarregue e avise
  ("alterado por outra pessoa"), sem sobrescrever em silêncio. Indicador de "alterações não salvas" + aviso ao sair da tela.
- **Variáveis** (`options.variables`): `{{clinica}}`, `{{data_hoje}}`, `{{horario}}`. Chips que inserem o token no cursor do bloco.
  `warnings.unknown_variables` (ex.: `{{Nome}}`, maiúsculas, espaços) **não bloqueiam** o save: mostre junto ao bloco (a IA falaria o texto literal).
- Limites de `options.limits` → contadores de caracteres por bloco e do prompt total; respeite `max_blocks`.
- O 1º bloco (`identidade`) é o único sem cabeçalho `##` no prompt compilado. **O backend não obriga** que ele exista nem que fique no topo
  (se for removido, o próximo bloco vira o primeiro e passa a ter cabeçalho normal); trate-o na UI como fixo no topo, sem botão de remover,
  e deixe o resto reordenável/renomeável/removível.
- Números de versão: descartar/substituir um rascunho **reaproveita** o número — só é definitivo depois de publicado. Mostre "rascunho (v{n})".
- `publish` faz o servidor invalidar o cache do runtime: a mudança vale na ligação seguinte (não precisa fazer nada no front).
- Tool **interna**: só a descrição é editável (nome/schema fixos). Tool HTTP: nome `^[a-z][a-z0-9_]{2,59}$`, único por versão, não pode ser nome de interna.
- Nunca exiba nem logue segredos; o backend já mascara. Não coloque credenciais no bundle.
- A tela Painel 360 muda a presença de voz do usuário ao abrir (`voice_status`); o Estúdio **não** deve fazer isso.
- Testar a UI no **navegador de verdade** (login por mim). Cheque o console do Chrome por erros a cada tela. Se não puder testar algo, diga explicitamente.

## 6. Escopo do E3 e ordem sugerida (PARE ao fim de cada subponto)

- **E3.1 — Esqueleto**: seletor de agente (`agents/list`), carrega `agents/detail`, mostra estado (publicada vN / rascunho vN), abas ou seções
  (Editor · Ferramentas · Versões), leitura somente do que existir. Sem edição ainda.
- **E3.2 — Editor de blocos**: lista de blocos reordenável (setas ↑↓ bastam; drag-and-drop é opcional), título editável, textarea,
  contador de caracteres, chips de variáveis, adicionar/remover bloco, "Salvar rascunho" (`draft/save`), indicador de alterações
  não salvas, tratamento de 409/422 (mensagens por bloco), avisos de variável desconhecida, pré-visualização do prompt resolvido (`prompt_resolved`).
- **E3.3 — Configurações da sessão** (versionadas): modelo, voz (lista de `options.voices`, **sem** pré-escuta ainda), temperatura (0–2),
  idioma, instrução da saudação, tempo máx. (30–3600 ou vazio), nota da versão; salvos junto do rascunho.
- **E3.4 — Versões**: publicar (com nota; confirmar), descartar rascunho, histórico (`versions/list`), **comparar** duas versões
  (renderizar `diff` por bloco: linhas `add`/`del`/`same`, badges `changed/added/removed`, diferenças de settings e de tools),
  **restaurar** uma versão antiga para o rascunho (confirmar: substitui o rascunho atual).
- **E3.5 — Ferramentas**: lista com liga/desliga (`tools/toggle`), adicionar interna do catálogo, remover, editar descrição da interna;
  **formulário da tool HTTP** (nome, descrição, editor de parâmetros do schema, método, URL, headers com "secreto", query, corpo,
  timeout, mapeamento da resposta, modo no Playground, resposta de exemplo) com validação das mensagens 422; **painel "Testar ferramenta"**
  (gera campos a partir do schema, roda `tools/test`, mostra requisição/resposta/`result_for_model`/duração; confirmação para não-GET).
- **E3.6 — Acabamento**: estados de carregamento/erro, textos, revisão de responsividade, conferência final no navegador (fluxo completo:
  editar → salvar → comparar → publicar → restaurar → descartar; tool HTTP ponta a ponta contra o ERP Demo).

Critério de pronto do E3: **editor por blocos com variáveis, versões (rascunho/publicar/comparar/reverter) e catálogo de ferramentas com
liga/desliga, e "Testar ferramenta" mostrando requisição e resposta — tudo usável pela UI**, sem depender de scripts.

## 7. Dados de teste

- Agente real: `id 1` "Triagem Central" (versão 1 publicada, 2 tools internas). **Não publique nada nele sem eu autorizar** e descarte os
  rascunhos que criar nele nos testes (rascunho não afeta ligações; publicar afeta).
- Para testar **publicar/reverter** sem tocar no agente real, crie um **agente de teste** via tinker (não há tela para isso ainda): insira uma
  linha em `voice_agents` (status `A`, model `gemini-3.8-live`, voice `Kore`, temperature `0.6`, language `pt-BR`, max_call_seconds `600`)
  e uma linha em `voice_agent_versions` (`number 1`, `status published`, `prompt` = cópia do prompt da versão 1 do agente 1) + copie as linhas de
  `voice_agent_tools` da versão 1 (copie o JSON **cru** de `parameters_schema`; nunca decodifique/recodifique). **Apague o agente de teste ao final**
  (`VoiceAgent::where('id',…)->delete()` — versões/tools caem em cascata) e confira que restam só o agente 1, a versão 1 e as 2 tools.
- Scripts que já existem: `voip/voice-agent/scripts/playground_smoke.py` (cliente headless do Playground; não é necessário no E3).

## 8. Lacunas conhecidas (avise-me se atrapalharem; não resolva por conta própria)

- **Não existe API nem tela para criar/editar/desativar um agente** (só as versões). Se o E3 precisar disso para ficar utilizável, proponha.
- Vozes: `config('voice.studio.voices')` tem 8 vozes Gemini, ainda sem validar qual soa bem em pt-BR.
- O despacho do agente no Playground é intermitente (2 falhas em ~17 sessões, causa não achada) — relevante só para o E4.
- `voice_agents.max_call_seconds` ainda não é aplicado em ligação real (só no Playground).

## 9. Primeira resposta esperada

Um plano curto (até ~15 linhas): confirme o que leu (TODO/estado), liste E3.1–E3.6 com o que provará em cada um, aponte qualquer
divergência entre este prompt e o código real que encontrar, e pergunte só o que for realmente indispensável. Depois **espere meu "ok"**.
