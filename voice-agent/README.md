# Agente de voz (teste) — Gemini Live + LiveKit Agents

Worker Python que atende a ligação que chega pelo tronco SIP, dá boas-vindas,
coleta **nome, CPF e data de nascimento** (um de cada vez), repete os três e
avisa que vai transferir para um atendente humano.

É a primeira peça do cenário 2 da análise: prova a conversa em pt-BR, a coleta de
dados por telefone e a chamada de ferramentas (function calling).

```
voip/voice-agent/
├── agent.py           -> mecânica (sessão, ferramentas, logs)
├── prompt.md          -> o prompt base, em português: edite aqui
├── .env.example       -> copiar para .env
├── requirements.txt
├── scripts/dispatch.py-> alterna a dispatch rule entre "teste" e "agente"
└── coletas.jsonl      -> dados coletados em cada ligação (gerado)
```

## 1. Instalação (uma vez)

```powershell
cd C:\wamp64\www\Infoprime\rapia\voip\voice-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Copy-Item .env.example .env
notepad .env        # GOOGLE_API_KEY (obrigatório) e CLINICA_NOME
```

As chaves `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` já vêm preenchidas com as do
`voip\livekit-local\.env`. Se você regerar as chaves do LiveKit, copie de novo.

A chave do Gemini sai do [Google AI Studio](https://aistudio.google.com/apikey).

## 2. Rodar

Com a stack do LiveKit de pé (`voip\livekit-local`):

```powershell
.\.venv\Scripts\python.exe agent.py dev
```

Deve aparecer `registered worker {"agent_name": "rapia-voice", ...}`. O aviso de
que o modo `dev` está obsoleto é inofensivo (a alternativa é `lk agent dev`).

Enquanto o worker roda, ele mostra no console a transcrição da conversa, as
ferramentas chamadas e os dados coletados.

## 3. Mandar as ligações para o agente

Por padrão a dispatch rule joga toda chamada na sala fixa `teste-sip`, sem agente.
Para passar a despachar a IA:

```powershell
.\.venv\Scripts\python.exe scripts\dispatch.py agente    # uma sala "call-*" por chamada + IA
.\.venv\Scripts\python.exe scripts\dispatch.py teste     # volta ao modo sem IA
.\.venv\Scripts\python.exe scripts\dispatch.py listar    # mostra trunks e regras
```

Ligue para o número da central. O worker recebe o job, o Gemini atende e a
conversa aparece no console.

> Com a regra em modo `agente` e o worker **parado**, a chamada entra na sala e
> ninguém atende. Suba o worker antes de ligar.

## 4. Ouvir a ligação pelo navegador (opcional)

O nome da sala (`call-...`) aparece no log do worker. Gere um token para ela e
entre pelo softphone de teste — é assim que a atendente vai assumir a ligação
depois da triagem:

```powershell
cd ..\livekit-local
.\scripts\token.ps1 -Room call-xxxxxxxx -Identity atendente1 | Set-Clipboard
# abra http://localhost/Infoprime/rapia/voip/livekit-local/test/atendente.html
```

## 5. Ajustar o comportamento

- **O que o agente fala e pergunta:** `prompt.md`. Basta salvar e reiniciar o worker.
- **Voz:** `GEMINI_VOICE` no `.env` (Kore, Puck, Charon, Aoede...).
- **Modelo:** `GEMINI_MODEL`. Padrão `gemini-3.8-live`; use
  `gemini-3.8-live-extended-thinking` se precisar de mais raciocínio, ao custo de
  resposta mais lenta.
- **Ferramentas:** em `agent.py`. Hoje há duas:
  - `registrar_dados_paciente(nome, cpf, data_nascimento)` — valida o dígito
    verificador do CPF, grava em `coletas.jsonl` e, se o CPF não conferir, devolve
    `cpf_invalido` para o agente pedir de novo;
  - `transferir_para_atendente()` — por enquanto só registra no log. É aqui que,
    depois, entra a chamada à API do RAPIA (enfileirar + avisar o Painel 360).

## 6. Pontos de atenção neste teste

- **CPF falado por telefone erra.** Onze dígitos em áudio de 8 kHz é o caso mais
  difícil. Por isso a validação do dígito verificador está na ferramenta. Na
  próxima etapa vale aceitar o CPF por DTMF (teclado do telefone).
- **Custo:** cada minuto de conversa consome tokens de áudio do Gemini. Acompanhe
  o uso no console do Google durante os testes.
- **Dados de saúde:** a partir do momento em que houver dado real de paciente,
  valem as exigências de LGPD descritas na análise (aviso de gravação, base legal,
  contrato com o provedor, retenção). Nos testes, use dados fictícios.
- **Estado do agente é por ligação.** Nada é persistido além do `coletas.jsonl`.
