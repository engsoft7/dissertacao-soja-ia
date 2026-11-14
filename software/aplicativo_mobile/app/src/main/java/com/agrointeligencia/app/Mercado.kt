package com.agrointeligencia.app

import androidx.compose.ui.res.stringResource
import android.os.Bundle
import android.content.Context
import android.content.SharedPreferences
import androidx.activity.ComponentActivity
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import java.net.URLEncoder
import android.annotation.SuppressLint
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.foundation.Canvas
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import android.graphics.Paint
import kotlin.math.max
import kotlin.math.roundToInt
import androidx.core.view.WindowCompat
import android.app.Activity
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.ui.platform.LocalView
import com.google.gson.Gson
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.activity.compose.BackHandler
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.foundation.lazy.rememberLazyListState
import kotlinx.coroutines.flow.first
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType

// Mercado: cotação do dia nas praças do Pará, Chicago em reais com gráfico de
// velas, média do Pará estimada e as médias mensais com a base.

// Períodos da tela Mercado: chave da API e rótulo do botão.
private val PERIODOS_MERCADO = listOf("1d" to "1D", "5d" to "5D", "1mo" to "1M", "6mo" to "6M")
// "1D" lido em voz alta não diz nada; o leitor de tela lê o período por extenso.
private val PERIODOS_POR_EXTENSO = mapOf("1d" to R.string.periodo_1d, "5d" to R.string.periodo_5d,
                                         "1mo" to R.string.periodo_1mo, "6mo" to R.string.periodo_6mo)

/**
 * Busca a cotação e entrega à tela; a tela em si é MercadoConteudo.
 *
 * Abre na hora com a última cotação guardada de cada período (a data dela fica
 * na tela) e troca pela nova quando chega. Cada período tem a sua: trocar de
 * 1D para 6M mostrava, até a resposta chegar, as velas do 1D com o 6M marcado.
 * Atualiza a cada minuto só com o app aberto na frente.
 */
@Composable
fun MercadoCard(recarga: Int = 0, uf: String = "PA", aoReceber: (MercadoResponse) -> Unit = {}) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE) }
    val gson = remember { Gson() }
    var periodo by rememberSaveable { mutableStateOf("1d") }
    // Uma por estado: trocar de estado não pode mostrar as praças do outro.
    val porPeriodo = remember(uf) { mutableStateMapOf<String, MercadoResponse>() }
    var carregando by remember { mutableStateOf(true) }
    var falhou by remember { mutableStateOf(false) }
    val receber by rememberUpdatedState(aoReceber)
    val ciclo = (context as? ComponentActivity)?.lifecycle

    LaunchedEffect(periodo, recarga, uf) {
        if (porPeriodo[periodo] == null) {
            prefs.getString(chaveDoEstado("mercado_$periodo", uf), null)
                ?.let { runCatching { gson.fromJson(it, MercadoResponse::class.java) }.getOrNull() }
                ?.let { porPeriodo[periodo] = it }
        }
        carregando = true
        suspend fun atualizaSempre() {
            while (true) {
                try {
                    val m = RetrofitClient.getInstance().getMercado(periodo, ufParaApi(uf))
                    // A API antiga responde pelo Pará: fora dele, só vale a resposta do estado.
                    if (!respostaDoEstado(uf, m.uf)) throw IllegalStateException("estado não atendido")
                    porPeriodo[periodo] = m
                    falhou = false
                    receber(m)
                    prefs.edit().putString(chaveDoEstado("mercado_$periodo", uf), gson.toJson(m)).apply()
                } catch (e: kotlinx.coroutines.CancellationException) {
                    throw e
                } catch (_: Exception) {
                    // mantém a última leitura; a hora dela continua visível
                    falhou = true
                }
                carregando = false
                // A API guarda a cotação por dois minutos: isto não pressiona a fonte.
                kotlinx.coroutines.delay(60_000)
            }
        }
        if (ciclo != null) ciclo.repeatOnLifecycle(Lifecycle.State.STARTED) { atualizaSempre() }
        else atualizaSempre()
    }
    MercadoConteudo(porPeriodo[periodo], carregando, periodo, falhou) { periodo = it }
}

/**
 * A tela Mercado sem rede: recebe os dados prontos. Separada de MercadoCard
 * para poder ser desenhada nas capturas de tela automáticas.
 */
@Composable
fun MercadoConteudo(
    mercado: MercadoResponse?,
    carregando: Boolean,
    periodo: String,
    falhou: Boolean = false,
    aoMudarPeriodo: (String) -> Unit
) {
    val isDark = isSystemInDarkTheme()
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    Card(
        modifier = Modifier.fillMaxWidth().padding(bottom = 24.dp),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // O preço do Pará primeiro: é o que o produtor daqui recebe; Chicago
            // vem depois, como o mercado que move esse preço.
            // Sem conexão, a tela mostra a última leitura; a data dela está em
            // cada número, e esta linha diz por que não mudou.
            if (falhou && mercado != null) {
                Text(stringResource(R.string.mercado_sem_conexao), fontSize = 12.sp,
                     color = corAtencao(isDark), fontWeight = FontWeight.SemiBold,
                     modifier = Modifier.padding(bottom = 8.dp).semantics { liveRegion = LiveRegionMode.Polite })
            }
            mercado?.pracasDoEstado()?.takeIf { it.isNotEmpty() }?.let { pracas ->
                CotacoesPracasPara(pracas, estado = estadoDoApp(mercado?.uf))
                HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            }
            Text(stringResource(R.string.mercado_chicago_titulo), fontWeight = FontWeight.Bold, fontSize = 16.sp,
                 color = MaterialTheme.colorScheme.onSurface)
            Text(stringResource(R.string.mercado_chicago_texto),
                 fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PERIODOS_MERCADO.forEach { (chave, rotulo) ->
                    val extenso = PERIODOS_POR_EXTENSO[chave]?.let { stringResource(it) } ?: rotulo
                    FilterChip(selected = periodo == chave, onClick = { aoMudarPeriodo(chave) },
                               label = { Text(rotulo) },
                               modifier = Modifier.semantics { contentDescription = extenso })
                }
            }
            Spacer(Modifier.height(10.dp))
            val cot = mercado?.cotacao
            when {
                carregando && cot == null ->
                    CircularProgressIndicator(modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally))
                cot == null ->
                    Text(stringResource(R.string.mercado_indisponivel),
                         fontSize = 13.sp, color = secundaria)
                else -> {
                    val subiu = cot.variacao_periodo_pct >= 0
                    val corVar = if (subiu) (if (isDark) Color(0xFF3fb950) else Color(0xFF15803d))
                                 else (if (isDark) Color(0xFFf85149) else Color(0xFFb91c1c))
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text("R$ ${reais(cot.ultimo_brl_saca)}", fontSize = 28.sp, fontWeight = FontWeight.Bold,
                             color = MaterialTheme.colorScheme.onSurface)
                        Spacer(Modifier.width(10.dp))
                        Text((if (subiu) "▲ +" else "▼ ") +
                             stringResource(R.string.mercado_variacao, String.format(LOCAL_NUMEROS, "%.2f", cot.variacao_periodo_pct)),
                             fontSize = 13.sp, color = corVar, fontWeight = FontWeight.SemiBold,
                             modifier = Modifier.padding(bottom = 5.dp))
                    }
                    Text(stringResource(R.string.mercado_max_min, reais(cot.maxima_periodo), reais(cot.minima_periodo)),
                         fontSize = 12.sp, color = secundaria)
                    mercado.para?.let { para -> para.estimado_brl_saca?.let { estimado ->
                        PrecoEstimadoPara(para, estimado, isDark)
                    } }
                    GraficoVelas(cot.velas, isDark, cot.periodo)
                    val quando = java.text.SimpleDateFormat(stringResource(R.string.mercado_formato_data_hora), LOCAL_NUMEROS)
                        .format(java.util.Date(cot.atualizado_em * 1000))
                    Text(stringResource(R.string.mercado_atraso, quando, cot.atraso_min.toString()),
                         fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
                    if (cot.ultimo_usd_bushel != null && cot.cambio != null) {
                        Text(stringResource(R.string.mercado_bushel, reais(cot.ultimo_usd_bushel),
                                            String.format(LOCAL_NUMEROS, "%.4f", cot.cambio)),
                             fontSize = 12.sp, color = secundaria)
                    }
                }
            }

            mercado?.para?.let { para -> para.meses?.takeIf { it.size >= 2 }?.let { meses ->
                HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
                GraficoMensalPara(meses, para.fonte, isDark)
            } }

            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            Text(stringResource(R.string.mercado_referencias), fontWeight = FontWeight.Bold, fontSize = 14.sp,
                 color = MaterialTheme.colorScheme.onSurface)
            mercado?.fisico?.let {
                Text(stringResource(R.string.mercado_fisico, it.praca, it.uf, it.tipo, reais(it.valor)) +
                     (if (it.uf != (mercado?.uf ?: "PA")) stringResource(R.string.mercado_outro_estado) else ""),
                     fontSize = 13.sp, color = secundaria)
            }
            mercado?.conab_saca?.let {
                Text(stringResource(R.string.mercado_porteira, mercado?.conab_fonte ?: "CONAB", reais(it)),
                     fontSize = 13.sp, color = secundaria)
            }
            Spacer(Modifier.height(8.dp))
            Text(stringResource(R.string.mercado_aviso),
                 fontSize = 12.sp, color = secundaria, lineHeight = 16.sp,
                 fontStyle = androidx.compose.ui.text.font.FontStyle.Italic)
        }
    }
}

/**
 * Cotação do dia em cada praça do Pará (Agrolink). Uma praça que a fonte parou
 * de atualizar continua listada, em cinza e com a data, para não passar por
 * preço de hoje.
 */
@Composable
fun CotacoesPracasPara(
    pracas: List<PracaPara>,
    hoje: java.time.LocalDate = java.time.LocalDate.now(),
    estado: EstadoDoApp = ESTADOS_DO_APP[0],
) {
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    Text(stringResource(R.string.pracas_titulo, estado.no, estado.nome), fontWeight = FontWeight.Bold, fontSize = 16.sp,
         color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.semantics { heading() })
    Text(stringResource(R.string.pracas_fonte),
         fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
    Spacer(Modifier.height(6.dp))
    // Com a fonte do sistema grande, a data desce para baixo do preço: na mesma
    // linha, o nome da praça ficava com uma letra de largura.
    val fonteGrande = LocalDensity.current.fontScale > 1.3f
    pracas.forEach { p ->
        val emDia = cotacaoEmDia(p, hoje)
        val data = if (emDia) dataCurta(p.data) else stringResource(R.string.pracas_parada, dataCurta(p.data))
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth().heightIn(min = 36.dp).semantics(mergeDescendants = true) {}
        ) {
            Text(p.praca, fontSize = 15.sp, modifier = Modifier.weight(1f),
                 color = if (emDia) MaterialTheme.colorScheme.onSurface else secundaria)
            if (fonteGrande) {
                Column(horizontalAlignment = Alignment.End) {
                    Text("R$ ${reais(p.valor)}", fontSize = 16.sp, fontWeight = FontWeight.Bold,
                         color = if (emDia) MaterialTheme.colorScheme.onSurface else secundaria)
                    Text(data, fontSize = 12.sp, color = secundaria)
                }
            } else {
                Text("R$ ${reais(p.valor)}", fontSize = 16.sp, fontWeight = FontWeight.Bold,
                     color = if (emDia) MaterialTheme.colorScheme.onSurface else secundaria)
                Text("  $data", fontSize = 12.sp, color = secundaria)
            }
        }
    }
}

/** Cor da estimativa do Pará nos dois gráficos da tela Mercado. */
fun corPara(isDark: Boolean) = if (isDark) Color(0xFF58A6FF) else Color(0xFF1D4ED8)

/**
 * O preço estimado no Pará agora, com a conta à vista: Chicago deste momento
 * mais a base do mês. A base tem sinal, e o sinal importa: Barcarena é porto
 * de exportação e pode pagar acima de Chicago convertido.
 */
@Composable
fun PrecoEstimadoPara(para: EstimativaPara, estimado: Double, isDark: Boolean) {
    val cor = corPara(isDark)
    val sinal = if (para.base_brl_saca >= 0) "+" else "−"
    Column(
        modifier = Modifier.fillMaxWidth().padding(top = 10.dp)
            .background(cor.copy(alpha = 0.08f), RoundedCornerShape(10.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp)
    ) {
        Text(stringResource(R.string.para_estimada), fontSize = 12.sp, color = cor, fontWeight = FontWeight.SemiBold)
        Text(stringResource(R.string.para_sc, reais(estimado)), fontSize = 22.sp, fontWeight = FontWeight.Bold,
             color = MaterialTheme.colorScheme.onSurface)
        Text(stringResource(R.string.para_base, sinal, reais(kotlin.math.abs(para.base_brl_saca)),
                            mesCurto(para.mes_base, anoCompleto = true)),
             fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp)
    }
}

/**
 * Médias mensais do Pará e de Chicago em R$/saca e, embaixo, a base de cada
 * mês em barras. A base é o número que importa, e antes era preciso deduzi-la
 * pela distância entre as linhas.
 */
@Composable
fun GraficoMensalPara(meses: List<MesPara>, fonte: String, isDark: Boolean) {
    val cPara = corPara(isDark)
    val cChicago = MaterialTheme.colorScheme.onSurfaceVariant
    val corTexto = MaterialTheme.colorScheme.onSurfaceVariant
    val corGrade = MaterialTheme.colorScheme.outlineVariant
    val marcas = eixoRedondo(meses.minOf { minOf(it.para, it.chicago) }, meses.maxOf { maxOf(it.para, it.chicago) })
    val minP = marcas.first()
    val maxP = marcas.last()
    val faixa = if (maxP > minP) maxP - minP else 1.0
    val positiva = if (isDark) Color(0xFF3fb950) else Color(0xFF15803d)
    val negativa = if (isDark) Color(0xFFf85149) else Color(0xFFb91c1c)
    var tocado by remember(meses) { mutableStateOf<Int?>(null) }
    val ultimo = meses.last()
    // Mesmo enquadramento horizontal nos dois quadros, para a barra de cada
    // mês ficar exatamente embaixo do ponto dele.
    fun indiceTocado(xToque: Float, largura: Float, padX: Float): Int {
        val passo = (largura - padX) / (meses.size - 1).coerceAtLeast(1)
        return ((xToque - padX) / passo).roundToInt().coerceIn(0, meses.size - 1)
    }

    Text(stringResource(R.string.mensal_titulo), fontWeight = FontWeight.Bold, fontSize = 14.sp,
         color = MaterialTheme.colorScheme.onSurface)
    val sel = tocado?.let { meses.getOrNull(it) } ?: ultimo
    Text(
        stringResource(R.string.mensal_selecao, mesCurto(sel.mes, anoCompleto = true), reais(sel.para), reais(sel.chicago),
                       (if (sel.base >= 0) "+" else "−") + reais(kotlin.math.abs(sel.base))),
        fontSize = 12.sp, color = corTexto, lineHeight = 16.sp, modifier = Modifier.padding(top = 4.dp)
    )
    val descricaoMensal = stringResource(R.string.mensal_descricao, mesCurto(meses.first().mes, true),
                                         mesCurto(ultimo.mes, true), reais(ultimo.para), reais(ultimo.chicago))
    Canvas(
        modifier = Modifier.fillMaxWidth().height(180.dp).padding(top = 6.dp, bottom = 6.dp)
            .semantics { contentDescription = descricaoMensal }
            .pointerInput(meses) {
                detectTapGestures { pos -> tocado = indiceTocado(pos.x, size.width.toFloat(), 56.dp.toPx()) }
            }
    ) {
        val padX = 56.dp.toPx()
        val padY = 22.dp.toPx()
        val w = size.width - padX
        val h = size.height - padY
        val passo = w / (meses.size - 1).coerceAtLeast(1)
        fun x(i: Int) = padX + passo * i
        fun y(p: Double) = (h - ((p - minP) / faixa * h)).toFloat()
        val paint = Paint().apply { color = corTexto.toArgb(); textSize = 11.sp.toPx(); isAntiAlias = true }
        marcas.forEach { p ->
            drawLine(color = corGrade, start = Offset(padX, y(p)), end = Offset(padX + w, y(p)), strokeWidth = 1.dp.toPx())
            drawContext.canvas.nativeCanvas.drawText(rotuloEixo(p, marcas), 0f, y(p) + 4.dp.toPx(), paint)
        }
        tocado?.let { drawLine(color = corTexto.copy(alpha = 0.5f), start = Offset(x(it), 0f), end = Offset(x(it), h), strokeWidth = 1.dp.toPx()) }
        fun linha(valor: (MesPara) -> Double, cor: Color, tracejada: Boolean) {
            for (i in 1 until meses.size) {
                drawLine(color = cor, start = Offset(x(i - 1), y(valor(meses[i - 1]))), end = Offset(x(i), y(valor(meses[i]))),
                         strokeWidth = 2.5.dp.toPx(),
                         pathEffect = if (tracejada) PathEffect.dashPathEffect(floatArrayOf(10f, 8f), 0f) else null)
            }
            meses.forEachIndexed { i, m -> drawCircle(color = cor, radius = 3.dp.toPx(), center = Offset(x(i), y(valor(m)))) }
        }
        linha({ it.chicago }, cChicago, tracejada = true)
        linha({ it.para }, cPara, tracejada = false)
        listOf(0, meses.size / 2, meses.size - 1).distinct().forEach { i ->
            val rotulo = mesCurto(meses[i].mes)
            val xx = (x(i) - paint.measureText(rotulo) / 2).coerceIn(padX, size.width - paint.measureText(rotulo))
            drawContext.canvas.nativeCanvas.drawText(rotulo, xx, h + 16.dp.toPx(), paint)
        }
    }
    Row {
        ItemLegenda(cPara, "Pará")
        ItemLegenda(cChicago, stringResource(R.string.legenda_chicago_rs), tracejada = true)
    }

    // Base de cada mês em barras, com escala simétrica em torno de zero.
    val limite = eixoRedondo(0.0, meses.maxOf { kotlin.math.abs(it.base) }, divisoes = 2).last().coerceAtLeast(1.0)
    Text(stringResource(R.string.base_titulo), fontSize = 12.sp, color = corTexto, fontWeight = FontWeight.SemiBold,
         modifier = Modifier.padding(top = 10.dp))
    val descricaoBase = stringResource(R.string.base_descricao, reais(meses.minOf { it.base }),
                                       reais(meses.maxOf { it.base }), reais(ultimo.base))
    Canvas(
        modifier = Modifier.fillMaxWidth().height(84.dp).padding(top = 4.dp)
            .semantics { contentDescription = descricaoBase }
            .pointerInput(meses) {
                detectTapGestures { pos -> tocado = indiceTocado(pos.x, size.width.toFloat(), 56.dp.toPx()) }
            }
    ) {
        val padX = 56.dp.toPx()
        val w = size.width - padX
        val h = size.height
        val passo = w / (meses.size - 1).coerceAtLeast(1)
        val zero = h / 2
        fun y(b: Double) = (zero - b / limite * (h / 2 - 2.dp.toPx())).toFloat()
        val paint = Paint().apply { color = corTexto.toArgb(); textSize = 11.sp.toPx(); isAntiAlias = true }
        drawLine(color = corGrade, start = Offset(padX, zero), end = Offset(padX + w, zero), strokeWidth = 1.dp.toPx())
        listOf(limite, 0.0, -limite).forEach { b ->
            val r = (if (b > 0) "+" else if (b < 0) "−" else "") + milhar(kotlin.math.abs(b))
            drawContext.canvas.nativeCanvas.drawText(r, 0f, (y(b) + 4.dp.toPx()).coerceIn(11.sp.toPx(), h), paint)
        }
        val largura = (passo * 0.6f).coerceIn(2.dp.toPx(), 14.dp.toPx())
        meses.forEachIndexed { i, m ->
            val x = padX + passo * i
            val cor = (if (m.base >= 0) positiva else negativa)
                .copy(alpha = if (tocado == null || tocado == i) 1f else 0.45f)
            val topo = minOf(y(m.base), zero)
            drawRect(color = cor, topLeft = Offset(x - largura / 2, topo),
                     size = Size(largura, kotlin.math.abs(y(m.base) - zero).coerceAtLeast(1.dp.toPx())))
        }
    }
    Text(stringResource(R.string.base_nota, fonte),
         fontSize = 12.sp, color = corTexto, lineHeight = 16.sp, modifier = Modifier.padding(top = 4.dp))
}

@Composable
fun GraficoVelas(velas: List<Vela>, isDark: Boolean, periodo: String) {
    if (velas.isEmpty()) return
    val alta = if (isDark) Color(0xFF3fb950) else Color(0xFF15803d)
    val baixa = if (isDark) Color(0xFFf85149) else Color(0xFFb91c1c)
    val corTexto = MaterialTheme.colorScheme.onSurfaceVariant
    val corGrade = MaterialTheme.colorScheme.outlineVariant
    // A linha do Pará entra na escala: com base positiva ela fica acima das
    // velas e sairia do quadro.
    val comPara = velas.any { it.pa != null }
    val cPara = corPara(isDark)
    val minDado = minOf(velas.minOf { it.l }, velas.mapNotNull { it.pa }.minOrNull() ?: Double.MAX_VALUE)
    val maxDado = maxOf(velas.maxOf { it.h }, velas.mapNotNull { it.pa }.maxOrNull() ?: -Double.MAX_VALUE)
    val (minEixo, maxEixo) = faixaDoEixo(minDado, maxDado)
    val marcas = eixoRedondo(minEixo, maxEixo)
    val minP = marcas.first()
    val maxP = marcas.last()
    val faixa = if (maxP > minP) maxP - minP else 1.0
    // Rótulo do eixo de tempo e da vela tocada conforme o tamanho da vela:
    // hora no dia, dia e hora em cinco dias, data no mês, semana em seis meses.
    val formato = java.text.SimpleDateFormat(
        if (periodo == "1d") "HH:mm" else stringResource(R.string.velas_formato_dia), LOCAL_NUMEROS)
    val formatoToque = java.text.SimpleDateFormat(
        when (periodo) {
            "1d", "5d" -> stringResource(R.string.velas_formato_dia_hora)
            "6mo" -> stringResource(R.string.velas_formato_semana)
            else -> stringResource(R.string.velas_formato_data)
        }, LOCAL_NUMEROS)
    var tocada by remember(velas) { mutableStateOf<Int?>(null) }
    val ultima = velas.last()
    val corUltima = if (ultima.c >= ultima.o) alta else baixa
    val descricao = stringResource(R.string.velas_descricao, reais(velas.first().o), reais(ultima.c),
                                   reais(velas.maxOf { it.h }), reais(velas.minOf { it.l }))

    // A vela tocada, por extenso: o gráfico mostra a forma, e o número exato
    // fica aqui em cima, legível.
    val sel = tocada?.let { velas.getOrNull(it) }
    Text(
        text = sel?.let {
            stringResource(R.string.velas_tocada, formatoToque.format(java.util.Date(it.t * 1000)),
                           reais(it.o), reais(it.h), reais(it.l), reais(it.c)) +
                (it.pa?.let { pa -> " · " + stringResource(R.string.velas_para_estimado, reais(pa)) } ?: "")
        } ?: stringResource(R.string.velas_toque),
        fontSize = 12.sp, color = corTexto, lineHeight = 16.sp,
        modifier = Modifier.padding(top = 10.dp)
    )
    Canvas(
        modifier = Modifier.fillMaxWidth().height(220.dp).padding(top = 6.dp, bottom = 6.dp)
            .semantics { contentDescription = descricao }
            .pointerInput(velas) {
                detectTapGestures { pos ->
                    val padX = 56.dp.toPx()
                    val passo = (size.width - padX) / velas.size
                    tocada = ((pos.x - padX) / passo).toInt().coerceIn(0, velas.size - 1)
                }
            }
    ) {
        val padX = 56.dp.toPx()
        val padY = 22.dp.toPx()
        val w = size.width - padX
        val h = size.height - padY
        val passo = w / velas.size
        // Com poucas velas (o pregão noturno acabou de abrir), cada uma ocupava
        // a largura do gráfico; o corpo agora tem largura máxima.
        val corpo = (passo * 0.6f).coerceIn(1f, 10.dp.toPx())
        fun y(p: Double) = (h - ((p - minP) / faixa * h)).toFloat()
        val paint = Paint().apply { color = corTexto.toArgb(); textSize = 11.sp.toPx(); isAntiAlias = true }
        val yUltima = y(ultima.c)

        marcas.forEach { p ->
            val yy = y(p)
            drawLine(color = corGrade, start = Offset(padX, yy), end = Offset(padX + w, yy), strokeWidth = 1.dp.toPx())
            // A etiqueta do preço atual ocupa a mesma coluna: a marca que
            // cairia embaixo dela fica sem rótulo, em vez de sobreposta.
            if (kotlin.math.abs(yy - yUltima) > 14.dp.toPx()) {
                drawContext.canvas.nativeCanvas.drawText(rotuloEixo(p, marcas), 0f, yy + 4.dp.toPx(), paint)
            }
        }
        tocada?.let {
            val x = padX + passo * it + passo / 2
            drawLine(color = corTexto.copy(alpha = 0.5f), start = Offset(x, 0f), end = Offset(x, h), strokeWidth = 1.dp.toPx())
        }
        velas.forEachIndexed { i, v ->
            val x = padX + passo * i + passo / 2
            val cor = if (v.c >= v.o) alta else baixa
            drawLine(color = cor, start = Offset(x, y(v.h)), end = Offset(x, y(v.l)), strokeWidth = 1.dp.toPx())
            val topo = y(maxOf(v.o, v.c))
            val base = y(minOf(v.o, v.c))
            drawRect(color = cor, topLeft = Offset(x - corpo / 2, topo), size = Size(corpo, (base - topo).coerceAtLeast(1.dp.toPx())))
        }
        if (comPara) {
            var anterior: Offset? = null
            velas.forEachIndexed { i, v ->
                val ponto = v.pa?.let { Offset(padX + passo * i + passo / 2, y(it)) }
                if (ponto != null && anterior != null) {
                    drawLine(color = cPara, start = anterior, end = ponto, strokeWidth = 2.dp.toPx(),
                             pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 6f), 0f))
                }
                anterior = ponto
            }
        }
        // Preço atual: linha tracejada até o eixo e o valor numa etiqueta na
        // coluna dos preços, na cor da última vela.
        drawLine(color = corUltima.copy(alpha = 0.7f), start = Offset(padX, yUltima), end = Offset(padX + w, yUltima),
                 strokeWidth = 1.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 6f), 0f))
        val etiqueta = reais(ultima.c)
        val brancoTexto = Paint().apply { color = android.graphics.Color.WHITE; textSize = 11.sp.toPx(); isAntiAlias = true; isFakeBoldText = true }
        val larg = brancoTexto.measureText(etiqueta) + 8.dp.toPx()
        val alt = 18.dp.toPx()
        val topoEtiqueta = (yUltima - alt / 2).coerceIn(0f, h - alt)
        drawRoundRect(color = corUltima, topLeft = Offset((padX - 4.dp.toPx() - larg).coerceAtLeast(0f), topoEtiqueta),
                      size = Size(larg, alt), cornerRadius = androidx.compose.ui.geometry.CornerRadius(4.dp.toPx()))
        drawContext.canvas.nativeCanvas.drawText(etiqueta, (padX - 4.dp.toPx() - larg).coerceAtLeast(0f) + 4.dp.toPx(),
                                                 topoEtiqueta + alt / 2 + 4.dp.toPx(), brancoTexto)

        listOf(0, velas.size / 2, velas.size - 1).distinct().forEach { i ->
            val rotulo = formato.format(java.util.Date(velas[i].t * 1000))
            val x = (padX + passo * i + passo / 2 - paint.measureText(rotulo) / 2)
                .coerceIn(padX, size.width - paint.measureText(rotulo))
            drawContext.canvas.nativeCanvas.drawText(rotulo, x, h + 16.dp.toPx(), paint)
        }
    }
    Row {
        ItemLegenda(alta, stringResource(R.string.velas_alta), faixa = true)
        ItemLegenda(baixa, stringResource(R.string.velas_baixa), faixa = true)
    }
    if (comPara) ItemLegenda(cPara, stringResource(R.string.velas_para), tracejada = true)
}
