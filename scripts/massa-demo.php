<?php
/**
 * Massa de dados fictícia da demonstração (M5, ponto 6) - tenant "api" (banco ipsys-rapia).
 *
 *   php voip/scripts/massa-demo.php --status
 *   php voip/scripts/massa-demo.php --criar      (recusa se já existir; use --remover antes)
 *   php voip/scripts/massa-demo.php --remover
 *
 * Por que script e não migration: migration roda em qualquer banco "rapia" (inclusive o de um
 * cliente real); isto é só para a instância da demonstração.
 *
 * O que cria (tudo identificável):
 *  - 5 contatos = os pacientes do ERP Demo (VoiceDemoErpController::PACIENTES), com conta de
 *    WhatsApp; contacts.obs = MARCA, accounts.account_origem = MARCA.
 *  - 2 a 3 sessões de WhatsApp encerradas por paciente (protocol "DEMO..."), com mensagens.
 *  - 8 chamadas de voz encerradas (room_name "call-api_{numero}_DEMO{8}"), com transcrição,
 *    triagem, eventos (tools, aviso de gravação, qualidade), fila/atendente quando houve,
 *    uso do Gemini (evento ai_usage com payload.demo=true) -> custo, e resumo/tags gerados pelo
 *    serviço real (VoiceSummaryService, chama o Gemini: alguns centavos).
 * A agenda vem do próprio ERP Demo (datas relativas a hoje): nada a criar.
 */

const MARCA = '[DEMO-M5] massa de demonstração';
const ORIGEM = 'DEMO-M5';

chdir(__DIR__ . '/../../sysapi');
require 'vendor/autoload.php';
$app = require 'bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Rapia\VoiceCall;
use App\Models\Rapia\VoiceCallEvent;
use App\Models\Rapia\VoiceQueueEntry;
use App\Models\Rapia\VoiceTranscript;
use App\Services\Voice\VoiceCostService;
use App\Services\Voice\VoiceSummaryService;
use Carbon\Carbon;
use Illuminate\Support\Facades\DB;

$d = App\Models\SysConnect::where('subdominio', 'api')->first();
config(['database.connections.' . $d->db_instancia => ['driver' => 'mysql', 'host' => $d->db_host ?? env('DB_APP_HOST'), 'database' => $d->db_instancia, 'username' => $d->db_usr ?? env('DB_APP_USER'), 'password' => $d->db_pwd ?? env('DB_APP_PWD'), 'charset' => 'utf8mb4', 'collation' => 'utf8mb4_unicode_ci', 'prefix' => '', 'strict' => false]]);
config(['database.default' => $d->db_instancia]);
session(['instancia_subdominio' => 'api']);
if (strpos($d->db_instancia, 'rapia') === false) {
    exit("Banco {$d->db_instancia} não é do RAPIA.\n");
}

$acao = $argv[1] ?? '--status';
$USUARIO = 9; // atendente das sessões/chamadas fictícias (ADMIN SYS)

function status(): array
{
    return [
        'contatos'  => DB::table('contacts')->where('obs', MARCA)->count(),
        'contas'    => DB::table('accounts')->where('account_origem', ORIGEM)->count(),
        'sessoes'   => DB::table('sessions')->where('protocol', 'like', 'DEMO%')->count(),
        'chamadas'  => DB::table('voice_calls')->where('room_name', 'like', 'call-api\_%\_DEMO%')->count(),
    ];
}

function remover(): void
{
    DB::transaction(function () {
        $chamadas = DB::table('voice_calls')->where('room_name', 'like', 'call-api\_%\_DEMO%')->pluck('id');
        foreach (['voice_transcripts', 'voice_call_events', 'voice_queue_entries', 'voice_callbacks', 'voice_recordings'] as $t) {
            DB::table($t)->whereIn('call_id', $chamadas)->delete();
        }
        DB::table('voice_calls')->whereIn('id', $chamadas)->delete();

        $sessoes = DB::table('sessions')->where('protocol', 'like', 'DEMO%')->pluck('id');
        DB::table('messages')->whereIn('session_id', $sessoes)->delete();
        DB::table('sessions')->whereIn('id', $sessoes)->delete();

        $contatos = DB::table('contacts')->where('obs', MARCA)->pluck('id');
        // chamadas reais feitas durante a demo que caíram num contato fictício ficam, sem o vínculo
        DB::table('voice_calls')->whereIn('contact_id', $contatos)->update(['contact_id' => null]);
        DB::table('contacts')->whereIn('id', $contatos)->delete();
        DB::table('accounts')->where('account_origem', ORIGEM)->delete();
    });
}

if ($acao === '--status') {
    echo json_encode(status()), "\n";
    exit(0);
}
if ($acao === '--remover') {
    remover();
    echo 'removida: ', json_encode(status()), "\n";
    exit(0);
}
if ($acao !== '--criar') {
    exit("Uso: --status | --criar | --remover\n");
}
if (array_sum(status()) > 0) {
    exit('Já existe massa de demonstração: ' . json_encode(status()) . ". Rode --remover antes.\n");
}

// ------------------------------------------------------------------ contatos + WhatsApp
$pacientes = App\Http\Controllers\Rapia\Voice\VoiceDemoErpController::PACIENTES;
$contatos = [];
$assuntosWhats = [
    ['Olá, gostaria de saber o horário de funcionamento do laboratório.', 'Olá! O laboratório funciona de segunda a sexta, das 6h às 17h, e aos sábados das 6h às 11h.'],
    ['Preciso de jejum para o exame de sangue?', 'Para hemograma não é obrigatório; para glicemia e colesterol, 8 a 12 horas de jejum.'],
    ['Meu resultado já saiu?', 'Sim! O resultado já está disponível no portal do paciente. Enviamos o link por aqui.'],
    ['Vocês atendem o plano Coopab?', 'Atendemos sim, os planos Coopab Essencial e Coopab Plus.'],
    ['Quero remarcar minha consulta.', 'Claro! Temos horários na próxima terça às 10h ou quinta às 15h. Qual prefere?'],
];

DB::transaction(function () use ($pacientes, &$contatos, $assuntosWhats, $USUARIO) {
    foreach ($pacientes as $i => $p) {
        $numero = ltrim($p['phone'], '+');           // 5584999990001
        $conta = DB::table('accounts')->insertGetId([
            'channel_type_id' => 1, 'number_code' => '55', 'account' => $numero, 'account_origem' => ORIGEM,
            'created_at' => now(), 'updated_at' => now(),
        ]);
        $contatos[$p['id']] = DB::table('contacts')->insertGetId([
            'type' => 1, 'account' => $conta, 'name' => mb_strtoupper($p['name']), 'number_code' => '55',
            'number' => substr($numero, 2), 'cpf' => $p['cpf'], 'nascimento' => $p['birth_date'],
            'obs' => MARCA, 'erp_code' => (string) $p['id'], 'created_at' => now(), 'updated_at' => now(),
        ]);

        // 2 ou 3 atendimentos de WhatsApp nas últimas semanas
        for ($s = 0; $s < 2 + ($i % 2); $s++) {
            $inicio = Carbon::now()->subDays(3 + $s * 6 + $i)->setTime(9 + $s * 2 + $i % 3, 10 * $i);
            [$pergunta, $resposta] = $assuntosWhats[($i + $s) % count($assuntosWhats)];
            $sessao = DB::table('sessions')->insertGetId([
                'protocol' => 'DEMO' . $inicio->format('ymd') . str_pad($i * 10 + $s, 4, '0', STR_PAD_LEFT),
                'channel_id' => 1, 'account_id' => $conta, 'type' => 'C', 'type_start' => 'I', 'user_id' => $USUARIO,
                'dthr_start' => $inicio, 'dthr_last_incoming' => $inicio->copy()->addMinutes(1),
                'dthr_fim' => $inicio->copy()->addMinutes(6), 'created_at' => $inicio, 'updated_at' => $inicio,
            ]);
            $msgs = [['I', $pergunta, 0], ['O', $resposta, 2], ['I', 'Obrigado(a)!', 4]];
            foreach ($msgs as [$tipo, $texto, $min]) {
                DB::table('messages')->insert([
                    'session_id' => $sessao, 'user_id' => $tipo === 'O' ? $USUARIO : null, 'type_msg' => $tipo,
                    'type_receptor' => 'C', 'message' => $texto, 'message_type' => 'text', 'msg_status' => 'read',
                    'dthr_received' => $tipo === 'I' ? $inicio->copy()->addMinutes($min) : null,
                    'dthr_sent' => $tipo === 'O' ? $inicio->copy()->addMinutes($min) : null,
                ]);
            }
        }
    }
});
echo 'contatos e WhatsApp: ', json_encode(status()), "\n";

// ------------------------------------------------------------------ chamadas de voz
$SAUDACAO = 'Olá, bem-vindo à Clínica Coopab. Esta ligação pode ser gravada para fins de atendimento. Por favor, qual é o seu nome completo?';
$cenarios = [
    ['pac' => 1001, 'dias' => 0, 'hora' => '08:42', 'dur' => 96, 'dir' => 'inbound', 'fim' => 'ia', 'tools' => ['registrar_triagem', 'buscar_paciente'], 'snr' => 22.4, 'falas' => [
        ['patient', 'Meu nome é Maria da Silva Souza.'], ['ai', 'Obrigado, Maria. Pode me informar seu CPF?'],
        ['patient', 'Cinco dois nove, nove oito dois, dois quatro sete, dois cinco.'], ['ai', 'Encontrei seu cadastro. Como posso ajudar?'],
        ['patient', 'Queria confirmar minha consulta com a cardiologista.'], ['ai', 'Sua consulta com a Dra. Helena Prado está marcada para daqui a três dias, às nove e meia. Precisa de mais alguma coisa?'],
        ['patient', 'Não, era só isso. Obrigada.'], ['ai', 'Por nada, Maria. Tenha um bom dia!']]],
    ['pac' => 1002, 'dias' => 0, 'hora' => '09:15', 'dur' => 214, 'dir' => 'inbound', 'fim' => 'humano', 'fila_s' => 38, 'tools' => ['registrar_triagem', 'transferir_para_atendente'], 'snr' => 17.9, 'falas' => [
        ['patient', 'João Pedro Almeida.'], ['ai', 'Obrigado, João. Qual o motivo da sua ligação?'],
        ['patient', 'Preciso remarcar meu retorno da ortopedia, surgiu uma viagem.'], ['ai', 'Entendi. Vou transferir você para um atendente, que vai verificar os horários disponíveis. Um momento, por favor.']]],
    ['pac' => 1003, 'dias' => 0, 'hora' => '10:03', 'dur' => 71, 'dir' => 'inbound', 'fim' => 'ia', 'tools' => ['registrar_triagem', 'enviar_whatsapp'], 'snr' => 24.1, 'falas' => [
        ['patient', 'Ana Beatriz Costa.'], ['ai', 'Olá, Ana. Como posso ajudar?'],
        ['patient', 'Queria saber se o resultado do meu exame de sangue já saiu.'], ['ai', 'Posso enviar as orientações para acessar o resultado pelo WhatsApp. Pode ser?'],
        ['patient', 'Pode sim.'], ['ai', 'Pronto, enviei uma mensagem para o seu WhatsApp. Você pode continuar o atendimento por lá.']]],
    ['pac' => null, 'dias' => 0, 'hora' => '10:40', 'dur' => 52, 'dir' => 'inbound', 'fim' => 'abandono', 'fila_s' => 52, 'numero' => '5584999990099', 'tools' => [], 'snr' => null, 'falas' => []],
    ['pac' => 1004, 'dias' => 1, 'hora' => '14:20', 'dur' => 118, 'dir' => 'inbound', 'fim' => 'ia', 'tools' => ['registrar_triagem'], 'snr' => 12.8, 'miss' => 1, 'falas' => [
        ['patient', 'Carlos Eduardo Lima.'], ['ai', 'Obrigado, Carlos. Como posso ajudar?'],
        ['patient', 'Queria saber se o meu plano Coopab Plus cobre a consulta com clínico geral e quanto fica a coparticipação.'],
        ['ai', 'O Coopab Plus cobre a consulta com clínico geral. A coparticipação é informada pelo plano no momento da autorização. Posso ajudar em mais alguma coisa?'],
        ['patient', 'Não, obrigado.'], ['ai', 'Por nada, Carlos. Até logo!']]],
    ['pac' => 1005, 'dias' => 1, 'hora' => '16:55', 'dur' => 104, 'dir' => 'inbound', 'fim' => 'retorno', 'tools' => ['registrar_triagem', 'transferir_para_atendente', 'agendar_callback'], 'snr' => 19.6, 'falas' => [
        ['patient', 'Fernanda Ribeiro Dantas.'], ['ai', 'Olá, Fernanda. Qual o motivo da ligação?'],
        ['patient', 'Quero marcar uma consulta com dermatologista.'], ['ai', 'Nenhum atendente está disponível agora. Posso agendar um retorno por ligação?'],
        ['patient', 'Pode, no fim da tarde.'], ['ai', 'Combinado. Um atendente vai ligar para você no fim da tarde. Obrigado!']]],
    ['pac' => 1001, 'dias' => 2, 'hora' => '11:10', 'dur' => 83, 'dir' => 'inbound', 'fim' => 'ia', 'tools' => ['registrar_triagem'], 'snr' => 21.0, 'falas' => [
        ['patient', 'Maria da Silva Souza.'], ['ai', 'Olá, Maria. Como posso ajudar?'],
        ['patient', 'Tenho um hemograma marcado. Preciso ir em jejum?'], ['ai', 'Para o hemograma completo o jejum não é obrigatório. Se o pedido tiver glicemia ou colesterol, faça de oito a doze horas de jejum.'],
        ['patient', 'Certo, obrigada.'], ['ai', 'Por nada! Até logo.']]],
    ['pac' => 1004, 'dias' => 3, 'hora' => '17:30', 'dur' => 65, 'dir' => 'outbound', 'fim' => 'ia', 'tools' => ['registrar_triagem'], 'snr' => 20.3, 'motivo' => 'confirmar consulta de amanhã', 'falas' => [
        ['ai', 'Olá, aqui é da Clínica Coopab. Esta ligação pode ser gravada. Falo com Carlos Eduardo Lima?'], ['patient', 'Sim, é ele.'],
        ['ai', 'Estou ligando para confirmar sua consulta de amanhã, às dezesseis e quarenta, com a Dra. Paula Nogueira. O senhor confirma?'],
        ['patient', 'Confirmo, estarei lá.'], ['ai', 'Consulta confirmada. Obrigado e até amanhã!']]],
];

$resumos = app(VoiceSummaryService::class);
$custos = app(VoiceCostService::class);
$porId = collect($pacientes)->keyBy('id');

foreach ($cenarios as $n => $c) {
    $p = $c['pac'] ? $porId[$c['pac']] : null;
    $numero = $p ? $p['phone'] : '+' . $c['numero'];
    $inicio = Carbon::today()->subDays($c['dias'])->setTimeFromTimeString($c['hora']);
    $fim = $inicio->copy()->addSeconds($c['dur']);
    $saida = $c['dir'] === 'outbound';
    $nacional = substr(ltrim($numero, '+'), 2);
    // sempre "call-" (mesmo a saída, que na vida real é "out-"): facilita achar e remover a massa
    $sala = sprintf('call-api_%s_DEMO%s', $nacional, strtoupper(substr(md5($n . $nacional), 0, 8)));

    $call = new VoiceCall();
    $call->forceFill([
        'room_name' => $sala, 'direction' => $c['dir'], 'origin' => 'pstn',
        'from_number' => $saida ? '+558431901994' : $numero, 'to_number' => $saida ? $numero : '+558431901994',
        'status' => $c['fim'] === 'abandono' ? 'abandoned' : 'ended',
        'contact_id' => $p ? $contatos[$p['id']] : null, 'agent_id' => $c['falas'] ? 1 : null,
        'user_id' => $c['fim'] === 'humano' ? $USUARIO : null,
        'triage' => $p ? ['nome' => $p['name'], 'cpf' => $p['cpf'], 'data_nascimento' => Carbon::parse($p['birth_date'])->format('d/m/Y')] : null,
        'answered_at' => $inicio, 'ended_at' => $fim, 'duration_seconds' => $c['dur'],
        'created_at' => $inicio, 'updated_at' => $fim,
    ]);
    if (isset($c['fila_s'])) {
        $call->queued_at = $inicio->copy()->addSeconds($c['fim'] === 'abandono' ? 0 : 60);
        if ($c['fim'] === 'humano') {
            $call->human_at = $call->queued_at->copy()->addSeconds($c['fila_s']);
        }
    }
    $call->save();

    $evento = function (string $tipo, array $payload, Carbon $quando) use ($call) {
        VoiceCallEvent::create(['call_id' => $call->id, 'type' => $tipo, 'payload' => $payload + ['demo' => true], 'occurred_at' => $quando]);
    };

    $evento('room_started', [], $inicio);
    if ($saida) {
        $evento('dial_requested', ['modo' => 'ia', 'user_name' => 'ADMIN SYS', 'motivo' => $c['motivo']], $inicio->copy()->subSeconds(20));
    }

    // falas: primeiro a saudação (entrada), depois o roteiro, espaçadas até ~o fim da parte com IA
    $falas = $c['falas'] ? array_merge($saida ? [] : [['ai', $SAUDACAO]], $c['falas']) : [];
    $fimIa = isset($c['fila_s']) && $c['fim'] === 'humano' ? 60 : $c['dur'] - 4;
    foreach ($falas as $k => [$role, $texto]) {
        $quando = $inicio->copy()->addSeconds((int) round(8 + $k * ($fimIa - 8) / max(count($falas), 1)));
        VoiceTranscript::create(['call_id' => $call->id, 'turn_seq' => $k + 1, 'role' => $role, 'text' => $texto, 'spoken_at' => $quando]);
        if ($k === 0 && $role === 'ai') {
            $evento('recording_notice', ['texto' => $texto], $quando);
        }
    }
    foreach ($c['tools'] as $k => $tool) {
        $quando = $inicio->copy()->addSeconds((int) round($fimIa * (0.35 + 0.2 * $k)));
        $ok = !($tool === 'transferir_para_atendente' && $c['fim'] === 'retorno');
        $evento('tool_called', ['name' => $tool], $quando);
        $evento('tool_result', ['name' => $tool, 'result' => ['ok' => $ok] + ($ok ? [] : ['motivo' => 'sem_atendente'])], $quando->copy()->addSecond());
    }
    if (!empty($c['miss'])) {
        $evento('comprehension_miss', ['motivos' => ['ia_pediu_repeticao'], 'seguidas' => 1, 'mesclado' => false], $inicio->copy()->addSeconds(40));
    }
    if (isset($c['fila_s'])) {
        VoiceQueueEntry::create(['call_id' => $call->id, 'queue_id' => null, 'entered_at' => $call->queued_at,
            'picked_at' => $call->human_at, 'picked_by' => $call->human_at ? $USUARIO : null, 'abandoned_at' => $c['fim'] === 'abandono' ? $fim : null]);
    }
    if ($c['fim'] === 'humano') {
        $evento('participant_joined', ['participant' => ['identity' => 'user_' . $USUARIO, 'name' => 'ADMIN SYS']], $call->human_at);
    }
    if ($c['snr'] !== null) {
        $evento('audio_quality_summary', ['snr_mediana_db' => $c['snr'], 'ruido_mediana_dbfs' => -52.0, 'buracos_pct' => 0.4, 'modo' => 'sombra'], $fim);
    }
    if ($c['falas']) {
        // uso proporcional ao da chamada de teste 114 (134 s): mesma ordem de grandeza de uma ligação real
        $f = min($c['fim'] === 'humano' ? 60 : $c['dur'], $c['dur']) / 134;
        $evento('ai_usage', ['modelos' => [[
            'model' => 'gemini-3.8-live', 'input_tokens' => (int) (25514 * $f), 'input_audio_tokens' => (int) (12041 * $f),
            'output_tokens' => (int) (2133 * $f), 'output_audio_tokens' => (int) (2073 * $f),
        ]], 'respostas' => count($falas)], $fim);
    }
    $evento('room_finished', [], $fim);

    try {
        $r = $resumos->gera($call->fresh());
        $custos->recalcula($call->fresh());
        echo "#{$call->id} {$sala} | ", implode(',', $r['tags']), ' | ', mb_substr($r['summary'], 0, 90), "\n";
    } catch (Throwable $e) {
        echo "#{$call->id} {$sala} | resumo falhou: ", $e->getMessage(), "\n";
    }
}

echo 'criada: ', json_encode(status()), "\n";
