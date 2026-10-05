# Roteiro da apresentação — Rapia Voice V1 (12 minutos)

Base: seções 1 e 11 do `TODO-RAPIA-VOICE-V1.md`. Ambiente de homologação: stack de voz na EC2
(`~/livekit-ec2`), sysapi/sysweb/worker/fila no PC, ngrok `apiflowip.ngrok.app`.

## A. Uma hora antes: conferir o ambiente

| # | O quê | Como conferir | Esperado |
|---|---|---|---|
| 1 | EC2 ligada e VPN conectada | `ssh -i ~/.ssh/srv_ipsys_web_sp ubuntu@172.31.11.133 'cd ~/livekit-ec2 && docker compose ps'` | redis, livekit, sip, asterisk, **egress** `running` |
| 2 | Registro SIP no provedor | `docker compose exec asterisk asterisk -rx 'pjsip show registrations'` | `Registered` |
| 3 | Egress saudável | `curl -s 127.0.0.1:8082` (na EC2) | JSON com `CpuLoad` |
| 4 | ngrok no ar | abrir `https://apiflowip.ngrok.app/api` | resposta do Laravel (não página do ngrok) |
| 5 | API local | `php -S 127.0.0.1:8000` rodando; `http://api.ipsys/api` responde | — |
| 6 | Fila | janela do `php artisan queue:listen --tries=1` aberta e ativa | processa jobs (resumo chega ~25 s após desligar) |
| 7 | Worker de IA | `voip/voice-agent/agent.log` (UTF-16) com `registered worker` recente; `.env` com `VOICE_WORKER_CARGA_FIXA=0` | um par launcher `.venv` + Python311 |
| 8 | CPU do PC | Gerenciador de Tarefas < 70% (fechar IDE/abas pesadas) | IA responde sem atraso |
| 9 | Front | `http://localhost:8080` compilando; login feito; alert "O campo email é obrigatório" só aceitar | — |
| 10 | Massa de dados | `php voip/scripts/massa-demo.php --status` | `{"contatos":5,"contas":5,"sessoes":12,"chamadas":8}` (recriar com `--remover` e `--criar` se as datas ficaram velhas: as chamadas "de hoje" são do dia em que o script rodou) |
| 11 | Filtro de entrada | `sys_parametros` VOICE: `VOICE_NUMEROS_PERMITIDOS` com o celular do prospect **ou** `VOICE_FILTRO_ENTRADA=N` durante a demo | a ligação dele não cai |
| 12 | Versão publicada | Estúdio > agente 1: a versão publicada é a que vai atender; o rascunho v2 (id 58) não deve ser publicado | — |
| 13 | Ligação de teste | ligar do celular de teste: URA, dígito 1, IA atende e avisa a gravação | chamada aparece no Painel; no fim, resumo + gravação na ficha |
| 14 | Presença | abrir o Painel 360 deixa a atendente Disponível | quem vai assumir precisa estar Disponível |
| 15 | Worker sem override de teste | `Get-CimInstance Win32_Process` do `agent.py`: a linha de comando **não** pode ter `VOICE_MAX_CALL_SECONDS_FORCAR` (só existe nos testes); `VOICE_TRANSCRICAO_IDIOMAS` só se o experimento A2 tiver aprovado | ligação real não é cortada aos 70 s |
| 16 | Plano B | vídeo de backup no desktop; 4G roteado; número alternativo | — |

## B. A apresentação (seção 11)

1. **(1 min) O RAPIA hoje.** Mostrar o chat de WhatsApp e o Contato 360 de um paciente da massa
   (ex.: Maria da Silva Souza): histórico de WhatsApp **e** de ligações, com resumo e tags.
2. **(3 min) O prospect liga do celular dele** para +55 84 3190-1994.
   - URA: "digite 1..." -> 1 = IA.
   - A IA cumprimenta, **avisa que a ligação pode ser gravada** e faz a triagem (nome, CPF, nascimento).
   - Enquanto ele ouve o menu, o Painel 360 > "Em curso" mostra a chamada **"Na URA"** (M5.1); depois do dígito
     a mesma linha vira "Com a IA". Se ele desligar no menu, ela vira "Abandonada" ("Desligou na URA").
   - Conferir enquanto ele fala: Painel 360 > "Em curso" mostra a chamada "Com a IA".
3. **(2 min) Painel 360.** Clicar na chamada: transcrição ao vivo, dados extraídos pela IA com o check,
   linha do tempo (aviso de gravação, ferramentas chamadas). Pedir ao prospect: "quero falar com um atendente".
   A IA transfere -> a chamada vai para "Em fila".
4. **(2 min) A atendente assume em um clique** ("Assumir"), o softphone abre, conversa com o prospect.
   Mostrar "Transferir para atendente" (não precisa transferir de fato).
5. **(1 min) Encerramento.** Encerrar pelo softphone: a ficha **fica aberta** com o selo "Encerrada" e a
   duração final; em ~25 s aparece o **resumo e as tags**; em seguida a **gravação** com a transcrição rolando
   junto (clicar num marcador, ex.: "Aviso de gravação"). Mostrar o Contato 360 com a ligação nova ao lado do
   WhatsApp. Abrir o **Dashboard** (Voz > Dashboard): chamadas do dia, TME, % resolvido pela IA, duração
   média, custo estimado (explicar que é estimativa só do Gemini).
6. **(2 min) Estúdio do Agente.** Mudar uma frase da saudação no rascunho, conferir no Playground,
   **publicar**, e pedir ao prospect para ligar de novo e ouvir a mudança.
   - **Depois da demo**: reverter para a versão anterior (Estúdio > Versões > restaurar) e publicar.
7. **(1 min) Roadmap e perguntas**: "o que falta para isso servir na sua operação?" (seção 8 do TODO).

## C. Se algo falhar

| Sintoma | Causa provável | Ação |
|---|---|---|
| Ligação toca e cai / não atende | worker sem despacho (CPU do PC alta, "no servers available") | aliviar a CPU; conferir `VOICE_WORKER_CARGA_FIXA=0`; reiniciar o worker |
| IA atende mas demora muito | CPU do PC, rede da VPN | seguir; se piorar, vídeo de backup |
| Painel não atualiza | `queue:listen` parado (broadcasts) | reabrir a fila |
| Resumo não aparece | fila parada ou Gemini fora | `php artisan voice:resumo <id> --tenant=api` |
| Gravação "falhou" | egress fora ou credencial S3 | `docker compose logs --tail 20 egress` na EC2 |
| "Não foi possível alterar sua disponibilidade" | era o erro intermitente do Apache (config vazia), corrigido em 29/09 com `Env::disablePutenv()` em `sysapi/public/index.php`; se voltar, é outra causa | trocar o seletor de presença de novo e olhar o `laravel.log` |
| Chamada "Na URA" que não some | o Asterisk não avisou o fim (rede) | some sozinha em 3 min (vira Abandonada) |
| A IA avisa que vai transferir e a ligação acaba | `max_call_seconds` da versão publicada (Estúdio > Configurações da sessão) | aumentar o limite ou deixar vazio (sem limite) |

## D. Depois da apresentação

- Reverter a versão do agente se foi publicada uma de demonstração.
- Deixar a presença Indisponível (sair do Painel pela navegação interna).
- Parar a EC2 se não houver outro uso (o Elastic IP continua cobrando).
- Ligações do prospect ficam gravadas (dado pessoal): apagar se ele pedir; retenção atual 90 dias (regra do bucket).

## E. Ensaio (critério de pronto do M5)

A sequência da parte B roda **três vezes seguidas** sem intervenção, e o **vídeo de backup** é gravado numa
dessas execuções (tela do Painel + áudio da ligação).

## F. Vídeo de backup e vídeo de divulgação (guia de produção)

Dois usos, o mesmo material gravado: (1) **backup** da apresentação (plano B se a ligação falhar ao vivo) e
(2) **divulgação** enviada antes aos clientes que já usam o chat do Rapia, para despertar o interesse na demonstração.
Grave **uma vez**, com qualidade, e monte as duas versões a partir das mesmas tomadas.

### F.1 Preparo antes de gravar
1. Checklist da parte A (ngrok, `php -S`, fila, sysweb, worker, EC2 com o Asterisk "Registered").
2. Worker **sem** `VOICE_MAX_CALL_SECONDS_FORCAR` e sem variável de teste ligada no `voice-agent\.env`.
3. Recriar a massa de demonstração, para o Dashboard e o Histórico estarem cheios e as chamadas "de hoje" serem de hoje:
   `php voip\scripts\massa-demo.php --remover` e depois `--criar`.
4. Usar só o **número de teste** e dados fictícios (paciente do ERP Demo). Nunca dados reais de paciente no vídeo.
5. Conferir que o agente publicado é o de demonstração (prompt, voz Leda) e que você está **Disponível** no Painel 360.
6. Navegador em janela limpa: perfil sem extensões visíveis ou modo anônimo, sem favoritos, notificações do sistema
   desligadas (Windows: Assistente de foco), **janela em 1920x1080** e zoom de 100% (ou 110% para o texto ficar legível).
7. Fazer cada cena **3 vezes** e escolher a melhor tomada; gravar também "tomadas de cobertura" (planos curtos para cobrir cortes).

### F.2 Captura: ferramentas gratuitas e configuração
O OBS Studio é gratuito e é a ferramenta recomendada: a má qualidade vem quase sempre de configuração. Descartar o CamStudio.

| Ajuste do OBS | Valor |
|---|---|
| Configurações > Vídeo | Resolução base e de saída 1920x1080, 30 fps |
| Configurações > Saída (modo Avançado) > Gravação | Formato **MKV** (não perde o arquivo se travar; depois Arquivo > Remux para MP4) |
| Codificador | NVENC (Nvidia) ou AMF (AMD) se houver placa dedicada; senão x264 |
| Controle de taxa | CBR, 20.000 a 30.000 kbps |
| Fonte de vídeo | "Captura de Janela" do navegador (ou "Captura de Tela" de um monitor); evitar capturar monitor com resolução diferente da saída |
| Áudio do desktop | Desligado nas tomadas de tela (o som da ligação vem de outra fonte, abaixo) |

Outras fontes de captura, todas gratuitas:
- **Tela do celular do paciente:** gravador de tela nativo do Android/iPhone (modo "Não perturbe" ligado), na cena do "mockup".
- **Áudio da ligação (paciente e IA):** a gravação que o próprio sistema já faz (player na ficha encerrada) é a fonte mais limpa;
  alternativa: gravar o celular em viva-voz com o gravador de voz de outro aparelho, em ambiente silencioso.
- **Narração:** gravada à parte, depois, sobre o vídeo (Audacity, gratuito, ou o gravador do próprio editor), com microfone de
  headset, sala silenciosa, tomadas curtas por trecho. Alternativa: voz sintetizada (Gemini TTS, o mesmo do projeto).
- **Realce do cursor:** o OBS não destaca cliques; usar o realce do próprio editor na pós-produção ou a ferramenta
  PowerToys > Mouse Utilities (gratuito) para destacar o cursor.
Cuidados: mouse devagar e com pouco movimento; clicar e esperar um segundo; não rolar a tela rápido; fechar o que não aparece no vídeo.

### F.3 Edição (gratuita)
- **DaVinci Resolve (gratuito)**: cortes, tela dividida, zoom, legendas e exportação em alta qualidade. Recomendado.
- **CapCut (desktop)**: mais simples de aprender, com legendas automáticas.
- Música: trilha instrumental livre da biblioteca de áudio do YouTube Studio, volume baixo (a voz sempre acima).
- Exportar em MP4 H.264, 1920x1080, 30 fps, 12 a 16 Mbps. Para WhatsApp/e-mail, gerar também uma versão de ~720p abaixo de 25 MB.

### F.4 Roteiro de cenas: versão divulgação (90 a 120 s)

| # | Tempo | Montagem da cena | O que mostrar | Texto na tela / narração |
|---|---|---|---|---|
| 1 | 0–8 s | **Só o mockup do celular do paciente** discando para a clínica | Tela de chamada, fundo neutro | "Quantas ligações sua clínica perde por dia?" |
| 2 | 8–20 s | **Celular em destaque**, ondas de voz | A IA cumprimenta e pede o nome; (opcional) o card "Na URA" | "Atendimento 24 horas, sem fila de espera." |
| 3 | 20–40 s | **Tela dividida:** celular à esquerda, Painel 360 à direita | Transcrição ao vivo e dados aparecendo na ficha (nome, CPF, nascimento) | "Tudo registrado em tempo real." |
| 4 | 40–55 s | **Tela cheia do Painel 360** | Consulta ao ERP Demo (paciente e agenda) respondida pela IA | "Consulta de agenda e exames sem atendente." |
| 5 | 55–70 s | **Tela dividida:** celular e Painel | O paciente pede um humano; o card vai para "Em fila" | "Quando precisa de gente, passa para a pessoa certa." |
| 6 | 70–85 s | **Tela cheia, atendente assume** (softphone) | Clique em Assumir, a IA sai, a atendente fala já com a ficha pronta | "A atendente já sabe tudo. O paciente não repete nada." |
| 7 | 85–100 s | **Ficha encerrada** | Resumo automático, tags, player da gravação com a transcrição sincronizada | "Resumo, gravação e histórico, automáticos." |
| 8 | 100–112 s | **Gestão** | Dashboard (chamadas, tempo de espera, custo por ligação) e o Estúdio do Agente (prompt) | "Você controla o que a IA fala." |
| 9 | 112–120 s | **Fecho** | Logo, contato e a chamada para ação | "Agende uma demonstração." |

### F.5 Versão backup da apresentação
- Uma **tomada contínua e limpa** da sequência da parte B (cenas 2 a 8 acima), sem música e **sem acelerar**, com os tempos reais.
- Grave dentro do ensaio (seção E), na 3ª execução seguida, para provar que o fluxo roda sem intervenção.
- Guardar o arquivo no desktop da apresentação e em uma cópia no celular/pen drive; testar a reprodução offline.

### F.6 Cuidados e lista de verificação final
- Sem dado pessoal real (nome, CPF, telefone, gravação de paciente) visível ou audível; conferir a ficha e o Histórico quadro a quadro.
- Aviso de gravação falado pela IA deve aparecer no vídeo (mostra conformidade com a LGPD).
- Não mostrar chaves, tokens, URLs internas do ngrok/EC2 nem o console do worker.
- Legendas em português em todo o vídeo (muita gente assiste sem som).
- Revisar o áudio da IA: se o telefone distorcer, usar a gravação do sistema.
- Chamada para ação com um único canal de contato.
