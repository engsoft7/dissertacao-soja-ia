package com.agrointeligencia.app

import androidx.compose.ui.res.stringResource
import android.os.Bundle
import android.content.Context
import android.content.SharedPreferences
import androidx.activity.ComponentActivity
import androidx.compose.ui.platform.LocalContext
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

// Histórico: o gráfico da série do IBGE com a projeção e um cartão por safra.

@Composable
fun PrevisaoCard(historico: PrevisaoHistorico, kpis: FinancaResponse?, precoPadrao: Double? = null) {
    val isDark = isSystemInDarkTheme()
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE) }
    // O mesmo preço e o mesmo custo do Resumo Financeiro. Sem isto, o produtor
    // informava o preço dele numa aba e via o histórico calculado com o da
    // CONAB na outra — duas margens diferentes para a mesma lavoura, no mesmo
    // aplicativo. Num produto de campo, isso destrói a confiança no número.
    val precoDoProdutor = remember { prefs.valorDoProdutor(PREF_PRECO) }
    val custoDoProdutor = remember { prefs.valorDoProdutor(PREF_CUSTO) }
    Card(
        modifier = Modifier.animateContentSize(animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessLow)).fillMaxWidth().padding(vertical = 6.dp),
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        // Layout em coluna, e não duas colunas lado a lado. Com Row + Column sem
        // largura definida, "Estimativa: 3230 kg" não cabia na coluna direita,
        // quebrava linha e o "kg" ia parar ao lado da margem em reais — duas
        // informações diferentes na mesma altura da tela. Empilhado, nada
        // colide em nenhum tamanho de fonte ou de aparelho.
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            val observado = historico.rendimento_real > 0

            // O ano e o que de fato se colheu, que é o que o produtor procura
            // ao percorrer a lista.
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Ano ${historico.ano}",
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    modifier = Modifier.weight(1f)
                )
                // A API envia 0.0 como sentinela de safra ainda não divulgada
                // pela PAM; imprimir esse zero anunciaria colheita nula.
                Text(
                    text = if (observado) milhar(historico.rendimento_real) + " kg/ha"
                           else stringResource(situacaoSemDado(historico.ano)),
                    fontWeight = FontWeight.Bold,
                    fontSize = if (observado) 16.sp else 12.sp,
                    maxLines = 1,
                    color = if (observado) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            // Estimativa e erro típico juntos, em cinza: são contexto do
            // modelo, não o dado da safra. "Margem" saiu daqui de propósito —
            // aparecia com dois sentidos no mesmo cartão, erro em kg e
            // dinheiro em reais, e para quem lê no talhão isso confunde.
            //
            // Para safras passadas a estimativa usa o clima médio do
            // município, e não o da safra: ela acompanha a tendência. Chamá-la
            // de "IA" sugeria uma previsão ano a ano que o modelo não faz.
            Text(
                text = String.format(LOCAL_NUMEROS, "Estimativa %,d kg/ha · erro típico ± %,d kg/ha", 
                    historico.rendimento_predito.roundToInt(), historico.margem_erro.roundToInt()),
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 2.dp)
            )

            // Safra observada: a margem parte do rendimento medido. Safra ainda
            // por vir: parte da projeção. Nos dois casos o preço e o custo são
            // os de hoje, e não os da época — daí o rótulo.
            if (kpis != null && (observado || historico.rendimento_predito > 0)) {
                val kgHa = if (observado) historico.rendimento_real else historico.rendimento_predito
                val r = resultadoPorHectare(
                    sacasDoCampo(kgHa / 60), precoDoProdutor ?: precoPadrao ?: kpis.soja_preco_saca, custoDoProdutor, kpis)
                val outro = r.outroRateio
                // Sinal incerto não leva verde nem vermelho: o dado publicado
                // não sustenta nenhum dos dois, e a cor é o que o produtor lê
                // antes do número.
                val color = when {
                    r.sinalIncerto -> corAtencao(isDark)
                    r.valor > 0 -> if (isDark) Color(0xFF3fb950) else Color(0xFF16a34a)
                    else -> if (isDark) Color(0xFFf85149) else Color(0xFFdc2626)
                }
                Text(
                    // "A preços de hoje" dizia mais do que é: o preço e o custo
                    // são os da Viabilidade, do produtor ou do levantamento da
                    // CONAB, que pode ter meses.
                    text = (if (observado) "Com o preço e o custo da Viabilidade: "
                            else "Projetado, com o preço e o custo da Viabilidade: ") + reaisInteiros(r.valor) + "/ha",
                    fontSize = 13.sp,
                    color = color,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 8.dp)
                )
                if (r.sinalIncerto && outro != null) {
                    Text(
                        text = "Pode ir de ${reaisInteiros(minOf(r.valor, outro))} a ${reaisInteiros(maxOf(r.valor, outro))}, " +
                               "conforme o rateio do custo.",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 2.dp)
                    )
                }
            }
        }
    }
}

@Composable
fun HistoricoProdutividadeChart(historico: List<PrevisaoHistorico>, previsao: PrevisaoResponse?) {
    if (historico.isEmpty()) return
    val isDark = isSystemInDarkTheme()
    val corReal = if (isDark) Color(0xFF3fb950) else Color(0xFF15803d)
    val corProj = if (isDark) Color(0xFF38BDF8) else Color(0xFF0369A1)
    // Faixas claras e sem texto: com a classificação por safra, quase todas as
    // safras têm El Niño ou La Niña, e um rótulo em cada uma cobria o gráfico.
    val corNino = if (isDark) Color(0x2EF87171) else Color(0x33EF4444)
    val corNina = if (isDark) Color(0x2E60A5FA) else Color(0x333B82F6)
    val corTexto = MaterialTheme.colorScheme.onSurfaceVariant
    val corGrade = MaterialTheme.colorScheme.outlineVariant

    val ordenado = remember(historico) { historico.sortedBy { it.ano } }
    val minYear = ordenado.first().ano
    val maxYear = ordenado.last().ano
    // Eixo em valores redondos e ajustado aos dados, e não de zero: com zero na
    // base, toda a variação entre safras ficava espremida na metade de cima.
    val valores = ordenado.flatMap { listOf(it.rendimento_real, it.rendimento_predito) }.filter { it > 0 }
        .ifEmpty { listOf(0.0, 1000.0) }
    val passoY = if (valores.max() - valores.min() > 2000) 1000.0 else 500.0
    val yMin = (kotlin.math.floor(valores.min() / passoY) * passoY).toFloat()
    val yMax = (kotlin.math.ceil(valores.max() / passoY) * passoY).toFloat().let { if (it <= yMin) yMin + passoY.toFloat() else it }
    val elNinos = previsao?.elNinos.orEmpty()
    val laNinas = previsao?.laNinas.orEmpty()
    val ultimoObservado = ordenado.lastOrNull { it.rendimento_real > 0 }
    val startPredYear = ultimoObservado?.ano ?: maxYear
    var anoTocado by remember(historico) { mutableStateOf<Int?>(null) }

    fun fase(ano: Int) = when (ano) { in elNinos -> " · El Niño"; in laNinas -> " · La Niña"; else -> "" }
    val descricao = "Gráfico da produtividade de $minYear a $maxYear. " +
        (ultimoObservado?.let { "Última safra observada, ${it.ano}: ${milhar(it.rendimento_real)} kg/ha. " } ?: "") +
        "Projeção para $maxYear: ${milhar(ordenado.last().rendimento_predito)} kg/ha."

    Card(
        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text("Evolução histórica e projeção (kg/ha)", fontWeight = FontWeight.Bold, fontSize = 16.sp,
                 color = MaterialTheme.colorScheme.onSurface)
            val sel = anoTocado?.let { a -> ordenado.firstOrNull { it.ano == a } }
            Text(
                text = sel?.let {
                    if (it.rendimento_real > 0)
                        "${it.ano}: observado ${milhar(it.rendimento_real)} · estimado ${milhar(it.rendimento_predito)} kg/ha${fase(it.ano)}"
                    else
                        "${it.ano}: projeção ${milhar(it.rendimento_predito)} kg/ha (± ${milhar(it.margem_erro)})${fase(it.ano)}"
                } ?: "Toque no gráfico para ver o valor de um ano.",
                fontSize = 12.sp, color = corTexto, lineHeight = 16.sp, modifier = Modifier.padding(top = 4.dp)
            )
            Canvas(
                modifier = Modifier.fillMaxWidth().height(220.dp).padding(top = 8.dp)
                    .semantics { contentDescription = descricao }
                    .pointerInput(ordenado) {
                        detectTapGestures { pos ->
                            val padX = 48.dp.toPx()
                            val frac = ((pos.x - padX) / (size.width - padX)).coerceIn(0f, 1f)
                            anoTocado = minYear + (frac * (maxYear - minYear)).roundToInt()
                        }
                    }
            ) {
                val padX = 48.dp.toPx()
                val padY = 22.dp.toPx()
                val w = size.width - padX
                val h = size.height - padY
                val span = (maxYear - minYear).coerceAtLeast(1)
                fun x(ano: Int) = padX + (ano - minYear) * (w / span)
                fun y(v: Double) = h - ((v.toFloat() - yMin) / (yMax - yMin)) * h
                val paint = Paint().apply { color = corTexto.toArgb(); textSize = 11.sp.toPx(); isAntiAlias = true }

                val largura = (w / span) * 0.85f
                for (ano in minYear..maxYear) {
                    val cor = when (ano) { in elNinos -> corNino; in laNinas -> corNina; else -> null } ?: continue
                    // recortada à área do gráfico: a primeira e a última safra
                    // não invadem a coluna dos números do eixo
                    val esq = (x(ano) - largura / 2).coerceAtLeast(padX)
                    val dir = (x(ano) + largura / 2).coerceAtMost(padX + w)
                    drawRect(color = cor, topLeft = Offset(esq, 0f), size = Size(dir - esq, h))
                }
                var v = yMin
                while (v <= yMax + 0.5f) {
                    val yy = y(v.toDouble())
                    drawLine(color = corGrade, start = Offset(padX, yy), end = Offset(padX + w, yy), strokeWidth = 1.dp.toPx())
                    drawContext.canvas.nativeCanvas.drawText(milhar(v.toDouble()), 0f, yy + 4.dp.toPx(), paint)
                    v += passoY.toFloat()
                }
                val passoRotulo = if (span > 12) 5 else if (span > 6) 2 else 1
                // De passoRotulo em passoRotulo; o último ano sempre aparece e,
                // se ficar perto demais do rótulo anterior, toma o lugar dele.
                val anosRotulo = (minYear..maxYear step passoRotulo).toMutableList()
                if (anosRotulo.last() != maxYear) {
                    if (maxYear - anosRotulo.last() <= passoRotulo / 2) anosRotulo[anosRotulo.lastIndex] = maxYear
                    else anosRotulo.add(maxYear)
                }
                for (ano in anosRotulo) {
                    val rotulo = "$ano"
                    val xr = (x(ano) - paint.measureText(rotulo) / 2).coerceIn(padX, size.width - paint.measureText(rotulo))
                    drawContext.canvas.nativeCanvas.drawText(rotulo, xr, h + 16.dp.toPx(), paint)
                }
                anoTocado?.let {
                    drawLine(color = corTexto.copy(alpha = 0.5f), start = Offset(x(it), 0f), end = Offset(x(it), h), strokeWidth = 1.dp.toPx())
                }

                // Observado (linha cheia)
                val pathReal = Path()
                var primeiro = true
                ordenado.filter { it.rendimento_real > 0 }.forEach { item ->
                    val px = x(item.ano)
                    val py = y(item.rendimento_real)
                    if (primeiro) { pathReal.moveTo(px, py); primeiro = false } else pathReal.lineTo(px, py)
                    drawCircle(color = corReal, radius = 3.dp.toPx(), center = Offset(px, py))
                }
                drawPath(path = pathReal, color = corReal, style = Stroke(width = 2.5.dp.toPx()))

                // Projeção (tracejada), a partir do último ano observado
                val pathPred = Path()
                primeiro = true
                ordenado.filter { it.ano >= startPredYear }.forEach { item ->
                    val valor = if (item.ano == startPredYear && item.rendimento_real > 0) item.rendimento_real else item.rendimento_predito
                    val px = x(item.ano)
                    val py = y(valor)
                    if (primeiro) { pathPred.moveTo(px, py); primeiro = false } else pathPred.lineTo(px, py)
                    if (item.ano > startPredYear) drawCircle(color = corProj, radius = 3.dp.toPx(), center = Offset(px, py))
                }
                drawPath(path = pathPred, color = corProj, style = Stroke(
                    width = 2.5.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 10f), 0f)))
            }
            Row {
                ItemLegenda(corReal, "Observado (IBGE)")
                ItemLegenda(corProj, "Projeção", tracejada = true)
            }
            Row {
                ItemLegenda(corNino, "Safra de El Niño", faixa = true)
                ItemLegenda(corNina, "Safra de La Niña", faixa = true)
            }
        }
    }
}
