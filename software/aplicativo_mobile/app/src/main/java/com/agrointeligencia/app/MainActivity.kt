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
import androidx.compose.ui.platform.LocalDensity
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

@OptIn(ExperimentalMaterial3Api::class)
/**
 * Rótulo da barra de abas, numa linha só e com a fonte crescendo no máximo
 * 1,15 vez. Com a fonte do sistema em 200%, "Histórico" quebrava em "Histór" e
 * "ico"; o ícone de cada aba continua ao lado do rótulo.
 */
@Composable
fun RotuloAba(texto: String) {
    val escala = LocalDensity.current.fontScale
    Text(texto, fontSize = (12f * minOf(escala, 1.15f) / escala).sp, maxLines = 1, softWrap = false,
         overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
}

/**
 * O celular tem agora uma rede que chega à Internet? Sem rede nenhuma a chamada
 * à API falha logo; o caso lento é a rede que existe e não navega (sinal fraco
 * no campo, Wi-Fi com login), em que a chamada só cai no tempo limite. O Android
 * marca essa rede como não validada. Sem resposta do sistema, supõe que sim.
 */
fun temRede(context: Context): Boolean {
    val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? android.net.ConnectivityManager
        ?: return true
    val rede = cm.activeNetwork ?: return false
    val capacidades = cm.getNetworkCapabilities(rede) ?: return false
    return capacidades.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
        capacidades.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED)
}

@Composable
fun AgroDashboard() {
    val coroutineScope = rememberCoroutineScope()
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current
    val sharedPrefs = remember { context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE) }
    val gson = remember { Gson() }
    val avisos = remember { SnackbarHostState() }
    var municipios by remember { mutableStateOf<List<String>>(emptyList()) }
    // O estado (Estados.kt): o Pará, se nada foi escolhido, como até a 2.7.
    var uf by remember { mutableStateOf(sharedPrefs.getString(PREF_ESTADO, null) ?: "PA") }
    val estado = estadoDoApp(uf)
    // Sedes dos municípios do estado, para o GPS, o Tempo e a praça mais perto.
    var sedes by remember { mutableStateOf(if (uf == "PA") SEDES_MUNICIPAIS else emptyMap()) }
    // Quando o servidor ainda não atende o estado escolhido.
    var avisoDoEstado by remember { mutableStateOf<String?>(null) }
    // O último município escolhido. Nulo na primeira abertura: o app pergunta
    // qual é, em vez de abrir no primeiro da lista (Municipio.kt).
    var selectedMunicipio by remember { mutableStateOf(sharedPrefs.getString(chaveDoEstado(PREF_MUNICIPIO, uf), null)) }
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
    // Mercado de hoje (praças do Pará e estimativa), um só para o app inteiro:
    // a Viabilidade, o Histórico e a Estimativa no campo usam o mesmo preço que
    // a tela Mercado mostra, e a tela Mercado o atualiza a cada minuto.
    var mercadoHoje by remember { mutableStateOf<MercadoResponse?>(null) }
    // Puxar a tela para baixo: true até a previsão e a lista voltarem.
    var atualizando by remember { mutableStateOf(false) }
    var sincronizandoPrevisao by remember { mutableStateOf(false) }
    LaunchedEffect(recarga, uf) {
        // Sem rede, as praças guardadas ainda servem (cada uma tem a data, e as
        // de mais de uma semana são ignoradas); a estimativa guardada, não, porque
        // "estimado agora" deixaria de ser verdade.
        if (mercadoHoje == null) {
            mercadoHoje = sharedPrefs.getString(chaveDoEstado("mercado_1d", uf), null)
                ?.let { runCatching { gson.fromJson(it, MercadoResponse::class.java) }.getOrNull() }
                ?.copy(para = null)
        }
        try {
            val m = RetrofitClient.getInstance().getMercado("1d", ufParaApi(uf))
            if (!respostaDoEstado(uf, m.uf)) return@LaunchedEffect
            mercadoHoje = m
            sharedPrefs.edit().putString(chaveDoEstado("mercado_1d", uf), gson.toJson(m)).apply()
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (_: Exception) {
        }
    }

    // Previsão do tempo (Tempo.kt): vem do Open-Meteo, e não da API, e por
    // isso carrega mesmo com a API dormindo. Serve o cartão do Resumo e a tela.
    val tempo = remember { EstadoTempo(sharedPrefs) }
    LaunchedEffect(sedes) { tempo.sedes = sedes }
    val lugarTempo = tempo.lugarPara(selectedMunicipio)
    LaunchedEffect(lugarTempo) { lugarTempo?.let { tempo.carrega(it) } }

    // Janela de plantio (Plantio.kt): calendário da portaria e ZARC do município.
    val plantio = remember { EstadoPlantio(sharedPrefs) }
    LaunchedEffect(selectedMunicipio, uf) { selectedMunicipio?.let { plantio.carrega(it, uf) } }

    // Mensagens curtas na barra de baixo; o TalkBack as lê em voz alta.
    fun avisar(msg: String) {
        coroutineScope.launch {
            avisos.currentSnackbarData?.dismiss()
            avisos.showSnackbar(msg)
        }
    }

    fun escolherMunicipio(mun: String) {
        selectedMunicipio = mun
        sharedPrefs.edit().putString(chaveDoEstado(PREF_MUNICIPIO, uf), mun).apply()
    }

    // Trocar de estado: a lista, as sedes e o mercado passam a ser os dele, e
    // o município volta a ser o último escolhido naquele estado.
    fun escolherEstado(novo: String) {
        if (novo == uf) return
        uf = novo
        sharedPrefs.edit().putString(PREF_ESTADO, novo).apply()
        municipios = emptyList()
        sedes = if (novo == "PA") SEDES_MUNICIPAIS else emptyMap()
        avisoDoEstado = null
        selectedMunicipio = sharedPrefs.getString(chaveDoEstado(PREF_MUNICIPIO, novo), null)
        previsao = null
        kpis = null
        mercadoHoje = null
    }

    // GPS para o município: a sede mais próxima entre os da lista, calculada
    // no celular. A posição não é guardada nem enviada.
    val leitorMunicipio = rememberLeitorDePosicao(
        semPermissao = "Sem a permissão de localização, escolha o município na lista.",
        aoFalhar = { avisar(it) }
    ) { lat, lon ->
        val candidatos = municipios.ifEmpty { sedes.keys.toList() }
        val proximo = municipioMaisProximo(lat, lon, candidatos, sedes)
        if (proximo == null) {
            avisar("Não foi possível achar um município da lista perto de você. Escolha na lista.")
        } else {
            escolherMunicipio(proximo.nome)
            mostrarLista = false
            avisar(fraseDoMaisProximo(proximo, candidatos.size, estado))
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
        val ufPedida = uf
        val cachedMunStr = sharedPrefs.getString(chaveDoEstado("municipios", ufPedida), null)
        val cachedKpiStr = sharedPrefs.getString(chaveDoEstado("kpis", ufPedida), null)
        // Lido com runCatching: um cache gravado por outra versão, ou cortado,
        // derrubava o app na abertura; agora só é ignorado.
        val munGuardados = cachedMunStr?.let { runCatching { gson.fromJson(it, MunicipioResponse::class.java) }.getOrNull() }
        val kpisGuardados = cachedKpiStr?.let { runCatching { gson.fromJson(it, FinancaResponse::class.java) }.getOrNull() }
        if (!munGuardados?.municipios.isNullOrEmpty() && kpisGuardados != null) {
            municipios = munGuardados!!.municipios
            sedes = sedesDoEstado(ufPedida, munGuardados.sedes)
            selectedMunicipio = municipioGuardadoValido(municipios, selectedMunicipio)
            kpis = kpisGuardados
        } else {
            carregandoLista = true
        }

        // Depois a versão do servidor, sem bloquear a tela.
        coroutineScope.launch {
            try {
                val api = RetrofitClient.getInstance()
                val response = api.getMunicipios(ufParaApi(ufPedida), if (ufPedida == "PA") null else true)
                // Trocou de estado enquanto a lista vinha: a resposta é do outro.
                if (ufPedida != uf) return@launch
                if (!respostaDoEstado(ufPedida, response.uf) || response.municipios.isEmpty()) {
                    // Um servidor de antes da v2.5.0 não tem os outros estados.
                    avisoDoEstado = "${estadoDoApp(ufPedida).nome} ainda não está disponível no servidor. " +
                        "Escolha o Pará ou tente de novo mais tarde."
                    if (municipios.isEmpty()) errorMsg = avisoDoEstado
                    return@launch
                }
                avisoDoEstado = null
                // Preço e custo são os da CONAB para o estado. No Pará, de um
                // município para outro só muda o VTN, que o aplicativo não
                // mostra; em Mato Grosso, a praça muda com o município, e a
                // previsão de cada um busca a sua.
                val kpisResponse = api.getFinancas(
                    if (ufPedida == "PA") "Paragominas" else (selectedMunicipio ?: response.municipios.first()),
                    ufParaApi(ufPedida))
                municipios = response.municipios
                sedes = sedesDoEstado(ufPedida, response.sedes)
                selectedMunicipio = municipioGuardadoValido(municipios, selectedMunicipio)
                kpis = kpisResponse
                sharedPrefs.edit()
                    .putString(chaveDoEstado("municipios", ufPedida), gson.toJson(response))
                    .putString(chaveDoEstado("kpis", ufPedida), gson.toJson(kpisResponse))
                    .apply()
                errorMsg = null
            } catch (e: Exception) {
                e.printStackTrace()
                if (municipios.isEmpty()) {
                    errorMsg = "Erro na API: ${e.message}"
                }
            } finally {
                carregandoLista = false
            }
        }
    }

    // Na abertura e a cada troca de estado.
    LaunchedEffect(uf) {
        loadData()
    }

    // O voltar do celular leva ao Resumo, e só do Resumo sai do app: antes, no
    // Mercado ou no Histórico, o voltar fechava o app de uma vez.
    BackHandler(enabled = currentTab != 0) { currentTab = 0 }

    // A previsão do município corre dentro do efeito, e não num escopo de fora:
    // trocar de município cancela a busca anterior. Antes as duas corriam
    // juntas, e a resposta do município velho, se chegasse por último, ficava
    // na tela com o nome do novo.
    LaunchedEffect(selectedMunicipio, recarga, uf) {
        val mun = selectedMunicipio
        val ufPedida = uf
        if (mun == null) {
            previsao = null
            sincronizandoPrevisao = false
            return@LaunchedEffect
        }
        sincronizandoPrevisao = true
        val guardada = sharedPrefs.getString(chaveDoEstado("previsao_$mun", ufPedida), null)
            ?.let { runCatching { gson.fromJson(it, PrevisaoResponse::class.java) }.getOrNull() }
            ?.valida()
        previsao = guardada
        previsaoEm = if (guardada != null) sharedPrefs.getLong(chaveDoEstado("previsao_${mun}_em", ufPedida), 0L) else 0L
        // O "carregando" só aparece quando não há nada guardado do município.
        carregandoPrevisao = guardada == null
        // Sem rede que navegue, o aviso aparece na hora: antes esperava a
        // chamada à API falhar, o que com sinal fraco levava o minuto do tempo
        // limite (que existe para o servidor do Render acordar). A chamada
        // segue, e o aviso some se ela der certo.
        if (!temRede(context)) isOfflineMode = true
        try {
            val resposta = RetrofitClient.getInstance().getPrevisao(mun, ufParaApi(ufPedida)).valida()
                ?.takeIf { respostaDoEstado(ufPedida, it.uf) }
                ?: throw IllegalStateException("resposta sem histórico")
            previsao = resposta
            previsaoEm = System.currentTimeMillis()
            sharedPrefs.edit()
                .putString(chaveDoEstado("previsao_$mun", ufPedida), gson.toJson(resposta))
                .putLong(chaveDoEstado("previsao_${mun}_em", ufPedida), previsaoEm)
                .apply()
            // Fora do Pará a praça da CONAB muda com o município (Sorriso ou Primavera do Leste).
            if (ufPedida != "PA") {
                runCatching { RetrofitClient.getInstance().getFinancas(mun, ufParaApi(ufPedida)) }
                    .getOrNull()?.takeIf { respostaDoEstado(ufPedida, it.uf) }?.let { k ->
                        kpis = k
                        sharedPrefs.edit().putString(chaveDoEstado("kpis", ufPedida), gson.toJson(k)).apply()
                    }
            }
            isOfflineMode = false
            carregandoPrevisao = false
            sincronizandoPrevisao = false
        } catch (e: kotlinx.coroutines.CancellationException) {
            // Trocou de município: o efeito novo cuida do indicador.
            throw e
        } catch (e: Exception) {
            e.printStackTrace()
            isOfflineMode = true
            carregandoPrevisao = false
            sincronizandoPrevisao = false
        }
    }

    // Atualiza tudo o que a tela mostra: lista, previsão, mercado e tempo. O
    // indicador some quando a lista e a previsão voltam (ou em 60 s).
    fun atualizarTudo() {
        if (atualizando) return
        atualizando = true
        loadData()
        recarga++
        lugarTempo?.let { l -> coroutineScope.launch { tempo.carrega(l, forcar = true) } }
        selectedMunicipio?.let { m -> coroutineScope.launch { plantio.carrega(m, uf, forcar = true) } }
        coroutineScope.launch {
            kotlinx.coroutines.delay(300)
            kotlinx.coroutines.withTimeoutOrNull(60_000) {
                snapshotFlow { carregandoLista || sincronizandoPrevisao }.first { !it }
            }
            atualizando = false
        }
    }

    // Um preço padrão para o app inteiro: a cotação do dia na praça do Pará mais
    // perto do município (Agrolink) e, sem ela, o levantamento da CONAB. Antes a
    // Viabilidade, o Histórico e a Estimativa no campo podiam usar preços
    // diferentes para a mesma lavoura.
    val pracaHoje = pracaParaUsar(selectedMunicipio, mercadoHoje?.pracasDoEstado().orEmpty(), sedes = sedes)
    val precoPadraoAtual: Double? = pracaHoje?.valor ?: kpis?.soja_preco_saca

    // Cada aba abre do começo: antes, quem rolava o Histórico e ia ao Mercado
    // caía no meio da tela.
    val lista = rememberLazyListState()
    LaunchedEffect(currentTab) { lista.scrollToItem(0) }

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
            aoFechar = { mostrarLista = false },
            estado = estado,
            aoEscolherEstado = { escolherEstado(it) },
            avisoDoEstado = avisoDoEstado
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
                    label = { RotuloAba("Resumo") }
                )
                NavigationBarItem(
                    selected = currentTab == 1,
                    onClick = { irPara(1) },
                    icon = { Icon(Icons.Filled.LocationOn, contentDescription = null) },
                    label = { RotuloAba("Mapa") }
                )
                @Suppress("DEPRECATION")
                NavigationBarItem(
                    selected = currentTab == 2,
                    onClick = { irPara(2) },
                    icon = { Icon(Icons.Filled.List, contentDescription = null) },
                    label = { RotuloAba("Histórico") }
                )
                NavigationBarItem(
                    selected = currentTab == 4,
                    onClick = { irPara(4) },
                    icon = { Icon(Icons.Filled.CandlestickChart, contentDescription = null) },
                    label = { RotuloAba("Mercado") }
                )
                NavigationBarItem(
                    selected = currentTab == 3,
                    onClick = { irPara(3) },
                    icon = { Icon(Icons.Filled.Info, contentDescription = null) },
                    label = { RotuloAba("Sobre") }
                )
            }
        }
    ) { paddingValues ->
        val isDark = isSystemInDarkTheme()
        PullToRefreshBox(
            isRefreshing = atualizando,
            onRefresh = { atualizarTudo() },
            modifier = Modifier.fillMaxSize().padding(paddingValues)
        ) {
        LazyColumn(
            state = lista,
            modifier = Modifier.fillMaxSize(),
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
                            IconButton(onClick = { atualizarTudo() }, enabled = !isLoading && !atualizando) {
                                Icon(Icons.Filled.Refresh, contentDescription = "Atualizar os dados")
                            }
                        }
                    }

                    // O aviso fala dos dados do município: só nas abas que os mostram.
                    if (isOfflineMode && currentTab in 0..2) {
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
                                aoUsarPosicao = { leitorMunicipio.ler() },
                                estado = estado
                            )
                        }
                    }

                    // Fora do bloco da previsão de produtividade: o tempo aparece
                    // mesmo enquanto a API acorda ou quando ela falha.
                    if (currentTab == 0 && lugarTempo != null) {
                        TempoResumoCard(tempo) { currentTab = 6 }
                    }
                    // A janela de plantio vem de arquivos da API, e não do modelo:
                    // aparece mesmo quando a previsão de produtividade falha.
                    if (currentTab == 0 && selectedMunicipio != null) {
                        PlantioResumoCard(plantio) { currentTab = 7 }
                    }
                }
            }

            val prev = previsao
            when {
                currentTab == 4 -> item {
                    // A cotação não depende da previsão do município: a aba abre
                    // mesmo quando a previsão ainda não carregou ou falhou.
                    MercadoCard(recarga, uf) { mercadoHoje = it }
                }
                currentTab == 5 -> item {
                    // Como o Mercado, não depende da previsão: a contagem no campo
                    // funciona sem rede. A previsão, se houver, entra para comparação.
                    val projecao = prev?.historico?.let { projecaoDaSafra(it) }
                    val precoDoProdutor = sharedPrefs.valorDoProdutor(PREF_PRECO)
                    EstimativaCampoTela(
                        precoPadrao = precoDoProdutor ?: precoPadraoAtual,
                        fontePreco = when {
                            precoDoProdutor != null -> "Seu preço, informado na Viabilidade."
                            pracaHoje != null -> "Cotação de ${pracaHoje.praca} em ${dataCurta(pracaHoje.data)} (Agrolink)."
                            else -> kpis?.fonte_preco?.let { "Preço de referência: $it." }
                        },
                        referenciaKgHa = projecao?.rendimento_predito,
                        rotuloReferencia = projecao?.let { "${prev?.municipio ?: selectedMunicipio} em ${it.ano}" },
                        aoVoltar = { currentTab = 0 }
                    )
                }
                currentTab == 6 -> item {
                    TempoTela(tempo, selectedMunicipio) { currentTab = 0 }
                }
                currentTab == 7 -> item {
                    PlantioTela(
                        plantio, selectedMunicipio,
                        aoAtualizar = { selectedMunicipio?.let { m -> coroutineScope.launch { plantio.carrega(m, uf, forcar = true) } } },
                        aoVoltar = { currentTab = 0 }
                    )
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
                                    contentDescription = "Mapa da produtividade da soja nos municípios ${estado.de}" +
                                        (selectedMunicipio?.let { ", com $it em destaque" } ?: "")
                                },
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            val currentTheme = if (isDark) "dark" else "light"
                            val mapUrl = "https://agrointeligencia-api.onrender.com/api/mapa/render?theme=${currentTheme}" +
                                (selectedMunicipio?.let { "&municipio=${URLEncoder.encode(it, "UTF-8")}" } ?: "") +
                                (ufParaApi(uf)?.let { "&uf=$it" } ?: "")
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
                                        // A página é da API; nada de arquivos do celular.
                                        settings.allowFileAccess = false
                                        settings.allowContentAccess = false
                                        setLayerType(android.view.View.LAYER_TYPE_SOFTWARE, null)
                                        // Um link de fora (o crédito do OpenStreetMap, por
                                        // exemplo) abre no navegador: dentro do quadro do
                                        // mapa, o produtor ficava preso numa página sem volta.
                                        webViewClient = object : WebViewClient() {
                                            override fun shouldOverrideUrlLoading(
                                                view: WebView, request: android.webkit.WebResourceRequest
                                            ): Boolean {
                                                if (request.url.host == "agrointeligencia-api.onrender.com") return false
                                                runCatching {
                                                    view.context.startActivity(
                                                        android.content.Intent(android.content.Intent.ACTION_VIEW, request.url)
                                                    )
                                                }
                                                return true
                                            }
                                        }
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
                errorMsg != null && avisoDoEstado != null -> item {
                    AvisoSemDados(titulo = "${estado.nome} ainda não está no servidor", texto = avisoDoEstado!!,
                                  rotulo = "Voltar ao Pará") {
                        escolherEstado("PA")
                    }
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

                    if (currentTab == 0) { // Resumo
                        item {
                            AtalhoEstimativaCampo { currentTab = 5 }
                        }
                        if (projecao != null) {
                            item {
                                TituloSecao(Icons.Filled.BarChart, "Resumo Agronômico (safra ${projecao.ano})")
                                ResumoAgronomicoCard(projecao, ultimoReal)
                            }
                            // A Viabilidade antes do Simulador: é a conta que o produtor
                            // faz; o simulador climático é ilustração do modelo.
                            kpis?.let { k ->
                                item {
                                    TituloSecao(Icons.Filled.MonetizationOn, "Viabilidade Financeira",
                                                Modifier.padding(top = 8.dp))
                                    ResumoFinanceiroCard(projecao, k, mercadoHoje?.para,
                                                         mercadoHoje?.pracasDoEstado().orEmpty(), selectedMunicipio, sedes)
                                }
                            }
                            item {
                                TituloSecao(Icons.Filled.SettingsSuggest, "Simulador de cenário climático",
                                            Modifier.padding(top = 8.dp))
                                // A safra em curso, a mesma do Resumo: antes o simulador
                                // partia da seguinte à última divulgada (2026 com o Resumo
                                // em 2027) e mostrava outro número para "a safra".
                                CenarioClimaticoCard(municipio = selectedMunicipio ?: prev.municipio,
                                                     baselineRendimento = projecao.rendimento_predito,
                                                     ano = projecao.ano, uf = ufParaApi(uf))
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
                            PrevisaoCard(hist, kpis, precoPadraoAtual)
                        }
                    }
                }
            }
        }
        } // PullToRefreshBox
    }
}
