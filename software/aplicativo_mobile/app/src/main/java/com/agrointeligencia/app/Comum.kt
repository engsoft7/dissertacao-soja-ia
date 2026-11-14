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

// Peças comuns às telas: formatos de número em português, títulos de seção,
// avisos de carregando e de sem dados, legendas e eixos dos gráficos.

/**
 * A resposta só serve com o histórico. O Gson não passa pelo construtor: sem o
 * campo no JSON (cache de outra versão, resposta cortada), um tipo não nulo
 * chega nulo, e o app caía na primeira tela que o lia.
 */
@Suppress("SENSELESS_COMPARISON")
internal fun PrevisaoResponse.valida(): PrevisaoResponse? =
    if (historico == null || municipio == null) null else this

/** Amarelo de atenção com contraste de texto acima de 4,5:1 nos dois temas. */
fun corAtencao(isDark: Boolean) = if (isDark) Color(0xFFd29922) else Color(0xFF9a6700)

/**
 * Título de seção, marcado como título para o leitor de tela: com o TalkBack,
 * o produtor pula de uma seção a outra em vez de ouvir a tela inteira.
 */
@Composable
fun TituloSecao(icone: ImageVector, texto: String, modifier: Modifier = Modifier) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier.padding(bottom = 4.dp).semantics(mergeDescendants = true) { heading() }
    ) {
        Icon(icone, contentDescription = null, tint = MaterialTheme.colorScheme.onBackground)
        Spacer(Modifier.width(8.dp))
        Text(texto, fontSize = 18.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onBackground)
    }
}

/** Sem dados para mostrar: o que aconteceu, o que ainda funciona e o botão de tentar de novo. */
@Composable
fun AvisoSemDados(titulo: String, texto: String, rotulo: String = stringResource(R.string.tentar_de_novo), aoTentar: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp)
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.fillMaxWidth().padding(24.dp)
                .semantics { liveRegion = LiveRegionMode.Polite }
        ) {
            Icon(Icons.Filled.WifiOff, contentDescription = null, tint = MaterialTheme.colorScheme.error,
                 modifier = Modifier.size(48.dp))
            Spacer(Modifier.height(12.dp))
            Text(titulo, color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Bold, fontSize = 18.sp,
                 textAlign = TextAlign.Center, modifier = Modifier.semantics { heading() })
            Text(texto, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp, lineHeight = 20.sp,
                 textAlign = TextAlign.Center, modifier = Modifier.padding(top = 8.dp, bottom = 20.dp))
            Button(onClick = aoTentar, modifier = Modifier.heightIn(min = 48.dp)) {
                Icon(Icons.Filled.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text(rotulo, fontWeight = FontWeight.Bold)
            }
        }
    }
}

/** Carregando, com o motivo da demora: o servidor gratuito dorme e leva até um minuto para acordar. */
@Composable
fun CarregandoDados(municipio: String?) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.fillMaxWidth().padding(vertical = 32.dp)
            .semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite }
    ) {
        CircularProgressIndicator()
        Spacer(Modifier.height(12.dp))
        Text(municipio?.let { stringResource(R.string.carregando_dados_de, it) } ?: stringResource(R.string.carregando_dados),
             fontSize = 15.sp,
             fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onBackground, textAlign = TextAlign.Center)
        Text(stringResource(R.string.servidor_acorda),
             fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center,
             lineHeight = 16.sp, modifier = Modifier.padding(top = 4.dp))
    }
}

// Números no formato do idioma em que o app abriu: "3.230" em português (e em
// qualquer idioma sem tradução, que mostra o app em português) e "3,230" em
// inglês. MainActivity e AlertasJob leem formato_numeros dos recursos; fora
// deles (testes de unidade, capturas) vale o português.
object Formatos {
    @Volatile
    var locale: java.util.Locale = java.util.Locale("pt", "BR")
        private set
    /** Dia e mês curtos ("26/10"; em inglês, "Oct 26"). */
    @Volatile
    var diaMes: String = "dd/MM"
        private set
    /** Dia, mês e hora ("26/10 às 00:00"; em inglês, "Oct 26 at 00:00"). */
    @Volatile
    var dataHora: String = "dd/MM 'às' HH:mm"
        private set

    fun doIdioma(context: android.content.Context) {
        locale = java.util.Locale.forLanguageTag(context.getString(R.string.formato_numeros))
        diaMes = context.getString(R.string.formato_dia_mes)
        dataHora = context.getString(R.string.formato_data_hora)
    }
}

internal val LOCAL_NUMEROS: java.util.Locale get() = Formatos.locale

fun milhar(v: Double): String = String.format(LOCAL_NUMEROS, "%,d", v.roundToInt())

fun reais(v: Double): String = String.format(LOCAL_NUMEROS, "%,.2f", v)

/**
 * Reais sem centavos, com o sinal antes do símbolo: "−R$ 86", e não "R$ -86".
 * O espaço depois de "R$" não quebra: numa frase longa, o símbolo ficava no fim
 * de uma linha e o número no começo da outra.
 */
fun reaisInteiros(v: Double): String =
    (if (v.roundToInt() < 0) "−" else "") + "R$\u00A0" + milhar(kotlin.math.abs(v))

private val MESES_CURTOS = listOf("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")

/**
 * "2026-10" -> "out/26"; com ano por extenso, "out/2026". Em português, as
 * abreviações sem ponto de MESES_CURTOS; nos outros idiomas, as do idioma
 * ("Oct/26").
 */
fun mesCurto(mes: String, anoCompleto: Boolean = false): String {
    val (ano, m) = mes.split("-").let { it[0] to it[1].toInt() }
    val nome = if (LOCAL_NUMEROS.language == "pt") MESES_CURTOS[m - 1]
               else java.time.Month.of(m).getDisplayName(java.time.format.TextStyle.SHORT, LOCAL_NUMEROS)
    return nome + "/" + if (anoCompleto) ano else ano.takeLast(2)
}

/** Amostra de cor e rótulo de uma legenda de gráfico. */
@Composable
internal fun ItemLegenda(cor: Color, rotulo: String, faixa: Boolean = false, tracejada: Boolean = false) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(end = 14.dp, top = 4.dp)) {
        Canvas(modifier = Modifier.size(width = 18.dp, height = 12.dp)) {
            if (faixa) {
                drawRect(color = cor)
            } else {
                drawLine(
                    color = cor, start = Offset(0f, size.height / 2), end = Offset(size.width, size.height / 2),
                    strokeWidth = 3.dp.toPx(),
                    pathEffect = if (tracejada) PathEffect.dashPathEffect(floatArrayOf(6f, 4f), 0f) else null
                )
            }
        }
        Spacer(Modifier.width(4.dp))
        Text(rotulo, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/**
 * Marcas redondas para um eixo de preço: passo de 1, 2, 2,5 ou 5 vezes uma
 * potência de 10, cobrindo [min, max] com umas quatro divisões. O eixo antes
 * dividia a faixa exata em três e saía com 135,87 / 141,04 / 146,20.
 */
fun eixoRedondo(min: Double, max: Double, divisoes: Int = 4): List<Double> {
    val bruto = (max - min).coerceAtLeast(0.01) / divisoes
    val potencia = Math.pow(10.0, kotlin.math.floor(kotlin.math.log10(bruto)))
    val passo = listOf(1.0, 2.0, 2.5, 5.0, 10.0).first { it * potencia >= bruto } * potencia
    val inicio = kotlin.math.floor(min / passo) * passo
    // Faixa vazia (preço parado) ainda precisa de duas marcas para ter escala.
    val fim = (kotlin.math.ceil(max / passo) * passo).let { if (it <= inicio) inicio + passo else it }
    return generateSequence(inicio) { it + passo }.takeWhile { it <= fim + passo / 2 }.toList()
}

/**
 * Faixa do eixo de preço com pelo menos 1% do preço. Num pregão calmo, ou com
 * poucas velas, a faixa dos dados é de centavos, e o eixo ajustado a ela fazia
 * um movimento de R$ 0,10 parecer uma queda enorme.
 */
fun faixaDoEixo(min: Double, max: Double, fracaoMinima: Double = 0.01): Pair<Double, Double> {
    val minimo = (min + max) / 2 * fracaoMinima
    if (max - min >= minimo) return min to max
    val meio = (min + max) / 2
    return (meio - minimo / 2) to (meio + minimo / 2)
}

/** Rótulo de uma marca: sem casas quando o passo é inteiro ("136"), com duas quando não. */
fun rotuloEixo(v: Double, marcas: List<Double>): String {
    val passo = if (marcas.size > 1) marcas[1] - marcas[0] else 1.0
    return if (passo >= 1 && kotlin.math.abs(passo - passo.roundToInt()) < 1e-9) milhar(v) else reais(v)
}
