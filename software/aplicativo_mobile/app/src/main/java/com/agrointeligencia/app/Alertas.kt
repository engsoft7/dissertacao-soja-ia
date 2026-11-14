package com.agrointeligencia.app

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Agriculture
import androidx.compose.material.icons.filled.AttachMoney
import androidx.compose.material.icons.filled.Thunderstorm
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.gson.Gson
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalDateTime

// ALERTAS NO CELULAR
//
// O produtor liga, na tela Alertas, o que quer receber: os avisos do INMET
// para o lugar da previsão, a próxima janela boa de pulverização e o preço da
// saca numa praça. O próprio Android (JobScheduler) chama AlertasJob a cada 3
// horas, com internet, mesmo com o app fechado; a conferência usa as mesmas
// fontes das telas Tempo e Mercado. As regras de quando notificar estão em
// AlertasCalculo.kt. Tudo desligado, nada é agendado.

const val PREF_ALERTA_INMET = "alerta_inmet"
const val PREF_ALERTA_PULVERIZACAO = "alerta_pulverizacao"
const val PREF_ALERTA_PRECO = "alerta_preco"
const val PREF_ALERTA_PRECO_ALVO = "alerta_preco_alvo"
const val PREF_ALERTA_PRECO_PRACA = "alerta_preco_praca"
private const val PREF_ALERTA_LUGAR = "alerta_lugar"
private const val PREF_ALERTA_UF = "alerta_uf"
private const val PREF_ALERTA_INMET_IDS = "alerta_inmet_ids"
private const val PREF_ALERTA_PULVERIZACAO_DIA = "alerta_pulverizacao_dia"
private const val PREF_ALERTA_PRECO_AVISADO = "alerta_preco_avisado"
private const val PREFS_DO_APP = "AgroAppCache"

object Alertas {
    const val JOB_ID = 4107
    private const val PERIODO_MS = 3 * 60 * 60 * 1000L
    private const val FLEXIBILIDADE_MS = 60 * 60 * 1000L

    fun algumLigado(prefs: SharedPreferences): Boolean =
        prefs.getBoolean(PREF_ALERTA_INMET, false) || prefs.getBoolean(PREF_ALERTA_PULVERIZACAO, false) ||
            prefs.getBoolean(PREF_ALERTA_PRECO, false)

    /** Agenda a conferência se algum alerta estiver ligado e cancela se nenhum estiver. */
    fun atualizaAgenda(context: Context, prefs: SharedPreferences) {
        val agenda = context.getSystemService(JobScheduler::class.java) ?: return
        if (!algumLigado(prefs)) {
            agenda.cancel(JOB_ID)
            return
        }
        if (agenda.getPendingJob(JOB_ID) != null) return
        agenda.schedule(
            JobInfo.Builder(JOB_ID, ComponentName(context, AlertasJob::class.java))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPeriodic(PERIODO_MS, FLEXIBILIDADE_MS)
                .setPersisted(true)
                .build()
        )
    }

    /**
     * O lugar da previsão e o estado, para a conferência em segundo plano, que
     * não abre a tela. O lugar já vem arredondado a ~1 km quando é o GPS.
     */
    fun guardaContexto(prefs: SharedPreferences, lugar: LugarTempo?, uf: String) {
        prefs.edit()
            .putString(PREF_ALERTA_LUGAR, lugar?.let { Gson().toJson(it) })
            .putString(PREF_ALERTA_UF, uf)
            .apply()
    }

    fun lugar(prefs: SharedPreferences): LugarTempo? =
        prefs.getString(PREF_ALERTA_LUGAR, null)
            ?.let { runCatching { Gson().fromJson(it, LugarTempo::class.java) }.getOrNull() }

    fun uf(prefs: SharedPreferences): String = prefs.getString(PREF_ALERTA_UF, null) ?: "PA"
}

/** O serviço que o Android chama; a conferência roda numa corrotina, fora da linha principal. */
class AlertasJob : JobService() {
    private val escopo = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onStartJob(params: JobParameters): Boolean {
        escopo.launch {
            try {
                confereAlertas(applicationContext)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // Sem rede ou com a API dormindo: a próxima rodada tenta de novo.
            } finally {
                jobFinished(params, false)
            }
        }
        return true
    }

    override fun onStopJob(params: JobParameters): Boolean {
        escopo.coroutineContext.cancelChildren()
        return true
    }

    override fun onDestroy() {
        escopo.cancel()
        super.onDestroy()
    }
}

/** De onde a conferência tira os dados; os testes trocam por respostas fixas. */
class FontesDosAlertas(
    val avisos: suspend (LugarTempo) -> AvisosResponse = { l ->
        RetrofitClient.getInstance().getAvisos(l.lat, l.lon, l.geocode)
    },
    val previsao: suspend (LugarTempo) -> PrevisaoTempo = { l -> OpenMeteo.previsao(l.lat, l.lon) },
    val mercado: suspend (String) -> MercadoResponse = { uf ->
        RetrofitClient.getInstance().getMercado("1d", ufParaApi(uf))
    },
    /** A hora no lugar da previsão (fuso dele); sem previsão, a do celular. */
    val agora: (PrevisaoTempo?) -> LocalDateTime = { p -> if (p != null) agoraNoLugar(p) else LocalDateTime.now() },
)

private suspend fun <T> tenta(bloco: suspend () -> T): T? = try {
    bloco()
} catch (e: CancellationException) {
    throw e
} catch (_: Exception) {
    null
}

/** Uma rodada: confere o que está ligado e notifica o que for novo. */
suspend fun confereAlertas(context: Context, fontes: FontesDosAlertas = FontesDosAlertas()) {
    Formatos.doIdioma(context)
    // Sem permissão de notificar, nada é marcado como avisado: quando o
    // produtor permitir, o aviso que ainda valer chega.
    if (!Notificacoes.podeNotificar(context)) return
    val prefs = context.getSharedPreferences(PREFS_DO_APP, Context.MODE_PRIVATE)
    val lugar = Alertas.lugar(prefs)

    if (prefs.getBoolean(PREF_ALERTA_INMET, false) && lugar != null) {
        // "disponivel" falso: o INMET não respondeu, e a lista guardada fica como estava.
        tenta { fontes.avisos(lugar) }?.takeIf { it.disponivel }?.let { r ->
            val avisos = r.avisos.orEmpty()
            val jaNotificados = prefs.getStringSet(PREF_ALERTA_INMET_IDS, null).orEmpty()
            avisosParaNotificar(avisos, jaNotificados, fontes.agora(null))
                .forEach { Notificacoes.avisoDoInmet(context, it, lugar) }
            prefs.edit().putStringSet(PREF_ALERTA_INMET_IDS, avisos.map { it.id }.toSet()).apply()
        }
    }

    if (prefs.getBoolean(PREF_ALERTA_PULVERIZACAO, false) && lugar != null) {
        tenta { fontes.previsao(lugar) }?.let { p ->
            val agora = fontes.agora(p)
            val horas = p.hourly?.let { horasDePulverizacao(it, agora) }.orEmpty()
            val ultimoDia = prefs.getString(PREF_ALERTA_PULVERIZACAO_DIA, null)
                ?.let { runCatching { LocalDate.parse(it) }.getOrNull() }
            janelaParaNotificar(horas, agora, ultimoDia)?.let { j ->
                Notificacoes.janelaDePulverizacao(context, j, agora, lugar)
                prefs.edit().putString(PREF_ALERTA_PULVERIZACAO_DIA, j.inicio.toLocalDate().toString()).apply()
            }
        }
    }

    if (prefs.getBoolean(PREF_ALERTA_PRECO, false)) {
        val uf = Alertas.uf(prefs)
        val alvo = prefs.getFloat(PREF_ALERTA_PRECO_ALVO, 0f).toDouble().takeIf { it > 0.0 }
        val nomeDaPraca = prefs.getString(PREF_ALERTA_PRECO_PRACA, null)
        tenta { fontes.mercado(uf) }?.takeIf { respostaDoEstado(uf, it.uf) }?.let { m ->
            val praca = m.pracasDoEstado().firstOrNull { it.praca == nomeDaPraca }
            val (notificar, avisado) = precoParaNotificar(
                praca, alvo, prefs.getBoolean(PREF_ALERTA_PRECO_AVISADO, false), fontes.agora(null))
            if (notificar && praca != null && alvo != null) Notificacoes.precoNoAlvo(context, praca, alvo)
            prefs.edit().putBoolean(PREF_ALERTA_PRECO_AVISADO, avisado).apply()
        }
    }
}

/** Os canais, o texto de cada notificação e o toque que abre a aba certa. */
object Notificacoes {
    const val CANAL_INMET = "avisos_inmet"
    const val CANAL_PULVERIZACAO = "pulverizacao"
    const val CANAL_PRECO = "preco"
    /** Aba que o toque na notificação abre (MainActivity). */
    const val EXTRA_ABA = "aba"
    const val ABA_TEMPO = 6
    const val ABA_MERCADO = 4
    private const val ID_PULVERIZACAO = 2001
    private const val ID_PRECO = 3001
    private const val ID_TESTE = 3999

    fun criaCanais(context: Context) {
        val gerente = context.getSystemService(NotificationManager::class.java) ?: return
        gerente.createNotificationChannels(listOf(
            NotificationChannel(CANAL_INMET, context.getString(R.string.alerta_canal_inmet),
                                NotificationManager.IMPORTANCE_HIGH),
            NotificationChannel(CANAL_PULVERIZACAO, context.getString(R.string.alerta_canal_pulverizacao),
                                NotificationManager.IMPORTANCE_DEFAULT),
            NotificationChannel(CANAL_PRECO, context.getString(R.string.alerta_canal_preco),
                                NotificationManager.IMPORTANCE_DEFAULT),
        ))
    }

    fun podeNotificar(context: Context): Boolean =
        NotificationManagerCompat.from(context).areNotificationsEnabled() &&
            (Build.VERSION.SDK_INT < 33 ||
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED)

    private fun mostra(context: Context, id: Int, canal: String, titulo: String, texto: String, aba: Int) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) return
        criaCanais(context)
        val abre = Intent(context, MainActivity::class.java)
            .putExtra(EXTRA_ABA, aba)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        val toque = PendingIntent.getActivity(context, id, abre,
                                              PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notificacao = NotificationCompat.Builder(context, canal)
            .setSmallIcon(R.drawable.ic_notificacao)
            .setContentTitle(titulo)
            .setContentText(texto)
            .setStyle(NotificationCompat.BigTextStyle().bigText(texto))
            .setContentIntent(toque)
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(id, notificacao)
        } catch (_: SecurityException) {
            // A permissão foi retirada entre a conferência e o aviso.
        }
    }

    fun avisoDoInmet(context: Context, a: AvisoMeteorologico, lugar: LugarTempo) {
        val evento = a.evento?.let { nomeDoInmet(context, it) } ?: context.getString(R.string.alerta_inmet_evento)
        val titulo = a.severidade?.let { context.getString(R.string.alerta_inmet_titulo_severidade, evento, nomeDoInmet(context, it)) }
            ?: context.getString(R.string.alerta_inmet_titulo, evento)
        val texto = context.getString(R.string.alerta_inmet_texto, lugar.nome, dataDoAviso(a.inicio), dataDoAviso(a.fim))
        mostra(context, a.id.hashCode(), CANAL_INMET, titulo, texto, ABA_TEMPO)
    }

    fun janelaDePulverizacao(context: Context, j: Janela, agora: LocalDateTime, lugar: LugarTempo) {
        val ini = horaCurta(context, j.inicio)
        val fim = horaCurta(context, j.fim)
        val texto = when (diaDaJanela(j, agora)) {
            QuandoJanela.HOJE -> context.getString(R.string.alerta_pulverizacao_hoje, ini, fim, lugar.nome)
            QuandoJanela.AMANHA -> context.getString(R.string.alerta_pulverizacao_amanha, ini, fim, lugar.nome)
            QuandoJanela.OUTRO_DIA -> context.getString(R.string.alerta_pulverizacao_dia,
                                                        dataCurta(j.inicio.toLocalDate().toString()), ini, fim, lugar.nome)
        }
        mostra(context, ID_PULVERIZACAO, CANAL_PULVERIZACAO,
               context.getString(R.string.alerta_pulverizacao_titulo), texto, ABA_TEMPO)
    }

    fun precoNoAlvo(context: Context, p: PracaPara, alvo: Double) {
        mostra(context, ID_PRECO, CANAL_PRECO,
               context.getString(R.string.alerta_preco_titulo, reais(p.valor), p.praca),
               context.getString(R.string.alerta_preco_texto, p.praca, dataCurta(p.data), reais(alvo)),
               ABA_MERCADO)
    }

    fun teste(context: Context) {
        mostra(context, ID_TESTE, CANAL_PRECO, context.getString(R.string.alerta_teste_titulo),
               context.getString(R.string.alerta_teste_texto), 0)
    }
}

/**
 * O preço digitado: "138,50", "1.234,56" ou "138.5". Com vírgula, a vírgula é
 * o decimal e o ponto separa milhar; sem vírgula, o ponto é o decimal. Null se
 * não for um preço de saca plausível.
 */
fun precoDigitado(texto: String): Double? =
    numeroDigitado(texto.trim().removePrefix("R$"))?.takeIf { it > 0.0 && it < 10_000.0 }

/** A tela Alertas: o que receber, a praça e o preço-alvo, e a permissão de notificar. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AlertasTela(
    prefs: SharedPreferences,
    lugar: LugarTempo?,
    pracas: List<PracaPara>,
    pracaPadrao: PracaPara?,
    aoVoltar: () -> Unit,
) {
    val context = LocalContext.current
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    var inmet by remember { mutableStateOf(prefs.getBoolean(PREF_ALERTA_INMET, false)) }
    var pulverizacao by remember { mutableStateOf(prefs.getBoolean(PREF_ALERTA_PULVERIZACAO, false)) }
    var preco by remember { mutableStateOf(prefs.getBoolean(PREF_ALERTA_PRECO, false)) }
    var praca by remember { mutableStateOf(prefs.getString(PREF_ALERTA_PRECO_PRACA, null) ?: pracaPadrao?.praca) }
    var alvoTexto by remember {
        mutableStateOf(prefs.getFloat(PREF_ALERTA_PRECO_ALVO, 0f).takeIf { it > 0f }?.let { reais(it.toDouble()) } ?: "")
    }
    // Lida de novo depois do pedido de permissão e a cada mudança na tela.
    var versao by remember { mutableIntStateOf(0) }
    val permitido = remember(versao, inmet, pulverizacao, preco) { Notificacoes.podeNotificar(context) }
    val pedePermissao = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { versao++ }

    fun pedeSePreciso() {
        if (!Notificacoes.podeNotificar(context) && Build.VERSION.SDK_INT >= 33) {
            pedePermissao.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    fun liga(chave: String, valor: Boolean) {
        val edicao = prefs.edit().putBoolean(chave, valor)
        if (chave == PREF_ALERTA_PRECO && valor && prefs.getString(PREF_ALERTA_PRECO_PRACA, null) == null) {
            praca?.let { edicao.putString(PREF_ALERTA_PRECO_PRACA, it) }
        }
        edicao.apply()
        if (valor) pedeSePreciso()
        Alertas.atualizaAgenda(context, prefs)
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = aoVoltar) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.alertas_voltar))
            }
            Text(stringResource(R.string.alertas_titulo), fontWeight = FontWeight.Bold, fontSize = 20.sp,
                 color = MaterialTheme.colorScheme.onBackground)
        }
        Text(stringResource(R.string.alertas_explicacao), fontSize = 13.sp, color = secundaria, lineHeight = 18.sp)

        if (!permitido && (inmet || pulverizacao || preco)) {
            CartaoComTitulo(stringResource(R.string.alertas_sem_permissao_titulo), Icons.Filled.Thunderstorm) {
                Text(stringResource(R.string.alertas_sem_permissao), fontSize = 13.sp,
                     color = MaterialTheme.colorScheme.onSurface, lineHeight = 18.sp)
                Button(
                    onClick = {
                        if (Build.VERSION.SDK_INT >= 33 &&
                            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
                            PackageManager.PERMISSION_GRANTED
                        ) {
                            pedePermissao.launch(Manifest.permission.POST_NOTIFICATIONS)
                        } else {
                            runCatching {
                                context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                                    .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
                                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                            }
                        }
                        versao++
                    },
                    modifier = Modifier.heightIn(min = 48.dp)
                ) { Text(stringResource(R.string.alertas_permitir)) }
            }
        }

        CartaoComTitulo(stringResource(R.string.alertas_inmet), Icons.Filled.Thunderstorm) {
            LinhaDoAlerta(
                texto = if (lugar != null) stringResource(R.string.alertas_inmet_lugar, lugar.nome)
                        else stringResource(R.string.alertas_sem_lugar),
                ligado = inmet,
                aoMudar = { inmet = it; liga(PREF_ALERTA_INMET, it) },
            )
        }

        CartaoComTitulo(stringResource(R.string.alertas_pulverizacao), Icons.Filled.Agriculture) {
            LinhaDoAlerta(
                texto = if (lugar != null) stringResource(R.string.alertas_pulverizacao_lugar, lugar.nome)
                        else stringResource(R.string.alertas_sem_lugar),
                ligado = pulverizacao,
                aoMudar = { pulverizacao = it; liga(PREF_ALERTA_PULVERIZACAO, it) },
            )
        }

        CartaoComTitulo(stringResource(R.string.alertas_preco), Icons.Filled.AttachMoney) {
            LinhaDoAlerta(
                texto = stringResource(R.string.alertas_preco_explicacao),
                ligado = preco,
                aoMudar = { preco = it; liga(PREF_ALERTA_PRECO, it) },
            )
            if (pracas.isEmpty()) {
                Text(stringResource(R.string.alertas_sem_pracas), fontSize = 12.sp, color = secundaria)
            } else {
                Text(stringResource(R.string.alertas_praca), fontSize = 12.sp, color = secundaria)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    pracas.forEach { p ->
                        FilterChip(
                            selected = p.praca == praca,
                            onClick = {
                                praca = p.praca
                                prefs.edit().putString(PREF_ALERTA_PRECO_PRACA, p.praca)
                                    .putBoolean(PREF_ALERTA_PRECO_AVISADO, false).apply()
                            },
                            label = { Text(stringResource(R.string.alertas_praca_valor, p.praca, reais(p.valor), dataCurta(p.data))) },
                            modifier = Modifier.heightIn(min = 48.dp)
                        )
                    }
                }
            }
            OutlinedTextField(
                value = alvoTexto,
                onValueChange = { novo ->
                    alvoTexto = novo
                    val valor = precoDigitado(novo)
                    prefs.edit().putFloat(PREF_ALERTA_PRECO_ALVO, (valor ?: 0.0).toFloat())
                        .putBoolean(PREF_ALERTA_PRECO_AVISADO, false).apply()
                },
                label = { Text(stringResource(R.string.alertas_preco_alvo)) },
                prefix = { Text("R$ ") },
                isError = alvoTexto.isNotBlank() && precoDigitado(alvoTexto) == null,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth()
            )
        }

        OutlinedButton(
            onClick = {
                if (Notificacoes.podeNotificar(context)) Notificacoes.teste(context) else pedeSePreciso()
                versao++
            },
            modifier = Modifier.heightIn(min = 48.dp)
        ) { Text(stringResource(R.string.alertas_testar)) }

        Text(stringResource(R.string.alertas_privacidade), fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
    }
}

@Composable
private fun LinhaDoAlerta(texto: String, ligado: Boolean, aoMudar: (Boolean) -> Unit) {
    val estado = stringResource(if (ligado) R.string.alertas_ligado else R.string.alertas_desligado)
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Text(texto, fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface, lineHeight = 18.sp,
             modifier = Modifier.weight(1f))
        Spacer(Modifier.width(8.dp))
        Switch(checked = ligado, onCheckedChange = aoMudar,
               modifier = Modifier.semantics { stateDescription = estado })
    }
}
