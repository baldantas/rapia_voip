# Teste diagnóstico do Asterisk na EC2 (M2.5)

**Quando rodar:** só depois de concluído o M2.5 (tarefa registrada no fim do
bloco M2.5 em `voip/TODO-RAPIA-VOICE-V1.md`).

## Por que este teste existe

No ambiente local (Docker Desktop no Windows), quando o **próprio Asterisk
atende** a ligação e toca áudio (a URA), o relay de mídia do provedor
(`52.67.163.135`) **não envia nenhum pacote de áudio**. Quando quem atende é a
**ponte com o LiveKit** (fluxo direto para a IA), funciona. Foram 10 ligações
reais em 24/09/2026, com tcpdump no container e pktmon no Windows. A sinalização
SIP é idêntica nos dois casos. A única anomalia de rede que sobrou é o Docker
Desktop trocar a porta de origem (SDP diz `20024`, o pacote sai por `61845`) e
mascarar a origem de quem entra (`172.30.0.1`). Isso acontece tanto em bridge
quanto no "host networking" do Docker Desktop, e não dá para eliminar no
Windows.

Aqui o Asterisk roda num Linux de verdade, com `network_mode: host`, na mesma
região da AWS do relay do provedor (sa-east-1). **Só o Asterisk**: sem LiveKit,
sem Laravel.

| Resultado | Conclusão |
|---|---|
| Ouve a URA, o dígito é reconhecido e o eco funciona | A causa era a rede local (NAT do Docker Desktop). Decidir onde o Asterisk vai morar (nuvem) |
| Mudo como no local | O problema é do provedor, e o chamado com ele vira prioridade (evidências no TODO) |

## Pré-requisitos (antes de subir)

1. **Autorização** para rodar um container a mais no servidor de produção.
2. **Security Group** da EC2, regras de **entrada**, liberadas **só** para o
   provedor. **Nunca `0.0.0.0/0`**: há tentativas de fraude SIP na internet o
   tempo todo.
   - UDP 5060 → origem `52.67.163.135/32`
   - UDP 20000-20099 → origem `52.67.163.135/32`
   - (a saída já costuma ser liberada por padrão)
3. **Nada escutando nessas portas** no servidor:
   `sudo ss -lunp | grep -E ':5060|:200[0-9][0-9]'` → deve voltar vazio.
4. Docker + Compose v2 instalados (`docker compose version`) e o `envsubst`
   (`sudo apt-get install -y gettext-base`).
5. **Parar o Asterisk local**. A conta do provedor aceita um registro por vez;
   se os dois registrarem, a ligação vai para quem registrou por último. No PC:
   `cd voip\livekit-local ; docker compose stop asterisk`

## Subir

```bash
# copiar a pasta voip/teste-ec2 para o servidor, por ex. em ~/rapia-voz-teste
cd ~/rapia-voz-teste
cp .env.example .env
nano .env            # PUBLIC_IP = Elastic IP; SIP_PASSWORD = mesma do voip/livekit-local/.env
bash render.sh
docker compose up -d
docker compose exec asterisk asterisk -rx "pjsip show registrations"   # precisa: Registered
```

## Testar (1 ligação)

Em outro terminal, capture a mídia (é o que dá a resposta objetiva):

```bash
sudo tcpdump -n -i any "udp portrange 20000-20099 and host 52.67.163.135" -w /tmp/rtp-ec2.pcap
```

Ligue para **84 3190-1994** e siga:

1. **Ouviu a voz da URA?** (anote)
2. Aperte **qualquer dígito**: o prompt deve **recomeçar** (prova que o DTMF chegou)
3. Depois do prompt entra o **eco**: fale e você deve **ouvir a própria voz**
4. Desligue e pare o tcpdump (Ctrl+C)

Contagem de pacotes, **sem precisar abrir o pcap**:

```bash
sudo tcpdump -n -r /tmp/rtp-ec2.pcap "src host 52.67.163.135" | wc -l   # recebidos do provedor
sudo tcpdump -n -r /tmp/rtp-ec2.pcap "dst host 52.67.163.135" | wc -l   # enviados ao provedor
```

No ambiente local, a primeira contagem dá **0** nas ligações que falham.

## Desfazer (sempre, ao terminar)

```bash
docker compose down
docker image rm andrius/asterisk:latest      # opcional
rm -rf ~/rapia-voz-teste /tmp/rtp-ec2.pcap   # o .env tem a senha SIP
```

- Remover as duas regras do Security Group.
- No PC: `cd voip\livekit-local ; docker compose start asterisk` e conferir
  `.\scripts\asterisk.ps1 registro` (precisa: Registered).
