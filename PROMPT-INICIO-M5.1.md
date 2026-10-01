## 1. Contexto

Projeto: plataforma de atendimento (clínicas/hospitais/laboratórios). Backend `sysapi` (Laravel 8, PHP 7.4),
frontend `sysweb` (Vue 2.5 + Webpack 3 + Vuex), módulo de voz em `voip/` (SIP + LiveKit + Gemini Live).
Leia `CLAUDE.md` da raiz e **`voip/TODO-RAPIA-VOICE-V1.md`** (fonte da verdade). Leia com atenção: o bloco **"M5 —
Acabamento de demonstração"** inteiro (principalmente "Achados das ligações reais do M5", 124 e 125), a **seção 7.1**
(nota da adaptação do Egress para a EC2), a **seção 7.3** (ambiente EC2; "Não verificado / pendências") e
**`voip/ROTEIRO-APRESENTACAO.md`** (checklist e passo a passo da demonstração de 01/11/2026).

Estado (todos na `main`, **sem push**): M0–M5 commitados. Commits do M5: sysapi `6824809`, sysweb `2b2242ba`. Outras
pessoas também commitam nesses repositórios (há merges por cima): não presuma que os últimos commits do `git log` são
do módulo de voz. `voip/` **não é repositório git** (worker, scripts, TODO, roteiro e este prompt ficam só no disco).

O que o M5 entregou (resumo): ficha da chamada encerrada aberta com selo "Encerrada"; resumo e tags pós-chamada (Gemini
REST `gemini-3.8-flash`; chave versionada `resumo_pos_chamada` S/N por versão do agente); gravação (Egress na EC2, somente
áudio, mono) com player sincronizado; custo estimado do Gemini (conversa + resumo, evento `ai_usage`); Dashboard de voz;
massa de demonstração (`voip/scripts/massa-demo.php`); ferramenta de ligação de teste sem telefone
(`voice-agent/scripts/chamada_teste.py`). Correções vindas das ligações reais: o agente sai da sala quando a atendente
assume (`ai_left`) e, transferida para a fila, a IA para de ouvir (`ai_waiting`).

**Sua tarefa: M5.1 — fechamento e robustez da demonstração** (seção 6). Fica de fora: M4.4 fase 2 (transferência
automática), M4.5 (WhatsApp Calling), provas reais antigas M4.1–M4.3 e adapter do ERP real (seção 8).

## 2. Como trabalhar (regras do usuário — obrigatórias)

1. **Comece devolvendo um PLANO curto** (os blocos, o que vai provar em cada um, divergências achadas no código, e as
   decisões que precisa de mim) e **espere o "ok" só desta vez**.
2. Depois do "ok", **execute em sequência, sem pedir autorização para passar ao seguinte**. Ao fim de cada bloco: rode as
   provas possíveis, atualize o TODO (item + detalhes técnicos que só apareceram na implementação) e siga. **Pare e
   pergunte apenas quando for necessário**: ligação real, login no navegador, credencial/ação na AWS, publicar versão do
   agente, rotação de segredo, decisão de produto que o TODO não fecha, ou algo do prompt/TODO errado diante do código.
3. Se algo deste prompt ou do TODO estiver errado diante do código real, **avise e proponha o ajuste**; não obedeça cegamente.
4. **Commit só no fim**: mostre o resumo, os arquivos por repositório e as mensagens, e **peça a autorização uma vez** (um
   commit por repositório afetado). Nenhum commit no meio.
5. **Git**: nunca `git push`; sempre na `main`, nunca criar branch. Só `git add` de arquivos específicos (há trabalho de
   outras pessoas na árvore: confira `git status` e não leve o que não é seu). Commits terminam com as linhas de
   co-autoria que o ambiente indicar. **No PowerShell 5.1, mensagem de commit com aspas duplas quebra**: grave a mensagem
   num arquivo do scratchpad e use `git commit -F <arquivo>` (no Bash funciona igual).
6. Respostas em português do Brasil, curtas. Sem emojis. Não criar documentos que não foram pedidos.
7. **Nunca digite senha nem faça login por mim.** Para testar no navegador: abra `http://localhost:8080/login` e me peça
   para logar. Depois do login pode aparecer um `alert` "O campo email é obrigatório": só aceitar.
8. **Ligação real só com minha autorização**, sempre do/para o meu celular de teste (**+55 84 98834-5243**, contato 1
   "JOAO SOUSA"). Eu atendo e falo; você confere eventos e log. Recusar a ligação no meu celular cai na caixa postal.
9. **Nunca publique versão do agente** sem eu pedir. A v1 publicada do agente 1 atende as ligações reais; o rascunho v2
   (id 58) tem a regra "Ligação com dificuldade" do M4.4 e **não** deve ser publicado nem descartado.
10. **Segredos**: não exiba valores de chave/token (nem em `cat`, `grep` ou `tail` de `.env`: confira só presença, tamanho
    e formato). Copiar entre `.env` sem exibir é autorizado. Quando eu precisar colocar um segredo novo, eu edito o `.env`
    e você só valida o formato.
11. Antes de terminar: nenhum processo `agent.py` órfão (só o par launcher `.venv` + filho Python311), dados de teste
    limpos (a massa de demonstração `[DEMO]` e as ligações reais 124/125 ficam) e **minha presença de voz Indisponível**
    (abrir o Painel 360 me marca Disponível: saia pela navegação interna e confira `users.voice_status` do id 9 = 2).

## 3. Ambiente (homologação na EC2 — já no ar)

- **LiveKit, LiveKit SIP, Redis, Asterisk e Egress rodam na EC2** (`sa-east-1`, IP privado `172.31.11.133`, Elastic IP
  `54.20.82.110`, acesso pela OpenVPN; SSH `ssh -i ~/.ssh/srv_ipsys_web_sp ubuntu@172.31.11.133`, stack em `~/livekit-ec2`,
  pacote em `voip/livekit-ec2/`). O egress sobe pelo perfil `gravacao` (`COMPOSE_PROFILES=gravacao` no `.env` de lá);
  depois de mudar a config: `./scripts/render-config.sh` e `docker compose restart egress` (o `up -d` não recria).
  sysapi, sysweb, worker e fila rodam no PC; EC2 -> PC pelo ngrok `apiflowip.ngrok.app` (webhooks do LiveKit e `CURL()` do
  dialplan). **Não rode `voip/iniciar.ps1`** (sobe o Asterisk local = 2º registro no provedor).
- **Worker de IA** (`voip/voice-agent/agent.py` + `qualidade.py`): `agent.py dev` numa janela própria; PID em
  `voip/.agente.pid`; log `voip/voice-agent/agent.log` em **UTF-16** (`iconv -f UTF-16 -t UTF-8`). **Não recarrega
  sozinho**: reiniciar = matar a árvore do PID do arquivo + órfãos `agent.py` e subir
  `powershell -NoExit -Command "& '<voice-agent>\.venv\Scripts\python.exe' agent.py dev 2>&1 | Tee-Object -FilePath agent.log"`
  com `-WorkingDirectory` no `voice-agent`, gravando o novo PID; conferir `registered worker` no log. No `voice-agent/.env`
  (só homologação): `VOICE_WORKER_CARGA_FIXA=0` e `VOICE_QUALITY_GUARD_FORCAR=sombra`. Jobs são **threads** do processo
  (Windows). Eventos que o worker publica: `audio_quality*`, `comprehension_miss`, `ai_session`, `ai_usage`, `ai_waiting`,
  `ai_left`.
- Fila: `php artisan queue:listen --tries=1` numa janela própria (broadcasts, resumo e jobs dependem dela). **Depois de
  mudar o `sysapi/.env`, reinicie o `queue:listen`.** API: `php -S 127.0.0.1:8000` (uma requisição por vez) e
  `http://api.ipsys/api` (Apache do WAMP, o que worker e front usam). Front: `http://localhost:8080` (hot reload; para
  conferir compilação: `curl -s http://localhost:8080/app.js | grep -c "Module build failed"`). Tenant `api` -> banco
  `ipsys-rapia`. **Hot reload não troca componente já montado nem componente novo**: recarregue a página (F5) antes de
  julgar que a mudança "não funcionou".
- **CLI/tinker usa o banco `ipsys`, não o do tenant.** Em scripts PHP de teste, replique o `CheckSubDomain`:
  ```php
  $d = App\Models\SysConnect::where('subdominio','api')->first();
  config(['database.connections.'.$d->db_instancia => ['driver'=>'mysql','host'=>$d->db_host ?? env('DB_APP_HOST'),'database'=>$d->db_instancia,'username'=>$d->db_usr ?? env('DB_APP_USER'),'password'=>$d->db_pwd ?? env('DB_APP_PWD'),'charset'=>'utf8mb4','collation'=>'utf8mb4_unicode_ci','prefix'=>'','strict'=>false]]);
  config(['database.default' => $d->db_instancia]);
  session(['instancia_subdominio' => 'api']);
  ```
  Bootstrap: `chdir('<sysapi>'); require 'vendor/autoload.php'; $app = require 'bootstrap/app.php';
  $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();`. Controllers podem ser chamados direto com
  `Request::create(...)` + `setUserResolver` (usuário 9 "ADMIN SYS", único SUPER). Prefira transação desfeita.
- Consultas rápidas: `C:\wamp64\bin\mysql\mysql8.0.27\bin\mysql.exe --no-defaults -uroot --default-character-set=utf8mb4
  ipsys-rapia` (`--no-defaults` obrigatório; SQL com `$` ou aspas: heredoc no Bash). Migrations: só as do módulo, apenas no
  `ipsys-rapia`, com a checagem `rapia` do `CLAUDE.md`, nunca `migrate:all`, sem seeders.
- **Ligação de teste sem telefone**: `voice-agent/scripts/chamada_teste.py` (`--roteiro quick|full|compreensao`,
  `--segurar N`, `--insistir N`, `--cortar-apos N`, `--remover SALA`). Cria a sala `call-api_849990000NN_*`, despacha o
  agente publicado e "fala" com o TTS local; webhooks, `voice_calls`, gravação e resumo são os reais. Não passa pela URA
  nem pelo filtro (são do Asterisk). Limitação: o `--remover` apaga só as linhas do banco, **não o arquivo da gravação no
  S3** (limpe com `Storage::disk('voz_gravacoes')->delete($s3_key)` antes de apagar `voice_recordings`; pequena melhoria
  aceita). O paciente sintético fala com TTS limpo: **não reproduz o problema de transcrição do telefone** (bloco A2).
- **Chrome**: o automatizado não tem microfone. Crie uma aba nova (`tabs_context_mcp` + `tabs_create_mcp`), peça meu login e
  navegue pelo roteador interno (`[...document.querySelectorAll('*')].find(e => e.__vue__).__vue__.$root.$router.push('/voice/painel')`).
  A captura de rede da extensão falhou nesta máquina: prove pelo banco.
- **CPU do PC**: com navegador/IDE pesados a carga passa de 0,9. Se algo de voz falhar sem motivo, meça a carga antes de depurar.

## 4. Decisões já tomadas (não reabrir)

- **Credencial S3 — NÃO mexer nesta fase.** Hoje o egress (escrita) e o Laravel (URL assinada) usam a **mesma** chave, e ela
  não é restrita ao prefixo `voz/gravacoes/`. Funciona e está registrada como pendência de segurança (TODO, bloco M5 >
  "Gravação", e a memória do projeto): a correção (dois usuários IAM, cada um só no prefixo) fica para antes de um piloto
  real. Não crie, não troque e não teste permissões dessas chaves; se algo do S3 parecer exigir mudança, **avise e pergunte**.
- Gravação: somente áudio, OGG, **mono** (`DEFAULT_MIXED`), URL assinada de 15 min, player só para SUPER, retenção de 90
  dias no prefixo (provisória; a definitiva é decisão antes de piloto).
- Custo: é **estimativa** e só do Gemini (conversa + resumo); preços e cotação em `config/voice.php`.
- Resumo pós-chamada: ligado por padrão; por agente/versão (`resumo_pos_chamada`). Tags de transferência/retorno/WhatsApp/
  áudio saem só dos eventos, nunca da IA.
- Ficha da chamada encerrada fica aberta (selo "Encerrada" + "Fechar").
- Nada de M4.4 fase 2, M4.5, publicar o rascunho v2 (id 58) ou mexer no prompt do agente publicado.

## 5. Dados de teste e cuidados

- Ligações reais 89, 101, 103–107, 124 e 125 são registro real — não apague (pode reprocessar resumo/tags:
  `php artisan voice:resumo <ids> --tenant=api`).
- Massa de demonstração `[DEMO]` (`php voip/scripts/massa-demo.php --status`: 5 contatos, 12 sessões de WhatsApp, 8 chamadas):
  fica. As chamadas "de hoje" são do dia em que o script rodou; recriar (`--remover` + `--criar`) só no dia do ensaio.
- Filtro de entrada (`sys_parametros` VOICE: `VOICE_FILTRO_ENTRADA`=S, `VOICE_NUMEROS_PERMITIDOS` com o meu celular); URA sempre
  ativa na homologação; dígito 1 = IA (agente 1), 2 = fila. Chamadas de teste sem telefone gravam no S3 e chamam o Gemini
  (centavos): limpe ao fim.

## 6. Escopo e ordem (seguir sem parar entre os blocos; parar só no que exigir intervenção)

**Bloco A — Robustez da demonstração** (riscos que podem aparecer na frente do prospect)
1. **A1. Erro intermitente do Apache (config vazia).** O log `sysapi/storage/logs/laravel.log` tem "LIVEKIT_API_KEY/LIVEKIT_API_SECRET
   não configurados (.env)" desde 25/09, intermitente, ligado a requisições simultâneas; em 26/09 a troca de presença ao
   sair do Painel falhou e `users.voice_status` ficou 1. Hoje há só um paliativo no front (nova tentativa em
   `definirPresenca`). Investigue a causa (qual rota lançou, stack trace no log, handler do PHP no Apache do WAMP: ZTS/
   mod_php x FastCGI, `env()` lido de dentro de `config/*.php` em thread) e proponha a correção; reproduzir com
   requisições paralelas. Hipótese **não verificada**: `env()`/`getenv` não é seguro entre threads. `config:cache` foi
   descartado no TODO por quebrar `env()` fora de `config/`: confirme antes de descartar de vez.
2. **A2. Transcrição do paciente pelo telefone troca português por espanhol** ("¿Qué?", "Sí. Sí.", "Eso es") e "50 centavos do
   2,90" no lugar da data; apareceu nas duas ligações reais do M5 (gerou `comprehension_miss` e a tag "Dificuldade de
   áudio"). O agente já passa `language` pt-BR. Confira no plugin `livekit-plugins-google` 1.8.2 e no `google-genai`
   instalados quais opções o Gemini Live aceita para idioma da fala/transcrição de entrada (não presuma nomes) e o que o
   prompt pode reforçar. **Só ligação real prova**: proponha um experimento curto (2–3 ligações, mesmo roteiro, uma variável
   por vez) e me peça as ligações. Não publique versão para testar: use o rascunho no Playground ou a variável de ambiente
   do worker, como no M4.4.
3. **A3. Rotação de segredos** (peça meu OK antes de começar): `URA_API_TOKEN`/`VOICE_WORKER_TOKEN` (mesmo valor; apareceu em
   resultado de ferramenta em 25/09) em `sys_parametros`, `voice-agent/.env` e `.env` da EC2 (render + `dialplan reload`).
   A chave do Gemini (`VOICE_GEMINI_API_KEY` = `GOOGLE_API_KEY` do worker) também apareceu em resultado de ferramenta em
   27/09: rotacionar no AI Studio é comigo; você troca nos dois `.env` sem exibir e reinicia worker e `queue:listen`.
   **Não inclui as credenciais S3** (seção 4).
4. **A4. `max_call_seconds` em ligação real.** O Playground aplica o limite; ligação real não. Proponha o comportamento (ex.:
   valer só enquanto a IA está na sala, avisar o paciente e transferir/encerrar) e peça minha decisão antes de implementar.

**Bloco B — Decisão: "Na URA" no Painel 360.** Observação minha (27/09): enquanto o paciente está no menu da URA ele não
aparece em nenhuma lista do Painel, só depois do dígito. Causa (já no TODO): a sala do LiveKit só nasce depois do dígito.
Desenho a avaliar: o dialplan avisa o RAPIA na entrada (já existe `CURL()` do filtro de números nesse ponto), status novo em
`voice_calls`, e casar esse registro com a sala criada depois (número + horário); e o que acontece se o paciente desligar
na URA. **Não implemente sem minha decisão**: apresente as opções, esforço e risco no plano e pergunte.

**Bloco C — Provas que dependem de mim** (deixe tudo pronto e me peça)
1. Uma ligação real curta confirmando que, transferida para a fila, a IA fica calada até eu assumir e sai quando assumo (hoje
   só provado sem telefone).
2. Ensaio da demonstração **três vezes seguidas** e **vídeo de backup** (`voip/ROTEIRO-APRESENTACAO.md`, seção E). Atualize o
   roteiro se algo do bloco A/B mudar o passo a passo.

Critério de pronto: blocos A e B resolvidos ou com decisão registrada, C pronto para eu executar, TODO atualizado, commits
únicos por repositório autorizados no fim.

## 7. Pequenas melhorias aceitas no caminho (se sobrar tempo, sem parar por elas)

- `chamada_teste.py --remover` apagar também o arquivo da gravação no S3.
- Erro do resumo (`summary_meta.erro`) visível no Histórico com um botão "Gerar de novo" (hoje só `php artisan voice:resumo`).

## 8. Fica para depois (não faz parte desta sessão)

M4.4 fase 2 (transferência automática por qualidade; espera mais ligações em sombra e decisão minha); M4.5 (estudo do WhatsApp
Calling); provas reais M4.1–M4.3 (memória do projeto); M4.2 (sessão nova de WhatsApp com envio real, resposta do paciente,
botão "Enviar p/ WhatsApp"); caixa postal contada como atendida no discador (AMD ou botão); ramais pela EC2 (AMI pela VPN +
sincronizar `pjsip_ramais.conf`); tela/API para criar e editar agentes; escuta silenciosa do supervisor; adapter do ERP real
(falta definir cliente-alvo e ERP); retenção definitiva das gravações; **restrição das credenciais S3** (seção 4).

## 9. Primeira resposta esperada

Um plano curto (até ~25 linhas): confirme o que leu (TODO/estado), liste os blocos A1–A4, B e C com o que provará em cada um e
onde vai precisar de mim (login, ligações, decisões); traga as **perguntas de decisão** (A4 e B) já com sua recomendação;
aponte divergências entre este prompt e o código real e **espere meu "ok"**. Depois disso, siga até o fim parando só no que
exigir intervenção.
