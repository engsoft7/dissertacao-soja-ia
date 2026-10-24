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
import kotlinx.coroutines.launch
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics

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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgroDashboard() {
    val coroutineScope = rememberCoroutineScope()
    var municipios by remember { mutableStateOf<List<String>>(emptyList()) }
    var selectedMunicipio by remember { mutableStateOf<String?>(null) }
    var previsao by remember { mutableStateOf<PrevisaoResponse?>(null) }
    var kpis by remember { mutableStateOf<FinancaResponse?>(null) }
    var isLoading by remember { mutableStateOf(false) }
    var expanded by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }
    // Salvável: a câmera da Estimativa no campo pode levar o Android a
    // encerrar o app, e na volta ele precisa reabrir na mesma tela.
    var currentTab by rememberSaveable { mutableStateOf(0) }
    var isOfflineMode by remember { mutableStateOf(false) }
    
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current
    val sharedPrefs = remember { context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE) }
    val gson = remember { Gson() }
    
    fun loadData() {
        errorMsg = null
        
        // --- 0. Proactive Render warm-up (fire-and-forget) ---
        coroutineScope.launch {
            try { RetrofitClient.getInstance().ping() } catch (_: Exception) {}
        }
        
        // --- 1. Optimistic Cache Load ---
        val cachedMunStr = sharedPrefs.getString("municipios", null)
        val cachedKpiStr = sharedPrefs.getString("kpis", null)
        
        if (cachedMunStr != null && cachedKpiStr != null) {
            val mResponse = gson.fromJson(cachedMunStr, MunicipioResponse::class.java)
            municipios = mResponse.municipios
            if (municipios.isNotEmpty() && selectedMunicipio == null) {
                selectedMunicipio = municipios[0]
            }
            kpis = gson.fromJson(cachedKpiStr, FinancaResponse::class.java)
            // Do not assume offline yet to avoid flickering
        } else {
            isLoading = true // Only show spinner if absolutely no data is available
        }
        
        // --- 2. Background Sync ---
        coroutineScope.launch {
            try {
                val response = RetrofitClient.getInstance().getMunicipios()
                val kpisResponse = RetrofitClient.getInstance().getFinancas("Paragominas")
                
                // Update State Silently
                municipios = response.municipios
                if (selectedMunicipio == null && municipios.isNotEmpty()) {
                    selectedMunicipio = municipios[0]
                }
                kpis = kpisResponse
                
                // Save Cache
                sharedPrefs.edit().apply {
                    putString("municipios", gson.toJson(response))
                    putString("kpis", gson.toJson(kpis))
                    apply()
                }
                
                isOfflineMode = false
                errorMsg = null
            } catch (e: Exception) {
                e.printStackTrace()
                if (cachedMunStr == null) {
                    errorMsg = "Erro na API: ${e.message}"
                }
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadData()
    }

    // A Estimativa no campo não tem item na barra de baixo; o voltar do
    // celular leva de volta ao Resumo, de onde ela é aberta.
    BackHandler(enabled = currentTab == 5) { currentTab = 0 }
    
    LaunchedEffect(selectedMunicipio) {
        selectedMunicipio?.let { mun ->
            // --- 1. Optimistic Cache Load ---
            val cachedPrevStr = sharedPrefs.getString("previsao_$mun", null)
            if (cachedPrevStr != null) {
                previsao = gson.fromJson(cachedPrevStr, PrevisaoResponse::class.java)
                // Se já carregou do cache, não bloqueamos o app com spinner principal
            } else {
                isLoading = true // Apenas mostra o spinner se for o primeiro acesso da cidade
            }
            
            // --- 2. Background Sync ---
            coroutineScope.launch {
                try {
                    val prevResponse = RetrofitClient.getInstance().getPrevisao(mun)
                    previsao = prevResponse // Atualiza estado silenciosamente
                    sharedPrefs.edit().putString("previsao_$mun", gson.toJson(prevResponse)).apply()
                    isOfflineMode = false
                } catch (e: Exception) {
                    isOfflineMode = true
                    e.printStackTrace()
                    if (cachedPrevStr == null) {
                        previsao = null
                        // Optional: show a toast or error state specifically for prevision
                    }
                } finally {
                    isLoading = false
                }
            }
        }
    }

    Scaffold(
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                NavigationBarItem(
                    selected = currentTab == 0,
                    onClick = { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); currentTab = 0 },
                    icon = { Icon(Icons.Filled.Home, contentDescription = "Resumo") },
                    label = { Text("Resumo") }
                )
                NavigationBarItem(
                    selected = currentTab == 1,
                    onClick = { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); currentTab = 1 },
                    icon = { Icon(Icons.Filled.LocationOn, contentDescription = "Mapa") },
                    label = { Text("Mapa") }
                )
                @Suppress("DEPRECATION")
                NavigationBarItem(
                    selected = currentTab == 2,
                    onClick = { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); currentTab = 2 },
                    icon = { Icon(Icons.Filled.List, contentDescription = "Histórico") },
                    label = { Text("Histórico") }
                )
                NavigationBarItem(
                    selected = currentTab == 4,
                    onClick = { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); currentTab = 4 },
                    icon = { Icon(Icons.Filled.CandlestickChart, contentDescription = "Mercado") },
                    label = { Text("Mercado") }
                )
                NavigationBarItem(
                    selected = currentTab == 3,
                    onClick = { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); currentTab = 3 },
                    icon = { Icon(Icons.Filled.Info, contentDescription = "Sobre") },
                    label = { Text("Sobre") }
                )
            }
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            userScrollEnabled = currentTab != 1
        ) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 8.dp)) {
                    Icon(Icons.Filled.Agriculture, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "AgroInteligência",
                        fontSize = 24.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                
                if (isOfflineMode) {
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 8.dp)) {
                        Icon(Icons.Filled.WifiOff, contentDescription = null, tint = Color(0xFFFF9800), modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text(text = "Exibindo dados da última vez em que esteve online", fontSize = 12.sp, color = Color(0xFFFF9800), fontWeight = FontWeight.Bold)
                    }
                }
                
                // O município só muda Resumo, Mapa e Histórico; em Mercado e
                // Sobre o seletor ocupava a tela sem efeito.
                if (currentTab in 0..2) {
                    Text(text = "Município selecionado:", color = MaterialTheme.colorScheme.onBackground)
                    
                    ExposedDropdownMenuBox(
                        expanded = expanded,
                        onExpandedChange = { expanded = !expanded },
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 8.dp)
                    ) {
                        OutlinedTextField(
                            value = selectedMunicipio ?: "Carregando...",
                            onValueChange = {},
                            readOnly = true,
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                            colors = ExposedDropdownMenuDefaults.outlinedTextFieldColors(),
                            modifier = Modifier.menuAnchor(type = ExposedDropdownMenuAnchorType.PrimaryNotEditable).fillMaxWidth()
                        )
                        
                        ExposedDropdownMenu(
                            expanded = expanded,
                            onDismissRequest = { expanded = false }
                        ) {
                            municipios.forEach { mun ->
                                DropdownMenuItem(
                                    text = { Text(mun) },
                                    onClick = {
                                        selectedMunicipio = mun
                                        expanded = false
                                    }
                                )
                            }
                        }
                    }
                }
            }

            if (currentTab == 4) {
                // A cotação não depende da previsão do município: a aba abre
                // mesmo quando a previsão ainda não carregou ou falhou.
                item {
                    MercadoCard()
                }
            } else if (currentTab == 5) {
                // Como o Mercado, não depende da previsão: a contagem no campo
                // funciona sem rede. A previsão, se houver, entra para comparação.
                item {
                    val projecao = previsao?.historico?.maxByOrNull { it.ano }
                    EstimativaCampoTela(
                        precoPadrao = sharedPrefs.valorDoProdutor(PREF_PRECO) ?: kpis?.soja_preco_saca,
                        fontePreco = if (sharedPrefs.valorDoProdutor(PREF_PRECO) != null) "Seu preço, informado na Viabilidade."
                                     else kpis?.fonte_preco?.let { "Preço de referência: $it." },
                        referenciaKgHa = projecao?.rendimento_predito,
                        rotuloReferencia = projecao?.let { "${previsao?.municipio ?: selectedMunicipio} em ${it.ano}" },
                        aoVoltar = { currentTab = 0 }
                    )
                }
            } else if (isLoading) {
                item {
                    CircularProgressIndicator(modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally))
                }
            } else if (errorMsg != null) {
                item {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        modifier = Modifier.fillMaxWidth().padding(top = 24.dp, bottom = 24.dp)
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier.fillMaxWidth().padding(24.dp)
                        ) {
                            Icon(Icons.Filled.WifiOff, contentDescription = null, tint = Color(0xFFf85149), modifier = Modifier.size(56.dp))
                            Spacer(Modifier.height(16.dp))
                            Text(
                                text = "Conexão Indisponível",
                                color = MaterialTheme.colorScheme.onSurface,
                                fontWeight = FontWeight.Bold,
                                fontSize = 20.sp
                            )
                            Text(
                                text = "Não foi possível sincronizar os dados meteorológicos e do mercado futuro. Verifique sua conexão.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 13.sp,
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                                modifier = Modifier.padding(top = 8.dp, bottom = 24.dp)
                            )
                            Button(
                                onClick = { loadData() },
                                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                            ) {
                                Text("Tentar Novamente", fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            } else {
                previsao?.let { prev ->
                    val historicoOrdenado = prev.historico.sortedByDescending { it.ano }
                    val projecao = historicoOrdenado.firstOrNull()
                    val ultimoReal = historicoOrdenado.drop(1).firstOrNull { it.rendimento_real > 0 } ?: historicoOrdenado.drop(1).firstOrNull()

                    when (currentTab) {
                        0 -> { // Resumo
                            item {
                                AtalhoEstimativaCampo { currentTab = 5 }
                            }
                            item {
                                if (projecao != null) {
                                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 4.dp)) {
                                        Icon(Icons.Filled.BarChart, contentDescription = null, tint = MaterialTheme.colorScheme.onBackground)
                                        Spacer(Modifier.width(8.dp))
                                        Text(
                                            text = "Resumo Agronômico (${projecao.ano})",
                                            fontSize = 18.sp,
                                            fontWeight = FontWeight.SemiBold,
                                            color = MaterialTheme.colorScheme.onBackground
                                        )
                                    }
                                    ResumoAgronomicoCard(projecao, ultimoReal)
                                }
                            }
                            item {
                                if (projecao != null) {
                                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 16.dp, bottom = 4.dp)) {
                                        Icon(Icons.Filled.SettingsSuggest, contentDescription = null, tint = MaterialTheme.colorScheme.onBackground)
                                        Spacer(Modifier.width(8.dp))
                                        Text(
                                            text = "Simulador de cenário climático",
                                            fontSize = 18.sp,
                                            fontWeight = FontWeight.SemiBold,
                                            color = MaterialTheme.colorScheme.onBackground
                                        )
                                    }
                                    CenarioClimaticoCard(municipio = selectedMunicipio ?: "", baselineRendimento = projecao.rendimento_predito)
                                }
                            }
                            item {
                                if (projecao != null && kpis != null) {
                                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 16.dp, bottom = 4.dp)) {
                                        Icon(Icons.Filled.MonetizationOn, contentDescription = null, tint = MaterialTheme.colorScheme.onBackground)
                                        Spacer(Modifier.width(8.dp))
                                        Text(
                                            text = "Viabilidade Financeira",
                                            fontSize = 18.sp,
                                            fontWeight = FontWeight.SemiBold,
                                            color = MaterialTheme.colorScheme.onBackground
                                        )
                                    }
                                    ResumoFinanceiroCard(projecao, kpis!!)
                                }
                            }
                        }
                        2 -> { // Histórico
                            item {
                                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp, bottom = 8.dp)) {
                                    Icon(Icons.Filled.DateRange, contentDescription = null, tint = MaterialTheme.colorScheme.onBackground)
                                    Spacer(Modifier.width(8.dp))
                                    Text(
                                        text = "Histórico Completo",
                                        fontSize = 18.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = MaterialTheme.colorScheme.onBackground
                                    )
                                }
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
                                    HistoricoProdutividadeChart(historico = historicoOrdenado, previsao = previsao)
                                }
                                items(historicoOrdenado) { hist ->
                                    PrevisaoCard(hist, kpis)
                                }
                        }
                        3 -> { // Sobre
                            item {
                                MetodologiaCard(kpis, previsao?.validacao)
                            }
                        }
                        1 -> { // Mapa WebView
                            item {
                                if (isOfflineMode) {
                                    Column(
                                        modifier = Modifier.fillMaxWidth().height(400.dp),
                                        verticalArrangement = Arrangement.Center,
                                        horizontalAlignment = Alignment.CenterHorizontally
                                    ) {
                                        Icon(Icons.Filled.WifiOff, contentDescription = null, tint = Color.Gray, modifier = Modifier.size(64.dp))
                                        Spacer(modifier = Modifier.height(16.dp))
                                        // Nunca houve imagem de satélite aqui: o mapa é vetorial,
                                        // com o contorno do Pará da malha do IBGE, rios do Natural
                                        // Earth e círculos coloridos pela produtividade observada.
                                        Text("Mapa indisponível offline", fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 16.sp)
                                        Spacer(modifier = Modifier.height(8.dp))
                                        Text("O mapa é desenhado pela API. Conecte-se para carregá-lo.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)
                                    }
                                } else {
                                    Card(
                                        modifier = Modifier.fillParentMaxHeight(0.82f).fillMaxWidth().padding(1.dp),
                                        shape = RoundedCornerShape(12.dp)
                                    ) {
                                        val currentTheme = if (isSystemInDarkTheme()) "dark" else "light"
                                        val mapUrl = "https://agrointeligencia-api.onrender.com/api/mapa/render?theme=${currentTheme}" + if (selectedMunicipio != null) "&municipio=${URLEncoder.encode(selectedMunicipio, "UTF-8")}" else ""
                                        // Remember last loaded URL to avoid redundant reloads on recomposition
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
                           else "não divulgada",
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
                    r.sinalIncerto -> if (isDark) Color(0xFFd29922) else Color(0xFFbf8700)
                    r.valor > 0 -> if (isDark) Color(0xFF3fb950) else Color(0xFF16a34a)
                    else -> if (isDark) Color(0xFFf85149) else Color(0xFFdc2626)
                }
                Text(
                    text = (if (observado) "Resultado a preços de hoje: "
                            else "Resultado projetado: ") + String.format(PT_BR, "R$ %,d/ha", r.valor.toInt()),
                    fontSize = 13.sp,
                    color = color,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 8.dp)
                )
                if (r.sinalIncerto && outro != null) {
                    Text(
                        text = String.format(PT_BR, "Pode ir de R$ %,d a R$ %,d conforme o rateio do custo, que a CONAB não publica aberto por item.", 
                            minOf(r.valor, outro).toInt(), maxOf(r.valor, outro).toInt()),
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
            Text(text = "Rendimento Esperado", fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = "${milhar(projYield)} kg/ha", 
                    fontSize = 28.sp, 
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(text = " (~ ${(projYield / 60).toInt()} sc/ha)", fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = 8.dp, bottom = 4.dp))
            }
            
            if (ultimoReal != null) {
                val pastYield = if (ultimoReal.rendimento_real > 0) ultimoReal.rendimento_real else ultimoReal.rendimento_predito
                val typeStr = if (ultimoReal.rendimento_real > 0) "Real" else "Est."
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
                        Text(text = "Safra ${ultimoReal.ano} ($typeStr)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(text = "${milhar(pastYield)} kg/ha", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(text = "Variação anual", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(text = "$sign${diffPct.toInt()}%", fontSize = 16.sp, color = color, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

@Composable
fun ResumoFinanceiroCard(projecao: PrevisaoHistorico, kpis: FinancaResponse) {
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
        mutableStateOf("%.2f".format(precoSalvo ?: kpis.soja_preco_saca))
    }
    var customCusto by remember {
        mutableStateOf("%.2f".format(custoSalvo ?: kpis.custo_ha))
    }
    var customProd by remember {
        mutableStateOf("%.1f".format(prodSalva ?: prodModelo))
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
                else -> kpis.aviso_preco?.let { "Preço possivelmente desatualizado. $it" }
            }
            alerta?.let {
                Text(
                    text = it,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                    color = if (isDark) Color(0xFFd29922) else Color(0xFFbf8700),
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
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9),
                        unfocusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9)
                    )
                )
                // Mantém a largura das colunas igual à da linha de cima.
                Spacer(modifier = Modifier.weight(1f))
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
            val quando = java.text.SimpleDateFormat("dd/MM/yyyy", java.util.Locale.getDefault())
            val legenda = listOfNotNull(
                if (seus.isEmpty())
                    "Preencha com os seus números: o app guarda e passa a abrir com eles."
                else
                    "Seus números: " + seus.joinToString(", ") + ".",
                if (temProd) null
                    else "A produtividade é a estimativa do modelo — se você já colheu, informe a sua.",
                if (temPreco) null else kpis.fonte_preco?.let { "Preço padrão: $it." },
                if (temPreco) null else kpis.nota_preco,
                if (temCusto) null else kpis.fonte_preco?.let { "Custo padrão: $it." },
                // Referência que se move todo dia, contra um padrão que se move
                // a cada dois meses. A praça vem do servidor: o corredor do
                // Pará quando a fonte publica, um porto do Sul só quando não
                // publica. Escrever "Paranaguá" fixo aqui era afirmar uma praça
                // que pode não ser a exibida. Concatenar antes de .format()
                // deixaria dúvida sobre a qual literal o format se aplica.
                kpis.preco_fisico?.let {
                    "Físico hoje em %s (%s), %s: R$ %.2f/sc — não é preço de porteira, entre a praça e a fazenda ainda há frete e base."
                        .format(it.praca, it.uf, it.tipo, it.valor)
                }
            ).joinToString(" ")
            if (legenda.isNotBlank()) {
                Text(text = legenda, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (seus.isNotEmpty()) {
                Text(
                    text = "Informados em " + quando.format(java.util.Date(
                        maxOf(precoEm, custoEm, prodEm))) + ".",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                // Caminho de volta, para ninguém ficar preso a um número
                // digitado errado sem saber de onde vinha o padrão.
                TextButton(
                    onClick = {
                        prefs.esquecerDoProdutor(PREF_PRECO, PREF_CUSTO, PREF_PROD)
                        temPreco = false; temCusto = false; temProd = false
                        precoEm = 0L; custoEm = 0L; prodEm = 0L
                        customPreco = "%.2f".format(kpis.soja_preco_saca)
                        customCusto = "%.2f".format(kpis.custo_ha)
                        customProd = "%.1f".format(prodModelo)
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
                r.sinalIncerto -> if (isDark) Color(0xFFd29922) else Color(0xFFbf8700)
                lucro >= 0 -> if (isDark) Color(0xFF3fb950) else Color(0xFF16a34a)
                else -> if (isDark) Color(0xFFf85149) else Color(0xFFdc2626)
            }

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = if (temProd) "Receita Bruta" else "Receita Bruta Est.",
                         fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "R$ ${receita.toInt()}/ha", fontSize = 18.sp, color = (if(isDark) Color(0xFF58a6ff) else Color(0xFF2563eb)), fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Custo Operacional", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "R$ ${custo.toInt()}/ha", fontSize = 18.sp, color = Color(0xFFf85149), fontWeight = FontWeight.Bold)
                }
            }
            
            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "Lucro Líquido Proj.", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "R$ ${lucro.toInt()}/ha", fontSize = 22.sp, color = profitColor, fontWeight = FontWeight.ExtraBold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "ROI (Retorno)", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "${roi.toInt()}%", fontSize = 22.sp, color = profitColor, fontWeight = FontWeight.ExtraBold)
                }
            }
            
            if (r.sinalIncerto && outroRateio != null) {
                Text(
                    text = String.format(PT_BR, "Atenção: com estes dados o resultado pode ir de R$ %,d a R$ %,d por hectare, conforme quanto do custo variável acompanha a área e quanto acompanha a produção. A CONAB publica só o total por saca, sem abrir por item. Informe o seu custeio para a conta parar de depender disso.", 
                        minOf(lucro, outroRateio).toInt(), maxOf(lucro, outroRateio).toInt()),
                    fontSize = 12.sp,
                    color = if (isDark) Color(0xFFd29922) else Color(0xFFbf8700),
                    modifier = Modifier.padding(top = 12.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(text = "Simulação Inteligente", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(text = "Ponto Empate: ${(custo / preco).toInt()} sc/ha", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
fun CenarioClimaticoCard(municipio: String, baselineRendimento: Double) {
    val isDark = isSystemInDarkTheme()
    var precipFactor by remember { mutableStateOf(100f) }
    var tempOffset by remember { mutableStateOf(0f) }
    var delta by remember { mutableStateOf(0.0) }
    var simulado by remember { mutableStateOf(baselineRendimento) }
    var isSimulating by remember { mutableStateOf(false) }
    var resposta by remember { mutableStateOf<SimulacaoResponse?>(null) }
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
            } catch (e: Exception) {
                e.printStackTrace()
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
                Text(text = "Projeção Ajustada", fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
            
            Text(text = "Precipitação (${precipFactor.toInt()}%)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Slider(
                value = precipFactor,
                onValueChange = { precipFactor = it },
                onValueChangeFinished = { simular() },
                valueRange = 50f..150f,
                steps = 19
            )
            
            Text(text = "Desvio Térmico (${if (tempOffset > 0) "+" else ""}${String.format("%.1f", tempOffset)}°C)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Slider(
                value = tempOffset,
                onValueChange = { tempOffset = it },
                onValueChangeFinished = { simular() },
                valueRange = -2f..3f,
                steps = 9
            )

            // O simulador precisa declarar o que pode prometer. A associação
            // entre chuva e produtividade nesta base não é distinguível de
            // zero, e a variação que ele produz cabe dentro da margem de erro
            // do modelo. Sem isso o usuário lê ruído como resposta agronômica.
            resposta?.sensibilidade?.let { sens ->
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = "O que este número vale: a associação entre chuva e " +
                           "produtividade nesta base não é distinguível de zero " +
                           "(r = ${String.format("%.3f", sens.r).replace('.', ',')}; " +
                           "p = ${String.format("%.3f", sens.p).replace('.', ',')}; " +
                           "n = ${sens.n})." +
                           (resposta?.margem_kg_ha?.let {
                               " A variação acima cabe dentro da margem de erro do " +
                               "modelo, de ± ${it.toInt()} kg/ha."
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
            Row(verticalAlignment = Alignment.CenterVertically) {
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
            
            Text(text = "Satélite: MODIS (Resolução 250m)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(text = "Clima: CHIRPS (Chuva) & ERA5-Land (Temp.)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(text = "Base Territorial: MapBiomas e IBGE (PAM)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                    color = if (isDark) Color(0xFFd29922) else Color(0xFFbf8700)
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

// Períodos da tela Mercado: chave da API e rótulo do botão.
private val PERIODOS_MERCADO = listOf("1d" to "1D", "5d" to "5D", "1mo" to "1M", "6mo" to "6M")

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
            Text("Soja em Chicago, em R$/saca", fontWeight = FontWeight.Bold, fontSize = 16.sp,
                 color = MaterialTheme.colorScheme.onSurface)
            Text("Bolsa de Chicago (CBOT), contrato mais próximo, convertido pelo dólar de cada momento",
                 fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PERIODOS_MERCADO.forEach { (chave, rotulo) ->
                    FilterChip(selected = periodo == chave, onClick = { aoMudarPeriodo(chave) },
                               label = { Text(rotulo) })
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
                    Text("Cotação de $quando, com atraso de cerca de ${cot.atraso_min} min. Não é tempo real.",
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
                Text("${it.praca} (${it.uf}), ${it.tipo}: R$ ${reais(it.valor)}/sc, cotação do dia",
                     fontSize = 13.sp, color = secundaria)
            }
            mercado?.conab_saca?.let {
                Text("Porteira, ${mercado?.conab_fonte ?: "CONAB"}: R$ ${reais(it)}/sc, padrão da simulação",
                     fontSize = 13.sp, color = secundaria)
            }
            Spacer(Modifier.height(8.dp))
            Text("Preço de bolsa não é preço de porteira: entre Chicago e a fazenda há câmbio, " +
                 "frete, prêmio de porto e base. Informação de mercado, não recomendação de compra ou venda.",
                 fontSize = 12.sp, color = secundaria, lineHeight = 16.sp,
                 fontStyle = androidx.compose.ui.text.font.FontStyle.Italic)
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
        Text("Pará, estimado agora", fontSize = 12.sp, color = cor, fontWeight = FontWeight.SemiBold)
        Text("R$ ${reais(estimado)}/sc", fontSize = 22.sp, fontWeight = FontWeight.Bold,
             color = MaterialTheme.colorScheme.onSurface)
        Text("Chicago deste momento $sinal R$ ${reais(kotlin.math.abs(para.base_brl_saca))} de base do Pará " +
             "(${mesCurto(para.mes_base, anoCompleto = true)}). Estimativa, não cotação de praça.",
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
    Text("Base = média do Pará − média de Chicago no mês. Fonte do Pará: $fonte; " +
         "o mês corrente entra com a média parcial. Chicago: CBOT convertida pelo dólar de cada dia.",
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
    val marcas = eixoRedondo(minDado, maxDado)
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
        val corpo = (passo * 0.6f).coerceAtLeast(1f)
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
