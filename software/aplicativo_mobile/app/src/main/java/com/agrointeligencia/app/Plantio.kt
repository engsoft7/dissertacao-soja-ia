package com.agrointeligencia.app

import android.content.SharedPreferences
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Grass
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.WbSunny
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.gson.Gson
import java.time.LocalDate
import java.time.Month
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.time.temporal.ChronoUnit

// A JANELA DE PLANTIO: CALENDÁRIO DA PORTARIA E RISCO DO ZARC
//
// Duas regras diferentes, lado a lado, sem o app decidir pelo produtor:
// - o calendário de semeadura e o vazio sanitário da Portaria SDA/MAPA nº
//   1.579/2026: fora dele, plantar soja é proibido;
// - o Zoneamento Agrícola de Risco Climático (ZARC): fora da janela, plantar é
//   permitido, mas sem o Proagro e sem boa parte do crédito rural.
// As contas estão em PlantioCalculo.kt; os textos, em res/values/strings.xml.

private const val PREF_PLANTIO_CICLO = "plantio_ciclo"
private const val PREF_PLANTIO_SOLO = "plantio_solo"
// Grupo II e AD3 de partida: o meio das opções. O produtor troca na tela, e a
// escolha fica guardada.
private const val CICLO_PADRAO = 21
private const val SOLO_PADRAO = 13
// O calendário e o ZARC mudam uma vez por safra: uma semana basta.
private const val VALIDADE_PLANTIO_MS = 7L * 24 * 3600 * 1000

private val COR_RISCO_20 = Color(0xFF2E7D32)
private val COR_RISCO_30 = Color(0xFFF9A825)
private val COR_RISCO_40 = Color(0xFFEF6C00)

private fun corDoRisco(risco: Int): Color = when (risco) {
    20 -> COR_RISCO_20
    30 -> COR_RISCO_30
    else -> COR_RISCO_40
}

/** "2026/2027" -> "2026/27". */
fun safraCurta(safra: String?): String? =
    safra?.split("/")?.takeIf { it.size == 2 }?.let { "${it[0]}/${it[1].takeLast(2)}" }

/** Estado da janela de plantio, com a última resposta guardada no aparelho. */
class EstadoPlantio(private val prefs: SharedPreferences) {
    private val gson = Gson()
    // internal: as capturas de tela (CapturasDeTelaTest) põem a resposta direto.
    var dados by mutableStateOf<PlantioResponse?>(null)
        internal set
    var carregando by mutableStateOf(false)
        private set
    var falhou by mutableStateOf(false)
        private set
    var ciclo by mutableStateOf(prefs.getInt(PREF_PLANTIO_CICLO, CICLO_PADRAO))
        private set
    var solo by mutableStateOf(prefs.getInt(PREF_PLANTIO_SOLO, SOLO_PADRAO))
        private set
    private var chaveAtual: String? = null

    fun escolherCiclo(c: Int) {
        ciclo = c
        prefs.edit().putInt(PREF_PLANTIO_CICLO, c).apply()
    }

    fun escolherSolo(s: Int) {
        solo = s
        prefs.edit().putInt(PREF_PLANTIO_SOLO, s).apply()
    }

    /** Os 36 riscos do grupo e do solo escolhidos; null sem ZARC para o município. */
    fun riscos(): String? = dados?.zarc?.riscos?.get("$ciclo-$solo")

    suspend fun carrega(municipio: String, uf: String, forcar: Boolean = false) {
        val k = chaveDoEstado("plantio_$municipio", uf)
        if (chaveAtual != k) {
            chaveAtual = k
            falhou = false
            dados = prefs.getString(k, null)?.let { runCatching { gson.fromJson(it, PlantioResponse::class.java) }.getOrNull() }
        }
        val em = prefs.getLong(k + "_em", 0L)
        if (!forcar && dados != null && System.currentTimeMillis() - em < VALIDADE_PLANTIO_MS) return
        carregando = true
        try {
            val r = RetrofitClient.getInstance().getPlantio(municipio, ufParaApi(uf))
            if (chaveAtual != k) return
            dados = r
            falhou = false
            prefs.edit().putString(k, gson.toJson(r)).putLong(k + "_em", System.currentTimeMillis()).apply()
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (_: Exception) {
            if (chaveAtual == k) falhou = true
        } finally {
            if (chaveAtual == k) carregando = false
        }
    }
}

@Composable
private fun formato(idPadrao: Int): DateTimeFormatter =
    DateTimeFormatter.ofPattern(stringResource(idPadrao), LocalConfiguration.current.locales[0])

/** A frase do calendário para o dia: semeadura até tal dia, vazio até tal dia, ou encerrada. */
@Composable
private fun fraseDoCalendario(c: CalendarioPlantio?, hoje: LocalDate): String? {
    val semeadura = periodoDeSemeadura(c) ?: return null
    val vazio = periodoDoVazio(c)
    val f = formato(R.string.plantio_formato_data)
    return when (situacaoNoDia(c, hoje)) {
        SituacaoCalendario.SEMEADURA -> stringResource(R.string.plantio_semeadura_ate, semeadura.second.format(f))
        SituacaoCalendario.VAZIO_SANITARIO ->
            stringResource(R.string.plantio_vazio_ate, vazio!!.second.format(f), semeadura.first.format(f))
        else -> if (vazio != null && hoje.isBefore(vazio.first))
            stringResource(R.string.plantio_vazio_comeca, vazio.first.format(f))
        else stringResource(R.string.plantio_semeadura_encerrada, semeadura.second.format(f))
    }
}

/** A frase do ZARC para o dia, com o grupo e o solo escolhidos. */
@Composable
private fun fraseDoZarc(estado: EstadoPlantio, hoje: LocalDate): Pair<String, Int> {
    val d = estado.dados
    val z = d?.zarc ?: return stringResource(R.string.plantio_zarc_sem_zoneamento) to 0
    val ini = anoInicialDaSafra(d.safra) ?: return stringResource(R.string.plantio_zarc_sem_zoneamento) to 0
    val grupo = z.ciclos?.firstOrNull { it.codigo == estado.ciclo }?.nome.orEmpty()
    val solo = z.solos?.firstOrNull { it.codigo == estado.solo }?.nome.orEmpty()
    val riscos = estado.riscos() ?: return stringResource(R.string.plantio_zarc_sem_combinacao, grupo, solo) to 0
    val risco = riscoNoDia(riscos, ini, hoje)
    if (risco > 0) return stringResource(R.string.plantio_zarc_hoje, risco, grupo, solo) to risco
    val prox = proximaJanelaZarc(janelasZarc(riscos, ini), hoje)
    val f = formato(R.string.plantio_formato_dia)
    return if (prox != null) stringResource(R.string.plantio_zarc_proxima, grupo, solo, prox.inicio.format(f), prox.risco) to 0
    else stringResource(R.string.plantio_zarc_encerrado, grupo, solo) to 0
}

@Composable
fun PlantioResumoCard(estado: EstadoPlantio, hoje: LocalDate = LocalDate.now(), aoAbrir: () -> Unit) {
    val d = estado.dados
    Card(
        onClick = aoAbrir,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(16.dp)) {
            Icon(Icons.Filled.Grass, contentDescription = null, tint = MaterialTheme.colorScheme.primary,
                 modifier = Modifier.size(32.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.plantio_titulo_cartao, safraCurta(d?.safra) ?: "…"), fontSize = 12.sp,
                     color = MaterialTheme.colorScheme.onSurfaceVariant)
                when {
                    d == null && estado.carregando ->
                        Text(stringResource(R.string.plantio_carregando), fontSize = 14.sp,
                             color = MaterialTheme.colorScheme.onSurface)
                    d == null ->
                        Text(stringResource(R.string.plantio_indisponivel), fontSize = 14.sp,
                             color = MaterialTheme.colorScheme.onSurface)
                    else -> {
                        fraseDoCalendario(d.calendario, hoje)?.let {
                            Text(it, fontWeight = FontWeight.SemiBold, fontSize = 15.sp,
                                 color = MaterialTheme.colorScheme.onSurface)
                        }
                        val (frase, risco) = fraseDoZarc(estado, hoje)
                        Text(frase, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                             color = if (risco > 0) corDoRisco(risco) else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = stringResource(R.string.plantio_abrir),
                 tint = MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable
private fun CartaoPlantio(titulo: String, icone: androidx.compose.ui.graphics.vector.ImageVector,
                          conteudo: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 4.dp)) {
                Icon(icone, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text(titulo, fontWeight = FontWeight.Bold, fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface,
                     modifier = Modifier.semantics { heading() })
            }
            conteudo()
        }
    }
}

/** A tela da janela de plantio: o calendário da região e o ZARC com grupo e solo à escolha. */
@Composable
fun PlantioTela(estado: EstadoPlantio, municipio: String?, aoAtualizar: () -> Unit, aoVoltar: () -> Unit,
                hoje: LocalDate = LocalDate.now()) {
    val d = estado.dados
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = aoVoltar) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.plantio_voltar))
            }
            Text(stringResource(R.string.plantio_titulo_tela), fontWeight = FontWeight.Bold, fontSize = 20.sp,
                 color = MaterialTheme.colorScheme.onBackground, modifier = Modifier.weight(1f))
            IconButton(onClick = aoAtualizar) {
                Icon(Icons.Filled.Refresh, contentDescription = stringResource(R.string.plantio_atualizar))
            }
        }
        val safra = d?.safra
        if (municipio != null && safra != null) {
            Text(stringResource(R.string.plantio_subtitulo, municipio, safra), fontSize = 12.sp, color = secundaria)
        }
        when {
            d == null && estado.carregando ->
                CircularProgressIndicator(modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally))
            d == null -> Text(stringResource(R.string.plantio_indisponivel_tela), fontSize = 14.sp, color = secundaria)
            else -> {
                if (estado.falhou) {
                    Text(stringResource(R.string.plantio_sem_conexao), fontSize = 12.sp, color = COR_RISCO_40,
                         fontWeight = FontWeight.SemiBold)
                }
                CartaoCalendario(d.calendario, hoje)
                CartaoZarc(estado, hoje)
                Text(stringResource(R.string.plantio_regras), fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface,
                     lineHeight = 18.sp)
            }
        }
    }
}

@Composable
private fun CartaoCalendario(c: CalendarioPlantio?, hoje: LocalDate) {
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    val uri = LocalUriHandler.current
    CartaoPlantio(stringResource(R.string.plantio_secao_calendario), Icons.Filled.CalendarMonth) {
        val semeadura = periodoDeSemeadura(c)
        if (c == null || semeadura == null) {
            Text(stringResource(R.string.plantio_sem_calendario), fontSize = 14.sp, color = secundaria)
            return@CartaoPlantio
        }
        val f = formato(R.string.plantio_formato_data)
        fraseDoCalendario(c, hoje)?.let {
            Text(it, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
        }
        c.regiao?.let { Text(stringResource(R.string.plantio_regiao, it), fontSize = 13.sp, color = secundaria) }
        periodoDoVazio(c)?.let {
            Text(stringResource(R.string.plantio_vazio_periodo, it.first.format(f), it.second.format(f)),
                 fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
        }
        Text(stringResource(R.string.plantio_semeadura_periodo, semeadura.first.format(f), semeadura.second.format(f)),
             fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
        // A frase vem pronta da API, com as datas da outra região (plantio.observacao).
        c.observacao?.let { Text(it, fontSize = 12.sp, color = secundaria, lineHeight = 16.sp) }
        c.fonte?.let { fonte ->
            TextButton(onClick = { c.url?.let { u -> runCatching { uri.openUri(u) } } },
                       modifier = Modifier.heightIn(min = 48.dp)) {
                Text(fonte, fontSize = 12.sp)
            }
        }
    }
}

// FlowRow: os seis solos não cabem numa linha de celular, e o AD6 ficava
// escondido na rolagem lateral.
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CartaoZarc(estado: EstadoPlantio, hoje: LocalDate) {
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    val uri = LocalUriHandler.current
    val d = estado.dados
    val z = d?.zarc
    val ini = anoInicialDaSafra(d?.safra)
    CartaoPlantio(stringResource(R.string.plantio_secao_zarc), Icons.Filled.WbSunny) {
        if (z == null || ini == null) {
            Text(stringResource(R.string.plantio_zarc_sem_zoneamento), fontSize = 14.sp, color = secundaria)
            return@CartaoPlantio
        }
        val (frase, risco) = fraseDoZarc(estado, hoje)
        Text(frase, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
             color = if (risco > 0) corDoRisco(risco) else MaterialTheme.colorScheme.onSurface)

        Text(stringResource(R.string.plantio_grupo), fontSize = 12.sp, color = secundaria)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            z.ciclos.orEmpty().forEach { o ->
                FilterChip(selected = o.codigo == estado.ciclo, onClick = { estado.escolherCiclo(o.codigo) },
                           label = { Text(o.nome) }, modifier = Modifier.heightIn(min = 48.dp))
            }
        }
        Text(stringResource(R.string.plantio_grupo_ajuda), fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
        Text(stringResource(R.string.plantio_solo), fontSize = 12.sp, color = secundaria)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            z.solos.orEmpty().forEach { o ->
                FilterChip(selected = o.codigo == estado.solo, onClick = { estado.escolherSolo(o.codigo) },
                           label = { Text(o.nome) }, modifier = Modifier.heightIn(min = 48.dp))
            }
        }
        Text(stringResource(R.string.plantio_solo_ajuda), fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)

        val riscos = estado.riscos()
        val janelas = riscos?.let { janelasZarc(it, ini) }.orEmpty()
        LinhaDoTempo(d?.calendario, janelas, ini, hoje)
        val semeadura = periodoDeSemeadura(d?.calendario)
        val f = formato(R.string.plantio_formato_dia)
        if (janelas.isEmpty()) {
            Text(stringResource(R.string.plantio_zarc_sem_janela), fontSize = 14.sp, color = secundaria)
        }
        janelas.forEach { j ->
            val dentro = dentroDoCalendario(j, semeadura)
            val base = stringResource(R.string.plantio_janela, j.inicio.format(f), j.fim.format(f), j.risco)
            val sufixo = when {
                dentro == null -> " " + stringResource(R.string.plantio_janela_fora)
                dentro != j -> " " + stringResource(R.string.plantio_janela_parte_fora)
                else -> ""
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(12.dp).background(corDoRisco(j.risco), RoundedCornerShape(3.dp)))
                Spacer(Modifier.width(8.dp))
                Text(base + sufixo, fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
            }
        }
        Text(stringResource(R.string.plantio_risco_explicacao), fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
        z.portaria?.let { p ->
            TextButton(onClick = { z.url?.let { u -> runCatching { uri.openUri(u) } } },
                       modifier = Modifier.heightIn(min = 48.dp)) {
                Text(stringResource(R.string.plantio_fonte_zarc, p), fontSize = 12.sp)
            }
        }
    }
}

/**
 * De julho a junho: o vazio sanitário e a semeadura na faixa de cima, as janelas
 * do ZARC na de baixo, e o dia de hoje. A lista abaixo do desenho diz o mesmo em
 * texto, para o leitor de tela.
 */
@Composable
private fun LinhaDoTempo(c: CalendarioPlantio?, janelas: List<JanelaZarc>, safraIni: Int, hoje: LocalDate) {
    val inicio = LocalDate.of(safraIni, 7, 1)
    val fim = LocalDate.of(safraIni + 1, 6, 30)
    val total = ChronoUnit.DAYS.between(inicio, fim).toFloat() + 1f
    val vazio = periodoDoVazio(c)
    val semeadura = periodoDeSemeadura(c)
    val corVazio = MaterialTheme.colorScheme.error.copy(alpha = 0.45f)
    val corSemeadura = MaterialTheme.colorScheme.primary.copy(alpha = 0.45f)
    val corTrilha = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f)
    val corHoje = MaterialTheme.colorScheme.onSurface
    val descricao = stringResource(R.string.plantio_linha_do_tempo)
    fun fracao(d: LocalDate): Float = (ChronoUnit.DAYS.between(inicio, d).toFloat() / total).coerceIn(0f, 1f)
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Canvas(Modifier.fillMaxWidth().height(48.dp).semantics { contentDescription = descricao }) {
            val w = size.width
            val faixa = size.height * 0.36f
            val y2 = size.height * 0.56f
            drawRect(corTrilha, Offset(0f, 0f), Size(w, faixa))
            drawRect(corTrilha, Offset(0f, y2), Size(w, faixa))
            vazio?.let { drawRect(corVazio, Offset(w * fracao(it.first), 0f), Size(w * (fracao(it.second) - fracao(it.first)), faixa)) }
            semeadura?.let {
                drawRect(corSemeadura, Offset(w * fracao(it.first), 0f), Size(w * (fracao(it.second) - fracao(it.first)), faixa))
            }
            janelas.forEach { j ->
                val x0 = w * fracao(j.inicio)
                val x1 = w * fracao(j.fim.plusDays(1))
                drawRect(corDoRisco(j.risco), Offset(x0, y2), Size(x1 - x0, faixa))
            }
            if (!hoje.isBefore(inicio) && !hoje.isAfter(fim)) {
                val x = w * fracao(hoje)
                drawLine(corHoje, Offset(x, 0f), Offset(x, size.height), strokeWidth = 2.dp.toPx())
            }
        }
        val locale = LocalConfiguration.current.locales[0]
        Row(Modifier.fillMaxWidth()) {
            (0 until 12).forEach { k ->
                val mes = inicio.plusMonths(k.toLong())
                Text(Month.from(mes).getDisplayName(TextStyle.NARROW, locale),
                     fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                     modifier = Modifier.weight(mes.lengthOfMonth().toFloat()))
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.horizontalScroll(rememberScrollState())) {
            Legenda(corVazio, stringResource(R.string.plantio_legenda_vazio))
            Legenda(corSemeadura, stringResource(R.string.plantio_legenda_semeadura))
            Legenda(COR_RISCO_20, "20%")
            Legenda(COR_RISCO_30, "30%")
            Legenda(COR_RISCO_40, "40%")
        }
    }
}

@Composable
private fun Legenda(cor: Color, texto: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).background(cor, RoundedCornerShape(2.dp)))
        Spacer(Modifier.width(4.dp))
        Text(texto, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
