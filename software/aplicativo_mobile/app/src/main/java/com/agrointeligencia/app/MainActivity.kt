package com.agrointeligencia.app

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

// OS TRÊS NÚMEROS QUE DECIDEM A MARGEM SÃO DO PRODUTOR.
//
// Este produto é usado por fazendeiro, produtor rural e técnico — não por
// quem escreveu a dissertação. Produtividade, preço e custeio são justamente
// o que essa pessoa conhece melhor que qualquer levantamento ou modelo: ela
// pesou a carga, recebeu o pagamento e pagou as notas.
//
// O padrão serve para a tela abrir com algo plausível. A partir do momento em
// que o produtor informa o dele, é o dele que vale, e fica guardado com a data
// — digitar o próprio custeio e perdê-lo ao fechar o aplicativo é defeito.
private const val PREF_PRECO = "preco_usuario_saca"
private const val PREF_CUSTO = "custo_usuario_ha"
private const val PREF_PROD = "produtividade_usuario_sc"
// Passado esse tempo, o app pede confirmação do preço. Não o descarta: um
// número velho do produtor ainda vale mais que um padrão de levantamento.
private const val DIAS_PARA_RECONFERIR_PRECO = 45L

/** Resultado por hectare e o quanto ele depende do rateio do custo. */
// internal, e não private: o teste de unidade vive no mesmo módulo e precisa
// enxergar. É a margem que o produtor lê na tela — a função que mais merece
// teste no aplicativo inteiro, e a única coisa que a impedia era visibilidade.
internal data class Resultado(
    val valor: Double,
    val outroRateio: Double?,
    /** true quando os dois rateios possíveis discordam sobre lucro ou prejuízo. */
    val sinalIncerto: Boolean,
)

/**
 * Resultado por hectare pelos dois rateios possíveis do custo.
 *
 * A CONAB publica o custo por saca comercializada, sem abrir por item. Tratar
 * o custo variável como fixo por hectare — o que a interface faz, por ser o
 * único caminho com os dados publicados — faz as sacas acima da produtividade
 * de referência entrarem na receita sem onerar colheita, secagem e frete.
 * Tratá-lo como proporcional à produção é o outro extremo.
 *
 * Entre os dois, o SINAL do resultado se inverte sempre que a produtividade
 * supera a de referência e a margem é estreita: em 2022, +R$ 188 ou -R$ 153
 * por hectare, com os mesmos dados. Um produto que pinta isso de verde manda
 * o produtor decidir com uma certeza que o dado não sustenta.
 *
 * Quando o produtor informa o próprio custo não há rateio a discutir: o número
 * é dele, e a função devolve só ele.
 */
internal fun resultadoPorHectare(
    sacasPorHectare: Double,
    preco: Double,
    custoDoProdutor: Double?,
    kpis: FinancaResponse
): Resultado {
    val receita = sacasPorHectare * preco
    if (custoDoProdutor != null) {
        return Resultado(receita - custoDoProdutor, null, false)
    }
    val porHectare = receita - kpis.custo_ha
    val variavel = kpis.custo_variavel_saca
    val fixo = kpis.custo_fixo_ha
    if (variavel == null || fixo == null) {
        return Resultado(porHectare, null, false)
    }
    val porSaca = receita - (variavel * sacasPorHectare + fixo)
    return Resultado(porHectare, porSaca, (porHectare > 0) != (porSaca > 0))
}

// O valor que o produtor digita é dinheiro, e dinheiro não cabe em float de
// 32 bits: 135,15 vira 135.14999389648438 na volta, porque não existe em
// binário de 32 bits. Guardado assim, o campo devolvia ao produtor um número
// que ele não digitou. Vai em Double, pelos bits, que é o jeito de pôr um
// Double em SharedPreferences — ela só conhece Long.
private fun SharedPreferences.valorDoProdutor(chave: String): Double? {
    val bruto = try {
        getLong(chave, 0L).takeIf { it != 0L }?.let { Double.fromBits(it) }
    } catch (_: ClassCastException) {
        // Instalação anterior a esta versão: a chave ainda guarda um Float.
        // Lê, converte e segue — a próxima gravação já sai em Double, e
        // ninguém precisa redigitar o preço dele por causa da nossa correção.
        getFloat(chave, -1f).takeIf { it > 0f }?.toDouble()
    }
    return bruto?.takeIf { it > 0.0 }
}

private fun SharedPreferences.informadoEm(chave: String): Long =
    getLong(chave + "_em", 0L)

private fun SharedPreferences.guardarDoProdutor(chave: String, valor: Double, quando: Long) {
    edit().putLong(chave, valor.toRawBits()).putLong(chave + "_em", quando).apply()
}

private fun SharedPreferences.esquecerDoProdutor(vararg chaves: String) {
    val editor = edit()
    for (chave in chaves) {
        editor.remove(chave)
        editor.remove(chave + "_em")
    }
    editor.apply()
}

/**
 * Cores do aplicativo. O texto secundário (onSurfaceVariant) e as linhas de
 * grade e divisórias (outlineVariant) são definidos aqui, e não com Color.Gray
 * espalhado pelas telas: o cinza fixo tinha contraste de 3,5:1 sobre o branco,
 * abaixo dos 4,5:1 recomendados para texto pequeno; estes passam de 7:1.
 */
fun esquemaAgro(isDark: Boolean): ColorScheme = if (isDark) {
    darkColorScheme(
        background = Color(0xFF0F172A),
        surface = Color(0xFF1E293B),
        primary = Color(0xFF10B981),
        onBackground = Color(0xFFE2E8F0),
        onSurface = Color(0xFFE2E8F0),
        onSurfaceVariant = Color(0xFFCBD5E1),
        outlineVariant = Color(0xFF334155)
    )
} else {
    lightColorScheme(
        background = Color(0xFFF8FAFC),
        surface = Color(0xFFFFFFFF),
        primary = Color(0xFF047857),
        onBackground = Color(0xFF1E293B),
        onSurface = Color(0xFF1E293B),
        onSurfaceVariant = Color(0xFF475569),
        outlineVariant = Color(0xFFE2E8F0)
    )
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val isDark = isSystemInDarkTheme()
            val colors = esquemaAgro(isDark)
            MaterialTheme(
                colorScheme = colors
            ) {
                val view = LocalView.current
                if (!view.isInEditMode) {
                    SideEffect {
                        val window = (view.context as Activity).window
                        @Suppress("DEPRECATION")
                        window.statusBarColor = colors.background.toArgb()
                        @Suppress("DEPRECATION")
                        window.navigationBarColor = colors.surface.toArgb()
                        WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !isDark
                        WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = !isDark
                    }
                }
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    AgroDashboard()
                }
            }
        }
    }
}

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
fun AvisoSemDados(titulo: String, texto: String, aoTentar: () -> Unit) {
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
                Text("Tentar de novo", fontWeight = FontWeight.Bold)
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
        Text("Carregando os dados" + (municipio?.let { " de $it" } ?: "") + "…", fontSize = 15.sp,
             fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onBackground, textAlign = TextAlign.Center)
        Text("Na primeira consulta do dia o servidor pode levar até um minuto para responder.",
             fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center,
             lineHeight = 16.sp, modifier = Modifier.padding(top = 4.dp))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgroDashboard() {
    val coroutineScope = rememberCoroutineScope()
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current
    val sharedPrefs = remember { context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE) }
    val gson = remember { Gson() }
    val avisos = remember { SnackbarHostState() }
    var municipios by remember { mutableStateOf<List<String>>(emptyList()) }
    // O último município escolhido. Nulo na primeira abertura: o app pergunta
    // qual é, em vez de abrir no primeiro da lista (Municipio.kt).
    var selectedMunicipio by remember { mutableStateOf(sharedPrefs.getString(PREF_MUNICIPIO, null)) }
    var previsao by remember { mutableStateOf<PrevisaoResponse?>(null) }
    var previsaoEm by remember { mutableStateOf(0L) }
    var kpis by remember { mutableStateOf<FinancaResponse?>(null) }
    // Duas cargas independentes, cada uma com o seu indicador: com um só, a
    // que terminava primeiro escondia o "carregando" da outra.
    var carregandoLista by remember { mutableStateOf(false) }
    var carregandoPrevisao by remember { mutableStateOf(false) }
    val isLoading = carregandoLista || carregandoPrevisao
    var errorMsg by remember { mutableStateOf<String?>(null) }
    // Salvável: a câmera da Estimativa no campo pode levar o Android a
    // encerrar o app, e na volta ele precisa reabrir na mesma tela.
    var currentTab by rememberSaveable { mutableStateOf(0) }
    var isOfflineMode by remember { mutableStateOf(false) }
    var mostrarLista by rememberSaveable { mutableStateOf(false) }
    // Aumenta a cada "atualizar" e refaz a busca da previsão do município.
    var recarga by remember { mutableStateOf(0) }
    // Preço estimado do Pará agora, para a Viabilidade oferecer em um toque.
    // Sem cache: um preço de mercado guardado envelhece, e aí é melhor não oferecer.
    var mercadoHoje by remember { mutableStateOf<MercadoResponse?>(null) }
    LaunchedEffect(recarga) {
        try {
            mercadoHoje = RetrofitClient.getInstance().getMercado("1d")
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (_: Exception) {
        }
    }

    // Previsão do tempo (Tempo.kt): vem do Open-Meteo, e não da API, e por
    // isso carrega mesmo com a API dormindo. Serve o cartão do Resumo e a tela.
    val tempo = remember { EstadoTempo(sharedPrefs) }
    val lugarTempo = tempo.lugarPara(selectedMunicipio)
    LaunchedEffect(lugarTempo) { lugarTempo?.let { tempo.carrega(it) } }

    // Mensagens curtas na barra de baixo; o TalkBack as lê em voz alta.
    fun avisar(msg: String) {
        coroutineScope.launch {
            avisos.currentSnackbarData?.dismiss()
            avisos.showSnackbar(msg)
        }
    }

    fun escolherMunicipio(mun: String) {
        selectedMunicipio = mun
        sharedPrefs.edit().putString(PREF_MUNICIPIO, mun).apply()
    }

    // GPS para o município: a sede mais próxima entre os da lista, calculada
    // no celular. A posição não é guardada nem enviada.
    val leitorMunicipio = rememberLeitorDePosicao(
        semPermissao = "Sem a permissão de localização, escolha o município na lista.",
        aoFalhar = { avisar(it) }
    ) { lat, lon ->
        val candidatos = municipios.ifEmpty { SEDES_MUNICIPAIS.keys.toList() }
        val proximo = municipioMaisProximo(lat, lon, candidatos)
        if (proximo == null) {
            avisar("Não foi possível achar um município da lista perto de você. Escolha na lista.")
        } else {
            escolherMunicipio(proximo.nome)
            mostrarLista = false
            avisar(fraseDoMaisProximo(proximo, candidatos.size))
        }
    }

    fun loadData() {
        errorMsg = null

        // Acorda a API do Render sem esperar a resposta.
        coroutineScope.launch {
            try { RetrofitClient.getInstance().ping() } catch (_: Exception) {}
            // Com a API acordada, confere se há modelo novo do contador de
            // vagens (no máximo uma vez por dia; ver AtualizaContador.kt).
            withContext(Dispatchers.IO) { atualizaContador(context) }
        }

        // Primeiro o que está guardado, para a tela abrir na hora.
        val cachedMunStr = sharedPrefs.getString("municipios", null)
        val cachedKpiStr = sharedPrefs.getString("kpis", null)
        if (cachedMunStr != null && cachedKpiStr != null) {
            municipios = gson.fromJson(cachedMunStr, MunicipioResponse::class.java).municipios
            selectedMunicipio = municipioGuardadoValido(municipios, selectedMunicipio)
            kpis = gson.fromJson(cachedKpiStr, FinancaResponse::class.java)
        } else {
            carregandoLista = true
        }

        // Depois a versão do servidor, sem bloquear a tela.
        coroutineScope.launch {
            try {
                val response = RetrofitClient.getInstance().getMunicipios()
                // Preço e custo são os da CONAB para o estado: de um município
                // para outro só muda o VTN, que o aplicativo não mostra.
                val kpisResponse = RetrofitClient.getInstance().getFinancas("Paragominas")
                municipios = response.municipios
                selectedMunicipio = municipioGuardadoValido(municipios, selectedMunicipio)
                kpis = kpisResponse
                sharedPrefs.edit()
                    .putString("municipios", gson.toJson(response))
                    .putString("kpis", gson.toJson(kpisResponse))
                    .apply()
                errorMsg = null
            } catch (e: Exception) {
                e.printStackTrace()
                if (cachedMunStr == null) {
                    errorMsg = "Erro na API: ${e.message}"
                }
            } finally {
                carregandoLista = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadData()
    }

    // A Estimativa no campo e o Tempo não têm item na barra de baixo; o voltar
    // do celular leva de volta ao Resumo, de onde eles são abertos.
    BackHandler(enabled = currentTab == 5 || currentTab == 6) { currentTab = 0 }

    // A previsão do município corre dentro do efeito, e não num escopo de fora:
    // trocar de município cancela a busca anterior. Antes as duas corriam
    // juntas, e a resposta do município velho, se chegasse por último, ficava
    // na tela com o nome do novo.
    LaunchedEffect(selectedMunicipio, recarga) {
        val mun = selectedMunicipio
        if (mun == null) {
            previsao = null
            return@LaunchedEffect
        }
        val guardada = sharedPrefs.getString("previsao_$mun", null)
            ?.let { runCatching { gson.fromJson(it, PrevisaoResponse::class.java) }.getOrNull() }
        previsao = guardada
        previsaoEm = if (guardada != null) sharedPrefs.getLong("previsao_${mun}_em", 0L) else 0L
        // O "carregando" só aparece quando não há nada guardado do município.
        carregandoPrevisao = guardada == null
        try {
            val resposta = RetrofitClient.getInstance().getPrevisao(mun)
            previsao = resposta
            previsaoEm = System.currentTimeMillis()
            sharedPrefs.edit()
                .putString("previsao_$mun", gson.toJson(resposta))
                .putLong("previsao_${mun}_em", previsaoEm)
                .apply()
            isOfflineMode = false
            carregandoPrevisao = false
        } catch (e: kotlinx.coroutines.CancellationException) {
            // Trocou de município: o efeito novo cuida do indicador.
            throw e
        } catch (e: Exception) {
            e.printStackTrace()
            isOfflineMode = true
            carregandoPrevisao = false
        }
    }

    if (mostrarLista) {
        EscolhaMunicipioDialog(
            municipios = municipios,
            atual = selectedMunicipio,
            procurandoPosicao = leitorMunicipio.procurando,
            aoUsarPosicao = { leitorMunicipio.ler() },
            aoEscolher = { mun ->
                escolherMunicipio(mun)
                mostrarLista = false
            },
            aoFechar = { mostrarLista = false }
        )
    }

    fun irPara(aba: Int) {
        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        currentTab = aba
    }

    Scaffold(
        snackbarHost = { SnackbarHost(avisos) },
        bottomBar = {
            // O rótulo já diz o nome da aba: o ícone fica sem descrição, senão
            // o leitor de tela lia "Resumo, Resumo".
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                NavigationBarItem(
                    selected = currentTab == 0,
                    onClick = { irPara(0) },
                    icon = { Icon(Icons.Filled.Home, contentDescription = null) },
                    label = { Text("Resumo") }
                )
                NavigationBarItem(
                    selected = currentTab == 1,
                    onClick = { irPara(1) },
                    icon = { Icon(Icons.Filled.LocationOn, contentDescription = null) },
                    label = { Text("Mapa") }
                )
                @Suppress("DEPRECATION")
                NavigationBarItem(
                    selected = currentTab == 2,
                    onClick = { irPara(2) },
                    icon = { Icon(Icons.Filled.List, contentDescription = null) },
                    label = { Text("Histórico") }
                )
                NavigationBarItem(
                    selected = currentTab == 4,
                    onClick = { irPara(4) },
                    icon = { Icon(Icons.Filled.CandlestickChart, contentDescription = null) },
                    label = { Text("Mercado") }
                )
                NavigationBarItem(
                    selected = currentTab == 3,
                    onClick = { irPara(3) },
                    icon = { Icon(Icons.Filled.Info, contentDescription = null) },
                    label = { Text("Sobre") }
                )
            }
        }
    ) { paddingValues ->
        val isDark = isSystemInDarkTheme()
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            userScrollEnabled = currentTab != 1
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Filled.Agriculture, contentDescription = null, tint = MaterialTheme.colorScheme.primary,
                             modifier = Modifier.size(28.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = "AgroInteligência",
                            fontSize = 24.sp,
                            fontWeight = FontWeight.ExtraBold,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.weight(1f).semantics { heading() }
                        )
                        if (currentTab in 0..2 && selectedMunicipio != null) {
                            IconButton(onClick = { loadData(); recarga++ }, enabled = !isLoading) {
                                Icon(Icons.Filled.Refresh, contentDescription = "Atualizar os dados")
                            }
                        }
                    }

                    if (isOfflineMode) {
                        val cor = corAtencao(isDark)
                        val quando = previsaoEm.takeIf { it > 0 }?.let {
                            java.text.SimpleDateFormat("dd/MM 'às' HH:mm", PT_BR).format(java.util.Date(it))
                        }
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite }
                        ) {
                            Icon(Icons.Filled.WifiOff, contentDescription = null, tint = cor, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(6.dp))
                            Text(
                                text = if (quando != null) "Sem conexão: mostrando os dados guardados em $quando."
                                       else "Sem conexão: mostrando os últimos dados guardados.",
                                fontSize = 12.sp, color = cor, fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    // O município só muda Resumo, Mapa e Histórico; em Mercado e
                    // Sobre o seletor ocupava a tela sem efeito.
                    if (currentTab in 0..2) {
                        if (selectedMunicipio == null) {
                            BoasVindasMunicipio(
                                procurandoPosicao = leitorMunicipio.procurando,
                                aoUsarPosicao = { leitorMunicipio.ler() },
                                aoAbrirLista = { mostrarLista = true }
                            )
                        } else {
                            SeletorMunicipio(
                                municipio = selectedMunicipio,
                                procurandoPosicao = leitorMunicipio.procurando,
                                aoAbrirLista = { mostrarLista = true },
                                aoUsarPosicao = { leitorMunicipio.ler() }
                            )
                        }
                    }

                    // Fora do bloco da previsão de produtividade: o tempo aparece
                    // mesmo enquanto a API acorda ou quando ela falha.
                    if (currentTab == 0 && lugarTempo != null) {
                        TempoResumoCard(tempo) { currentTab = 6 }
                    }
                }
            }

            val prev = previsao
            when {
                currentTab == 4 -> item {
                    // A cotação não depende da previsão do município: a aba abre
                    // mesmo quando a previsão ainda não carregou ou falhou.
                    MercadoCard()
                }
                currentTab == 5 -> item {
                    // Como o Mercado, não depende da previsão: a contagem no campo
                    // funciona sem rede. A previsão, se houver, entra para comparação.
                    val projecao = prev?.historico?.let { projecaoDaSafra(it) }
                    EstimativaCampoTela(
                        precoPadrao = sharedPrefs.valorDoProdutor(PREF_PRECO) ?: kpis?.soja_preco_saca,
                        fontePreco = if (sharedPrefs.valorDoProdutor(PREF_PRECO) != null) "Seu preço, informado na Viabilidade."
                                     else kpis?.fonte_preco?.let { "Preço de referência: $it." },
                        referenciaKgHa = projecao?.rendimento_predito,
                        rotuloReferencia = projecao?.let { "${prev?.municipio ?: selectedMunicipio} em ${it.ano}" },
                        aoVoltar = { currentTab = 0 }
                    )
                }
                currentTab == 6 -> item {
                    TempoTela(tempo, selectedMunicipio) { currentTab = 0 }
                }
                // O Sobre traz o aviso de não afiliação e as fontes oficiais que
                // o Google Play exige: abre sempre, com ou sem previsão carregada.
                currentTab == 3 -> item {
                    MetodologiaCard(kpis, prev?.validacao)
                }
                currentTab == 1 -> item {
                    if (isOfflineMode) {
                        Column(
                            modifier = Modifier.fillMaxWidth().height(400.dp),
                            verticalArrangement = Arrangement.Center,
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(Icons.Filled.WifiOff, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                 modifier = Modifier.size(64.dp))
                            Spacer(modifier = Modifier.height(16.dp))
                            // Nunca houve imagem de satélite aqui: o mapa é vetorial,
                            // com o contorno do Pará da malha do IBGE, rios do Natural
                            // Earth e círculos coloridos pela produtividade observada.
                            Text("Mapa indisponível sem conexão", fontWeight = FontWeight.Bold,
                                 color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 16.sp)
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("O mapa é desenhado pelo servidor. Conecte-se para carregá-lo.",
                                 color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp, textAlign = TextAlign.Center)
                        }
                    } else {
                        Card(
                            modifier = Modifier.fillParentMaxHeight(0.82f).fillMaxWidth().padding(1.dp)
                                .semantics {
                                    contentDescription = "Mapa da produtividade da soja nos municípios do Pará" +
                                        (selectedMunicipio?.let { ", com $it em destaque" } ?: "")
                                },
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            val currentTheme = if (isDark) "dark" else "light"
                            val mapUrl = "https://agrointeligencia-api.onrender.com/api/mapa/render?theme=${currentTheme}" +
                                (selectedMunicipio?.let { "&municipio=${URLEncoder.encode(it, "UTF-8")}" } ?: "")
                            // Lembra a última URL para não recarregar a cada recomposição.
                            var lastLoadedUrl by remember { mutableStateOf("") }
                            AndroidView(
                                factory = { ctx ->
                                    WebView(ctx).apply {
                                        layoutParams = android.view.ViewGroup.LayoutParams(
                                            android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                                            android.view.ViewGroup.LayoutParams.MATCH_PARENT
                                        )
                                        settings.javaScriptEnabled = true
                                        settings.domStorageEnabled = true
                                        settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
                                        setLayerType(android.view.View.LAYER_TYPE_SOFTWARE, null)
                                        webViewClient = WebViewClient()
                                        loadUrl(mapUrl)
                                        lastLoadedUrl = mapUrl
                                    }
                                },
                                update = { webView ->
                                    if (mapUrl != lastLoadedUrl) {
                                        webView.loadUrl(mapUrl)
                                        lastLoadedUrl = mapUrl
                                    }
                                },
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                    }
                }
                isLoading -> item {
                    CarregandoDados(selectedMunicipio)
                }
                errorMsg != null -> item {
                    AvisoSemDados(
                        titulo = "Sem conexão com o servidor",
                        texto = "Não foi possível baixar a lista de municípios e as estimativas. O servidor pode " +
                                "levar até um minuto para acordar: confira a internet e tente de novo. " +
                                "A Estimativa no campo funciona sem internet."
                    ) { loadData(); recarga++ }
                }
                // Primeira abertura: o cartão de boas-vindas, lá em cima, pergunta o município.
                selectedMunicipio == null -> {}
                prev == null -> item {
                    AvisoSemDados(
                        titulo = "Sem dados de $selectedMunicipio neste celular",
                        texto = "A estimativa deste município ainda não foi baixada. Confira a internet e tente de novo."
                    ) { recarga++ }
                }
                else -> {
                    val historicoOrdenado = prev.historico.sortedByDescending { it.ano }
                    // A safra em curso, e não a projeção mais distante (Safra.kt).
                    val projecao = projecaoDaSafra(prev.historico)
                    val ultimoReal = ultimoObservado(prev.historico)
                    val baseSimulador = projecaoDoSimulador(prev.historico) ?: projecao

                    if (currentTab == 0) { // Resumo
                        item {
                            AtalhoEstimativaCampo { currentTab = 5 }
                        }
                        if (projecao != null) {
                            item {
                                TituloSecao(Icons.Filled.BarChart, "Resumo Agronômico (safra ${projecao.ano})")
                                ResumoAgronomicoCard(projecao, ultimoReal)
                            }
                            item {
                                TituloSecao(Icons.Filled.SettingsSuggest, "Simulador de cenário climático",
                                            Modifier.padding(top = 8.dp))
                                CenarioClimaticoCard(municipio = selectedMunicipio ?: prev.municipio,
                                                     baselineRendimento = (baseSimulador ?: projecao).rendimento_predito,
                                                     ano = (baseSimulador ?: projecao).ano)
                            }
                            kpis?.let { k ->
                                item {
                                    TituloSecao(Icons.Filled.MonetizationOn, "Viabilidade Financeira",
                                                Modifier.padding(top = 8.dp))
                                    ResumoFinanceiroCard(projecao, k, mercadoHoje?.para,
                                                         mercadoHoje?.pracas_para.orEmpty(), selectedMunicipio)
                                }
                            }
                        }
                    } else if (currentTab == 2) { // Histórico
                        item {
                            TituloSecao(Icons.Filled.DateRange, "Histórico Completo", Modifier.padding(top = 8.dp))
                            Text(
                                text = "A estimativa das safras passadas parte do histórico " +
                                       "do município e da tendência, com o clima médio da série. " +
                                       "Ela não é uma previsão refeita ano a ano.",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                lineHeight = 16.sp,
                                modifier = Modifier.padding(top = 6.dp, bottom = 4.dp)
                            )
                        }
                        item {
                            HistoricoProdutividadeChart(historico = historicoOrdenado, previsao = prev)
                        }
                        items(historicoOrdenado) { hist ->
                            PrevisaoCard(hist, kpis)
                        }
                    }
                }
            }
        }
    }
}

/** Entrada da Estimativa no campo, no alto do Resumo. */
@Composable
fun AtalhoEstimativaCampo(aoAbrir: () -> Unit) {
    Card(
        onClick = aoAbrir,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.10f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(16.dp)) {
            Icon(Icons.Filled.CameraAlt, contentDescription = null, tint = MaterialTheme.colorScheme.primary,
                 modifier = Modifier.size(28.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("Estimativa no campo", fontWeight = FontWeight.SemiBold, fontSize = 16.sp,
                     color = MaterialTheme.colorScheme.onSurface)
                Text("Fotografe, conte plantas e vagens e veja a produtividade da sua lavoura.",
                     fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp)
            }
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable
fun PrevisaoCard(historico: PrevisaoHistorico, kpis: FinancaResponse?) {
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
                           else situacaoSemDado(historico.ano),
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
                text = String.format(PT_BR, "Estimativa %,d kg/ha · erro típico ± %,d kg/ha", 
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
                    kgHa / 60, precoDoProdutor ?: kpis.soja_preco_saca, custoDoProdutor, kpis)
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
fun ResumoAgronomicoCard(projecao: PrevisaoHistorico, ultimoReal: PrevisaoHistorico?) {
    val isDark = isSystemInDarkTheme()
    Card(
        modifier = Modifier.animateContentSize(animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessLow)).fillMaxWidth().padding(top = 8.dp, bottom = 8.dp),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            val projYield = projecao.rendimento_predito
            Text(text = "Produtividade esperada na safra ${projecao.ano}", fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = "${milhar(projYield)} kg/ha", 
                    fontSize = 28.sp, 
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(text = " (~ ${(projYield / 60).roundToInt()} sc/ha)", fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = 8.dp, bottom = 4.dp))
            }
            // O erro típico vai junto do número: é uma estimativa, e a loja
            // promete a margem de erro sempre ao lado dela.
            if (projecao.margem_erro > 0) {
                Text(text = "Estimativa do modelo, com erro típico de ± ${milhar(projecao.margem_erro)} kg/ha.",
                     fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            
            if (ultimoReal != null) {
                val pastYield = if (ultimoReal.rendimento_real > 0) ultimoReal.rendimento_real else ultimoReal.rendimento_predito
                val typeStr = if (ultimoReal.rendimento_real > 0) "IBGE" else "estimada"
                val diff = projYield - pastYield
                val diffPct = if (pastYield > 0) (diff / pastYield) * 100 else 0.0
                val color = if (diff >= 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626))
                val sign = if (diff >= 0) "+" else ""
                
                Spacer(modifier = Modifier.height(16.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column {
                        Text(text = "Safra ${ultimoReal.ano}, $typeStr", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(text = "${milhar(pastYield)} kg/ha", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        // Entre a safra esperada e a última divulgada pode haver
                        // mais de um ano: "variação anual" dizia outra coisa.
                        Text(text = "Em relação a ${ultimoReal.ano}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(text = "$sign${diffPct.roundToInt()}%", fontSize = 16.sp, color = color, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

@Composable
fun ResumoFinanceiroCard(
    projecao: PrevisaoHistorico,
    kpis: FinancaResponse,
    paraHoje: EstimativaPara? = null,
    pracas: List<PracaPara> = emptyList(),
    municipio: String? = null
) {
    // A cotação do dia na praça do Pará mais perto do município; sem ela, a
    // média do Pará estimada com Chicago e a base do mês.
    val praca = remember(pracas, municipio) { pracaParaUsar(municipio, pracas) }
    val precoHoje: Double? = praca?.valor ?: paraHoje?.estimado_brl_saca
    val rotuloHoje: String = praca?.let { "${it.praca}, ${dataCurta(it.data)}" } ?: "Pará, estimado agora"
    val isDark = isSystemInDarkTheme()
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE) }

    // Ver o comentário das constantes PREF_*: os três números são do produtor,
    // e o padrão só existe para a tela abrir com algo plausível.
    //
    // A produtividade é a que mais desloca o resultado. A estimativa sai da
    // PAM, e a própria pesquisa mostrou que a PAM arredonda para sacas
    // inteiras e trava em platôs: dois terços dos registros da base são
    // múltiplos exatos de 60 kg. Quem colheu 65 sacas não deve ver a margem
    // calculada sobre 55 porque a estatística oficial arredondou.
    val precoSalvo = remember { prefs.valorDoProdutor(PREF_PRECO) }
    val custoSalvo = remember { prefs.valorDoProdutor(PREF_CUSTO) }
    val prodSalva = remember { prefs.valorDoProdutor(PREF_PROD) }
    // Teclado numérico nos três campos: no teclado de letras, o produtor
    // tinha de trocar de teclado para digitar cada número.
    val tecladoNumero = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Next)
    val prodModelo = projecao.rendimento_predito / 60.0

    // Os três carimbos de "informado em" são estado, e os três se declaram
    // aqui. Antes só o preço era: custo e produtividade eram lidos do disco
    // dentro da composição, na hora de montar a legenda. Funcionava por
    // acidente — editar qualquer campo provoca recomposição, e a leitura se
    // refazia —, mas era I/O em @Composable e tratamento diferente para três
    // coisas iguais, que é como um bug entra quando alguém mexer perto.
    var precoEm by remember { mutableStateOf(prefs.informadoEm(PREF_PRECO)) }
    var custoEm by remember { mutableStateOf(prefs.informadoEm(PREF_CUSTO)) }
    var prodEm by remember { mutableStateOf(prefs.informadoEm(PREF_PROD)) }
    var temPreco by remember { mutableStateOf(precoSalvo != null) }
    var temCusto by remember { mutableStateOf(custoSalvo != null) }
    var temProd by remember { mutableStateOf(prodSalva != null) }

    // Os três campos são formatados, e não impressos com toString(). Preço e
    // custo são dinheiro e param em centavos; produtividade, em décimos de
    // saca. Sem isto o campo exibia a representação binária inteira — foi
    // assim que 135,15 apareceu ao produtor como 135.14999389648438.
    var customPreco by remember {
        mutableStateOf(String.format(PT_BR, "%.2f", precoSalvo ?: kpis.soja_preco_saca))
    }
    var customCusto by remember {
        mutableStateOf(String.format(PT_BR, "%.2f", custoSalvo ?: kpis.custo_ha))
    }
    // Com a chave, o campo acompanha o município: sem ela, ao trocar de
    // município, seguia a estimativa do anterior até o produtor redigitar.
    var customProd by remember(prodModelo) {
        mutableStateOf(String.format(PT_BR, "%.1f", prefs.valorDoProdutor(PREF_PROD) ?: prodModelo))
    }

    Card(
        modifier = Modifier.animateContentSize(animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessLow)).fillMaxWidth().padding(top = 8.dp, bottom = 8.dp),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            val preco = customPreco.replace(',', '.').toDoubleOrNull() ?: kpis.soja_preco_saca
            val custo = customCusto.replace(',', '.').toDoubleOrNull() ?: kpis.custo_ha
            val scHa = customProd.replace(',', '.').toDoubleOrNull() ?: prodModelo
            val diasDoPrecoProprio =
                if (temPreco && precoEm > 0L)
                    (System.currentTimeMillis() - precoEm) / 86_400_000L
                else -1L

            // Os avisos vêm ANTES dos campos, não como nota de rodapé: quem for
            // ler a margem precisa saber de onde vem o número antes de lê-la.
            // O texto é do servidor, que sabe que dia é hoje — sem ele, este
            // aplicativo mostraria 2026 como se fosse agora, para sempre.
            //
            // Com preço próprio informado, o aviso do preço perde sentido, mas
            // o CUSTO continua saindo do mesmo levantamento velho e entrando na
            // margem: aí o alerta troca de assunto em vez de sumir.
            val alerta = when {
                temPreco && diasDoPrecoProprio >= DIAS_PARA_RECONFERIR_PRECO ->
                    "Você informou este preço há $diasDoPrecoProprio dias. Confirme se ainda é o que recebe."
                // Com preço próprio, o custo é que continua vindo do
                // levantamento — a menos que o produtor já tenha informado o
                // dele também, e aí não há o que avisar.
                temPreco && !temCusto -> kpis.aviso_custo
                // Com o número de hoje ao lado, o produtor vê o tamanho da
                // defasagem em vez de só ler que ela existe.
                // Curto: a idade do padrão e, ao lado, o preço de hoje. O texto
                // longo do servidor fica só quando ele não manda a idade.
                else -> {
                    val meses = kpis.defasagem_meses
                    val hoje = precoHoje?.let { " $rotuloHoje: R$\u00A0${reais(it)}/sc." } ?: ""
                    when {
                        meses == null -> kpis.aviso_preco?.let { "Preço possivelmente desatualizado. $it" }
                        meses >= 12 -> "Preço padrão da CONAB de mais de um ano atrás.$hoje"
                        meses >= 5 -> "Preço padrão da CONAB de $meses meses atrás.$hoje"
                        else -> null
                    }
                }
            }
            alerta?.let {
                Text(
                    text = it,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                    color = corAtencao(isDark),
                    modifier = Modifier.padding(bottom = 12.dp)
                )
            }

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                OutlinedTextField(
                    value = customProd,
                    onValueChange = { digitado ->
                        customProd = digitado
                        // Guarda assim que o número for válido: o produtor não
                        // deve precisar apertar nada para o app lembrar.
                        val valor = digitado.replace(',', '.').toDoubleOrNull()
                        if (valor != null && valor > 0) {
                            temProd = true
                            prodEm = System.currentTimeMillis()
                            prefs.guardarDoProdutor(PREF_PROD, valor, prodEm)
                        }
                    },
                    label = { Text(if (temProd) "Sua produtividade (sc/ha)" else "Produtividade (sc/ha)", fontSize = 12.sp) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    keyboardOptions = tecladoNumero,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9),
                        unfocusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9)
                    )
                )
                OutlinedTextField(
                    value = customPreco,
                    onValueChange = { digitado ->
                        customPreco = digitado
                        // Guarda assim que o número for válido: o produtor não
                        // deve precisar apertar nada para o app lembrar.
                        val valor = digitado.replace(',', '.').toDoubleOrNull()
                        if (valor != null && valor > 0) {
                            temPreco = true
                            precoEm = System.currentTimeMillis()
                            prefs.guardarDoProdutor(PREF_PRECO, valor, precoEm)
                        }
                    },
                    label = { Text(if (temPreco) "Seu preço (R$/sc)" else "Preço da saca (R$)", fontSize = 12.sp) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    keyboardOptions = tecladoNumero,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9),
                        unfocusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9)
                    )
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                OutlinedTextField(
                    value = customCusto,
                    onValueChange = { digitado ->
                        customCusto = digitado
                        // Guarda assim que o número for válido: o produtor não
                        // deve precisar apertar nada para o app lembrar.
                        val valor = digitado.replace(',', '.').toDoubleOrNull()
                        if (valor != null && valor > 0) {
                            temCusto = true
                            custoEm = System.currentTimeMillis()
                            prefs.guardarDoProdutor(PREF_CUSTO, valor, custoEm)
                        }
                    },
                    label = { Text(if (temCusto) "Seu custo/ha (R$)" else "Custo/ha (R$)", fontSize = 12.sp) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Done),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9),
                        unfocusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9)
                    )
                )
                // Mantém a largura das colunas igual à da linha de cima.
                Spacer(modifier = Modifier.weight(1f))
            }

            // O preço do Pará de hoje, a um toque. O padrão é o levantamento da
            // CONAB, que pode ter meses, e o produtor não tinha como trazer o
            // mercado para a conta sem ir à tela Mercado e copiar o número.
            precoHoje?.let { pa ->
                val usandoEste = temPreco && kotlin.math.abs(preco - pa) < 0.005
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp)
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("$rotuloHoje: R$ ${reais(pa)}/sc", fontSize = 13.sp,
                             fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                        Text(if (praca != null) "Cotação do dia na praça (Agrolink); na fazenda pode ser menor, pelo frete."
                             else "Chicago agora + base do Pará no mês; na fazenda pode ser menor.",
                             fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp)
                    }
                    if (usandoEste) {
                        Text("Em uso", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary,
                             fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(start = 8.dp))
                    } else {
                        TextButton(onClick = {
                            customPreco = String.format(PT_BR, "%.2f", pa)
                            temPreco = true
                            precoEm = System.currentTimeMillis()
                            prefs.guardarDoProdutor(PREF_PRECO, pa, precoEm)
                        }) {
                            Text("Usar este preço")
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))
            // A legenda diz, em linguagem de campo, o que é do produtor e o que
            // ainda é padrão. Quem usa isto no talhão precisa saber de onde vem
            // o número antes de decidir com ele.
            val seus = listOfNotNull(
                if (temProd) "produtividade" else null,
                if (temPreco) "preço" else null,
                if (temCusto) "custo" else null
            )
            val quando = java.text.SimpleDateFormat("dd/MM/yyyy", PT_BR)
            // "Informados em" com uma data só deixava dúvida: era a data do
            // preço digitado ou a da cotação? Agora cada número diz quando foi
            // informado pelo produtor.
            val datas = listOfNotNull(
                if (temProd && prodEm > 0L) "a produtividade em ${quando.format(java.util.Date(prodEm))}" else null,
                if (temPreco && precoEm > 0L) "o preço em ${quando.format(java.util.Date(precoEm))}" else null,
                if (temCusto && custoEm > 0L) "o custo em ${quando.format(java.util.Date(custoEm))}" else null
            )
            // Duas frases: o que é do produtor (e quando informou) e o que
            // ainda é padrão. A nota sobre a série de preços da CONAB fica no
            // Sobre; o físico de outro estado, no Mercado.
            val conab = kpis.fonte_preco?.removePrefix("CONAB, ")
            val daConab = listOfNotNull(if (temPreco) null else "preço", if (temCusto) null else "custo")
            val padrao = listOfNotNull(
                if (temProd) null else "produtividade do modelo",
                if (daConab.isNotEmpty() && conab != null) juntaComE(daConab) + " da CONAB ($conab)" else null
            )
            val legenda = listOfNotNull(
                when {
                    datas.isNotEmpty() -> "Você informou ${juntaComE(datas)}." +
                        (if (temPreco) " Seu preço não muda sozinho com o mercado." else "")
                    seus.isNotEmpty() -> "Seus números: " + seus.joinToString(", ") + "."
                    else -> null
                },
                if (padrao.isEmpty()) null
                else "Padrão: ${juntaComE(padrao)}." + (if (seus.isEmpty()) " Toque num campo para usar os seus números." else ""),
                kpis.preco_fisico?.takeIf { it.uf == "PA" }?.let { "Físico hoje em ${it.praca}: R$\u00A0${reais(it.valor)}/sc." }
            ).joinToString(" ")
            if (legenda.isNotBlank()) {
                Text(text = legenda, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (seus.isNotEmpty()) {
                // Caminho de volta, para ninguém ficar preso a um número
                // digitado errado sem saber de onde vinha o padrão.
                TextButton(
                    onClick = {
                        prefs.esquecerDoProdutor(PREF_PRECO, PREF_CUSTO, PREF_PROD)
                        temPreco = false; temCusto = false; temProd = false
                        precoEm = 0L; custoEm = 0L; prodEm = 0L
                        customPreco = String.format(PT_BR, "%.2f", kpis.soja_preco_saca)
                        customCusto = String.format(PT_BR, "%.2f", kpis.custo_ha)
                        customProd = String.format(PT_BR, "%.1f", prodModelo)
                    },
                    contentPadding = PaddingValues(horizontal = 0.dp, vertical = 0.dp)
                ) {
                    Text(text = "Voltar aos valores padrão", fontSize = 12.sp)
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            val receita = scHa * preco
            val r = resultadoPorHectare(scHa, preco, if (temCusto) custo else null, kpis)
            val outroRateio = r.outroRateio
            val lucro = r.valor
            val roi = if (custo > 0) (lucro / custo) * 100 else 0.0
            val profitColor = when {
                r.sinalIncerto -> corAtencao(isDark)
                lucro >= 0 -> if (isDark) Color(0xFF3fb950) else Color(0xFF16a34a)
                else -> if (isDark) Color(0xFFf85149) else Color(0xFFdc2626)
            }

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = if (temProd) "Receita bruta" else "Receita bruta estimada",
                         fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "${reaisInteiros(receita)}/ha", fontSize = 18.sp, color = (if(isDark) Color(0xFF58a6ff) else Color(0xFF2563eb)), fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Custo operacional", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "${reaisInteiros(custo)}/ha", fontSize = 18.sp,
                         color = if (isDark) Color(0xFFf85149) else Color(0xFFdc2626), fontWeight = FontWeight.Bold)
                }
            }
            
            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "Lucro líquido projetado", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "${reaisInteiros(lucro)}/ha", fontSize = 22.sp, color = profitColor, fontWeight = FontWeight.ExtraBold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Retorno sobre o custo", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "${roi.toInt()}%", fontSize = 22.sp, color = profitColor, fontWeight = FontWeight.ExtraBold)
                }
            }
            
            if (r.sinalIncerto && outroRateio != null) {
                Text(
                    text = "O resultado pode ir de ${reaisInteiros(minOf(lucro, outroRateio))} a " +
                           "${reaisInteiros(maxOf(lucro, outroRateio))}/ha, conforme o rateio do custo da CONAB. " +
                           "Informe o seu custo para fechar a conta.",
                    fontSize = 12.sp,
                    color = corAtencao(isDark),
                    modifier = Modifier.padding(top = 12.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))
            // O ponto de equilíbrio arredonda para cima: com 54,2 sacas de
            // equilíbrio, 54 ainda dá prejuízo.
            if (preco > 0) {
                Text(text = "Ponto de equilíbrio: ${kotlin.math.ceil(custo / preco).toInt()} sc/ha para cobrir o custo",
                     fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
fun CenarioClimaticoCard(municipio: String, baselineRendimento: Double, ano: Int? = null) {
    val isDark = isSystemInDarkTheme()
    // Tudo volta ao padrão quando o município muda: sem a chave, o cartão
    // seguia com a estimativa e o cenário do município anterior.
    var precipFactor by remember(municipio, baselineRendimento) { mutableStateOf(100f) }
    var tempOffset by remember(municipio, baselineRendimento) { mutableStateOf(0f) }
    var delta by remember(municipio, baselineRendimento) { mutableStateOf(0.0) }
    var simulado by remember(municipio, baselineRendimento) { mutableStateOf(baselineRendimento) }
    var isSimulating by remember { mutableStateOf(false) }
    var resposta by remember(municipio, baselineRendimento) { mutableStateOf<SimulacaoResponse?>(null) }
    var falhou by remember(municipio, baselineRendimento) { mutableStateOf(false) }
    val coroutineScope = rememberCoroutineScope()

    val haptic = LocalHapticFeedback.current
    fun simular() {
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        coroutineScope.launch {
            isSimulating = true
            try {
                val req = SimulacaoRequest(municipio, precipFactor / 100.0, tempOffset.toDouble())
                val resp = RetrofitClient.getInstance().simularCenario(req)
                simulado = resp.estimativa_kg_ha
                delta = resp.delta_kg_ha
                resposta = resp
                falhou = false
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                e.printStackTrace()
                falhou = true
            } finally {
                isSimulating = false
            }
        }
    }

    Card(
        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                // O simulador da API parte da safra seguinte à última divulgada,
                // que pode não ser a do Resumo: o ano fica escrito.
                Text(text = "Projeção com o cenário" + (ano?.let { ", safra $it" } ?: ""),
                     fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (isSimulating) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                }
            }
            
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = "${milhar(simulado)} kg/ha", 
                    fontSize = 28.sp, 
                    fontWeight = FontWeight.Bold,
                    color = if (delta < 0) (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626)) else if (delta > 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else MaterialTheme.colorScheme.primary
                )
                if (kotlin.math.abs(delta) > 1) {
                    val sign = if (delta >= 0) "+" else ""
                    val c = if (delta >= 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626))
                    Text(text = " ($sign${milhar(delta)} kg/ha)", fontSize = 14.sp, color = c, modifier = Modifier.padding(start = 8.dp, bottom = 4.dp))
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            
            // O leitor de tela anunciava a posição do controle ("50 por cento"
            // no meio da faixa), e não o valor: a descrição diz o cenário.
            val chuva = "${precipFactor.roundToInt()}% da chuva média"
            val temperatura = if (kotlin.math.abs(tempOffset) < 0.05f) "temperatura média"
                              else String.format(PT_BR, "%+.1f °C na temperatura média", tempOffset)
            Text(text = "Chuva: $chuva", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Slider(
                modifier = Modifier.semantics { contentDescription = "Chuva da safra"; stateDescription = chuva },
                value = precipFactor,
                onValueChange = { precipFactor = it },
                onValueChangeFinished = { simular() },
                valueRange = 50f..150f,
                steps = 19
            )
            
            Text(text = "Temperatura: $temperatura", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Slider(
                modifier = Modifier.semantics { contentDescription = "Temperatura da safra"; stateDescription = temperatura },
                value = tempOffset,
                onValueChange = { tempOffset = it },
                onValueChangeFinished = { simular() },
                valueRange = -2f..3f,
                steps = 9
            )

            if (falhou) {
                Text(
                    text = "Não foi possível simular agora. Confira a internet e mova o controle de novo.",
                    fontSize = 12.sp, color = corAtencao(isDark), fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 8.dp).semantics { liveRegion = LiveRegionMode.Polite }
                )
            }
            // O simulador precisa declarar o que pode prometer. A associação
            // entre chuva e produtividade nesta base não é distinguível de
            // zero, e a variação que ele produz cabe dentro da margem de erro
            // do modelo. Sem isso o usuário lê ruído como resposta agronômica.
            resposta?.sensibilidade?.let { sens ->
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    // Os números do teste (r, p, n) estão na dissertação; aqui, a
                    // conclusão dele, dita conforme o resultado e não fixa.
                    text = (if (sens.p >= 0.05) "Nesta base, a chuva não mostrou efeito claro na produtividade."
                            else "Nesta base, a chuva tem efeito pequeno na produtividade.") +
                           (resposta?.margem_kg_ha?.let {
                               if (kotlin.math.abs(delta) <= it) " A variação acima cabe na margem de erro do modelo (± ${milhar(it)} kg/ha)."
                               else " A variação acima passa da margem de erro do modelo (± ${milhar(it)} kg/ha)."
                           } ?: ""),
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp
                )
            }
            resposta?.fora_da_faixa?.takeIf { it.isNotEmpty() }?.let {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Cenário fora da faixa observada na base; o resultado foi " +
                           "preso ao limite do que o modelo viu.",
                    fontSize = 12.sp,
                    color = if (isDark) Color(0xFFd29922) else Color(0xFF9a6700),
                    lineHeight = 16.sp
                )
            }
        }
    }
}

@Composable
fun MetodologiaCard(kpis: FinancaResponse?, validacao: ValidacaoModelo?) {
    val isDark = isSystemInDarkTheme()
    Card(
        modifier = Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 24.dp),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.semantics(mergeDescendants = true) { heading() }) {
                Icon(Icons.Filled.Verified, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(8.dp))
                Text(
                    text = "Origem dos Dados & IA", 
                    fontSize = 16.sp, 
                    fontWeight = FontWeight.Bold, 
                    color = MaterialTheme.colorScheme.onBackground
                )
            }
            Spacer(modifier = Modifier.height(16.dp))
            
            // Aviso de que o app não é do governo e cada fonte com o link oficial, como o
            // Google Play exige de apps que mostram dados de órgãos públicos (FontesOficiais.kt).
            FontesDosDados()
            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            // Preço e custo são constantes de um levantamento datado, não cotação
            // diária. Sem a praça e a data o número envelhece sem avisar — por isso
            // o rótulo vem da API, junto com a frase que diz onde o preço está na
            // série da praça: quando a CONAB publica levantamento novo, esta tela
            // acompanha sem recompilar o APK.
            Text(text = "Preço e custo: " + (kpis?.fonte_preco ?: "CONAB (levantamento indisponível offline)"), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(text = "Preço de porteira, não cotação de bolsa. Ambos editáveis na tela Resumo.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            kpis?.nota_preco?.let {
                Text(text = it, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            kpis?.aviso_preco?.let {
                Text(
                    text = it,
                    fontSize = 12.sp,
                    color = corAtencao(isDark)
                )
            }
            
            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            
            // Métricas da validação temporal deixando um ano de fora por vez. Vêm
            // da API, que as lê de pesquisa/dados/metricas_validacao.json, o mesmo
            // arquivo que o painel web exibe: acompanham a base a cada safra nova.
            // O R² da referência aparece ao lado de propósito: o modelo empata com o
            // histórico municipal somado à tendência, e omitir isso superestimaria o
            // que a ferramenta entrega.
            if (validacao != null) {
                val r2 = String.format("%.3f", validacao.r2).replace('.', ',')
                val r2Ref = String.format("%.3f", validacao.r2_referencia).replace('.', ',')
                val rrmse = String.format("%.1f", validacao.rrmse_pct).replace('.', ',')
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column {
                        Text(text = "R² do modelo", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(text = r2, fontSize = 14.sp, color = (if(isDark) Color(0xFFbc8cff) else Color(0xFF7c3aed)), fontWeight = FontWeight.Bold)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(text = "R² da tendência (referência)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(text = r2Ref, fontSize = 14.sp, color = (if(isDark) Color(0xFF8b949e) else Color(0xFF57606a)), fontWeight = FontWeight.Bold)
                    }
                }
                Spacer(modifier = Modifier.height(10.dp))
                Text(
                    text = "Erro típico de ± ${validacao.rmse_kg_ha.roundToInt()} kg/ha, ou $rrmse% da produtividade média, " +
                           "sobre ${validacao.registros} registros de ${validacao.municipios} municípios.",
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp
                )
            } else {
                Text(
                    text = "Métricas de validação indisponíveis sem conexão com o servidor.",
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp
                )
            }
            
            Spacer(modifier = Modifier.height(20.dp))
            Text(
                text = "Aviso Legal: Este é um projeto de pesquisa acadêmica em Inteligência Artificial. As estimativas projetadas pela IA e os valores financeiros não configuram recomendação de investimento ou consultoria agronômica. Consulte profissionais certificados antes de tomar decisões financeiras reais.",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontStyle = androidx.compose.ui.text.font.FontStyle.Italic,
                lineHeight = 16.sp,
                textAlign = androidx.compose.ui.text.style.TextAlign.Start
            )
        }
    }
}



// Números no formato brasileiro em qualquer aparelho: "3.230", e não "3,230"
// num celular configurado em inglês.
private val PT_BR = java.util.Locale("pt", "BR")

fun milhar(v: Double): String = String.format(PT_BR, "%,d", v.roundToInt())

fun reais(v: Double): String = String.format(PT_BR, "%,.2f", v)

/**
 * Reais sem centavos, com o sinal antes do símbolo: "−R$ 86", e não "R$ -86".
 * O espaço depois de "R$" não quebra: numa frase longa, o símbolo ficava no fim
 * de uma linha e o número no começo da outra.
 */
fun reaisInteiros(v: Double): String =
    (if (v.roundToInt() < 0) "−" else "") + "R$\u00A0" + milhar(kotlin.math.abs(v))

// Períodos da tela Mercado: chave da API e rótulo do botão.
private val PERIODOS_MERCADO = listOf("1d" to "1D", "5d" to "5D", "1mo" to "1M", "6mo" to "6M")
// "1D" lido em voz alta não diz nada; o leitor de tela lê o período por extenso.
private val PERIODOS_POR_EXTENSO = mapOf("1d" to "1 dia", "5d" to "5 dias", "1mo" to "1 mês", "6mo" to "6 meses")

/** Busca a cotação e entrega à tela; a tela em si é MercadoConteudo. */
@Composable
fun MercadoCard() {
    var periodo by remember { mutableStateOf("1d") }
    var mercado by remember { mutableStateOf<MercadoResponse?>(null) }
    var carregando by remember { mutableStateOf(true) }

    // Atualiza a cada minuto enquanto a tela está aberta. A API guarda a
    // cotação por dois minutos, então isto não pressiona a fonte.
    LaunchedEffect(periodo) {
        carregando = true
        while (true) {
            try {
                mercado = RetrofitClient.getInstance().getMercado(periodo)
            } catch (_: Exception) {
                // mantém a última leitura; a hora dela continua visível
            }
            carregando = false
            kotlinx.coroutines.delay(60_000)
        }
    }
    MercadoConteudo(mercado, carregando, periodo) { periodo = it }
}

/**
 * A tela Mercado sem rede: recebe os dados prontos. Separada de MercadoCard
 * para poder ser desenhada nas capturas de tela automáticas.
 */
@Composable
fun MercadoConteudo(mercado: MercadoResponse?, carregando: Boolean, periodo: String, aoMudarPeriodo: (String) -> Unit) {
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
            mercado?.pracas_para?.takeIf { it.isNotEmpty() }?.let { pracas ->
                CotacoesPracasPara(pracas)
                HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            }
            Text("Soja em Chicago, em R$/saca", fontWeight = FontWeight.Bold, fontSize = 16.sp,
                 color = MaterialTheme.colorScheme.onSurface)
            Text("Bolsa de Chicago (CBOT), contrato mais próximo, convertido pelo dólar de cada momento",
                 fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PERIODOS_MERCADO.forEach { (chave, rotulo) ->
                    FilterChip(selected = periodo == chave, onClick = { aoMudarPeriodo(chave) },
                               label = { Text(rotulo) },
                               modifier = Modifier.semantics { contentDescription = PERIODOS_POR_EXTENSO[chave] ?: rotulo })
                }
            }
            Spacer(Modifier.height(10.dp))
            val cot = mercado?.cotacao
            when {
                carregando && cot == null ->
                    CircularProgressIndicator(modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally))
                cot == null ->
                    Text("Cotação indisponível no momento. Tente de novo em alguns minutos.",
                         fontSize = 13.sp, color = secundaria)
                else -> {
                    val subiu = cot.variacao_periodo_pct >= 0
                    val corVar = if (subiu) (if (isDark) Color(0xFF3fb950) else Color(0xFF15803d))
                                 else (if (isDark) Color(0xFFf85149) else Color(0xFFb91c1c))
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text("R$ ${reais(cot.ultimo_brl_saca)}", fontSize = 28.sp, fontWeight = FontWeight.Bold,
                             color = MaterialTheme.colorScheme.onSurface)
                        Spacer(Modifier.width(10.dp))
                        Text((if (subiu) "▲ +" else "▼ ") + String.format(PT_BR, "%.2f", cot.variacao_periodo_pct) + "% no período",
                             fontSize = 13.sp, color = corVar, fontWeight = FontWeight.SemiBold,
                             modifier = Modifier.padding(bottom = 5.dp))
                    }
                    Text("Máxima R$ ${reais(cot.maxima_periodo)} · mínima R$ ${reais(cot.minima_periodo)}",
                         fontSize = 12.sp, color = secundaria)
                    mercado.para?.let { para -> para.estimado_brl_saca?.let { estimado ->
                        PrecoEstimadoPara(para, estimado, isDark)
                    } }
                    GraficoVelas(cot.velas, isDark, cot.periodo)
                    val quando = java.text.SimpleDateFormat("dd/MM/yyyy HH:mm", PT_BR)
                        .format(java.util.Date(cot.atualizado_em * 1000))
                    Text("Cotação de $quando, com cerca de ${cot.atraso_min} min de atraso.",
                         fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
                    if (cot.ultimo_usd_bushel != null && cot.cambio != null) {
                        Text("US$ ${reais(cot.ultimo_usd_bushel)}/bushel · dólar a R$ ${String.format(PT_BR, "%.4f", cot.cambio)}",
                             fontSize = 12.sp, color = secundaria)
                    }
                }
            }

            mercado?.para?.let { para -> para.meses?.takeIf { it.size >= 2 }?.let { meses ->
                HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
                GraficoMensalPara(meses, para.fonte, isDark)
            } }

            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            Text("Referências de preço físico", fontWeight = FontWeight.Bold, fontSize = 14.sp,
                 color = MaterialTheme.colorScheme.onSurface)
            mercado?.fisico?.let {
                Text("${it.praca} (${it.uf}), ${it.tipo}: R$ ${reais(it.valor)}/sc, cotação do dia" +
                     (if (it.uf != "PA") ", em outro estado" else ""),
                     fontSize = 13.sp, color = secundaria)
            }
            mercado?.conab_saca?.let {
                Text("Porteira, ${mercado?.conab_fonte ?: "CONAB"}: R$ ${reais(it)}/sc, padrão da simulação",
                     fontSize = 13.sp, color = secundaria)
            }
            Spacer(Modifier.height(8.dp))
            Text("Informação de mercado, não recomendação de compra ou venda.",
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
fun CotacoesPracasPara(pracas: List<PracaPara>, hoje: java.time.LocalDate = java.time.LocalDate.now()) {
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    Text("Soja no Pará, cotação do dia", fontWeight = FontWeight.Bold, fontSize = 16.sp,
         color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.semantics { heading() })
    Text("Agrolink, por praça. Na fazenda o preço pode ser menor, pelo frete.",
         fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
    Spacer(Modifier.height(6.dp))
    pracas.forEach { p ->
        val emDia = cotacaoEmDia(p, hoje)
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth().heightIn(min = 36.dp).semantics(mergeDescendants = true) {}
        ) {
            Text(p.praca, fontSize = 15.sp, modifier = Modifier.weight(1f),
                 color = if (emDia) MaterialTheme.colorScheme.onSurface else secundaria)
            Text("R$ ${reais(p.valor)}", fontSize = 16.sp, fontWeight = FontWeight.Bold,
                 color = if (emDia) MaterialTheme.colorScheme.onSurface else secundaria)
            Text(if (emDia) "  ${dataCurta(p.data)}" else "  parada desde ${dataCurta(p.data)}",
                 fontSize = 12.sp, color = secundaria)
        }
    }
}

/** Cor da estimativa do Pará nos dois gráficos da tela Mercado. */
fun corPara(isDark: Boolean) = if (isDark) Color(0xFF58A6FF) else Color(0xFF1D4ED8)

private val MESES_CURTOS = listOf("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")

/** "2026-10" -> "out/26"; com ano por extenso, "out/2026". */
fun mesCurto(mes: String, anoCompleto: Boolean = false): String {
    val (ano, m) = mes.split("-").let { it[0] to it[1].toInt() }
    return MESES_CURTOS[m - 1] + "/" + if (anoCompleto) ano else ano.takeLast(2)
}

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
        Text("Média do Pará, estimada agora", fontSize = 12.sp, color = cor, fontWeight = FontWeight.SemiBold)
        Text("R$ ${reais(estimado)}/sc", fontSize = 22.sp, fontWeight = FontWeight.Bold,
             color = MaterialTheme.colorScheme.onSurface)
        Text("Chicago agora $sinal R$ ${reais(kotlin.math.abs(para.base_brl_saca))} de base média do Pará " +
             "(${mesCurto(para.mes_base, anoCompleto = true)}). Acompanha Chicago ao longo do dia.",
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

    Text("Pará × Chicago, médias mensais (R$/saca)", fontWeight = FontWeight.Bold, fontSize = 14.sp,
         color = MaterialTheme.colorScheme.onSurface)
    val sel = tocado?.let { meses.getOrNull(it) } ?: ultimo
    Text(
        "${mesCurto(sel.mes, anoCompleto = true)} · Pará ${reais(sel.para)} · Chicago ${reais(sel.chicago)} · " +
            "base ${if (sel.base >= 0) "+" else "−"}${reais(kotlin.math.abs(sel.base))}",
        fontSize = 12.sp, color = corTexto, lineHeight = 16.sp, modifier = Modifier.padding(top = 4.dp)
    )
    Canvas(
        modifier = Modifier.fillMaxWidth().height(180.dp).padding(top = 6.dp, bottom = 6.dp)
            .semantics {
                contentDescription = "Médias mensais da soja no Pará e em Chicago, em reais por saca, de " +
                    "${mesCurto(meses.first().mes, true)} a ${mesCurto(ultimo.mes, true)}; no último mês, " +
                    "Pará R$ ${reais(ultimo.para)} e Chicago R$ ${reais(ultimo.chicago)}."
            }
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
        ItemLegenda(cChicago, "Chicago em R$", tracejada = true)
    }

    // Base de cada mês em barras, com escala simétrica em torno de zero.
    val limite = eixoRedondo(0.0, meses.maxOf { kotlin.math.abs(it.base) }, divisoes = 2).last().coerceAtLeast(1.0)
    Text("Base do Pará (Pará − Chicago)", fontSize = 12.sp, color = corTexto, fontWeight = FontWeight.SemiBold,
         modifier = Modifier.padding(top = 10.dp))
    Canvas(
        modifier = Modifier.fillMaxWidth().height(84.dp).padding(top = 4.dp)
            .semantics {
                contentDescription = "Base do Pará por mês, de ${reais(meses.minOf { it.base })} a " +
                    "${reais(meses.maxOf { it.base })} reais por saca; no último mês, ${reais(ultimo.base)}."
            }
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
    Text("Base = Pará − Chicago, médias do mês (o mês atual é parcial). Pará: $fonte.",
         fontSize = 12.sp, color = corTexto, lineHeight = 16.sp, modifier = Modifier.padding(top = 4.dp))
}

/** Amostra de cor e rótulo de uma legenda de gráfico. */
@Composable
private fun ItemLegenda(cor: Color, rotulo: String, faixa: Boolean = false, tracejada: Boolean = false) {
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
    val formato = java.text.SimpleDateFormat(if (periodo == "1d") "HH:mm" else "dd/MM", PT_BR)
    val formatoToque = java.text.SimpleDateFormat(
        when (periodo) {
            "1d", "5d" -> "dd/MM HH:mm"
            "6mo" -> "'semana de' dd/MM/yyyy"
            else -> "dd/MM/yyyy"
        }, PT_BR)
    var tocada by remember(velas) { mutableStateOf<Int?>(null) }
    val ultima = velas.last()
    val corUltima = if (ultima.c >= ultima.o) alta else baixa
    val descricao = "Gráfico de velas da soja em reais por saca, de R$ ${reais(velas.first().o)} " +
                    "a R$ ${reais(ultima.c)}; máxima R$ ${reais(velas.maxOf { it.h })}, mínima R$ ${reais(velas.minOf { it.l })}."

    // A vela tocada, por extenso: o gráfico mostra a forma, e o número exato
    // fica aqui em cima, legível.
    val sel = tocada?.let { velas.getOrNull(it) }
    Text(
        text = sel?.let {
            formatoToque.format(java.util.Date(it.t * 1000)) +
                " · abertura ${reais(it.o)} · máxima ${reais(it.h)} · mínima ${reais(it.l)} · fechamento ${reais(it.c)}" +
                (it.pa?.let { pa -> " · Pará estimado ${reais(pa)}" } ?: "")
        } ?: "Toque numa vela para ver os valores.",
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
        ItemLegenda(alta, "Fechou acima da abertura", faixa = true)
        ItemLegenda(baixa, "Fechou abaixo", faixa = true)
    }
    if (comPara) ItemLegenda(cPara, "Pará estimado (Chicago + base do mês)", tracejada = true)
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
