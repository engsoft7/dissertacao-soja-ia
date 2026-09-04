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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

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
private data class Resultado(
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
private fun resultadoPorHectare(
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

private fun SharedPreferences.valorDoProdutor(chave: String): Float? =
    getFloat(chave, -1f).takeIf { it > 0f }

private fun SharedPreferences.informadoEm(chave: String): Long =
    getLong(chave + "_em", 0L)

private fun SharedPreferences.guardarDoProdutor(chave: String, valor: Double, quando: Long) {
    edit().putFloat(chave, valor.toFloat()).putLong(chave + "_em", quando).apply()
}

private fun SharedPreferences.esquecerDoProdutor(vararg chaves: String) {
    val editor = edit()
    for (chave in chaves) {
        editor.remove(chave)
        editor.remove(chave + "_em")
    }
    editor.apply()
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val isDark = isSystemInDarkTheme()
            val colors = if (isDark) {
                darkColorScheme(
                    background = Color(0xFF0F172A),
                    surface = Color(0xFF1E293B),
                    primary = Color(0xFF10B981),
                    onBackground = Color(0xFFE2E8F0),
                    onSurface = Color(0xFFE2E8F0)
                )
            } else {
                lightColorScheme(
                    background = Color(0xFFF8FAFC),
                    surface = Color(0xFFFFFFFF),
                    primary = Color(0xFF059669),
                    onBackground = Color(0xFF1E293B),
                    onSurface = Color(0xFF1E293B)
                )
            }
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
    var currentTab by remember { mutableStateOf(0) }
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
                    Icon(Icons.Filled.AddCircle, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "AgroInteligência Pro",
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
                
                if (currentTab != 2) {
                    Text(text = "Município Selecionado:", color = MaterialTheme.colorScheme.onBackground)
                    
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

            if (isLoading) {
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
                                color = Color.Gray,
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
                                            text = "Simulador Climático (What-If)",
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
                                    fontSize = 11.sp,
                                    color = Color.Gray,
                                    lineHeight = 15.sp,
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
                                MetodologiaCard(kpis)
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
                                        Text("Mapa indisponível offline", fontWeight = FontWeight.Bold, color = Color.Gray, fontSize = 16.sp)
                                        Spacer(modifier = Modifier.height(8.dp))
                                        Text("O mapa é desenhado pela API. Conecte-se para carregá-lo.", color = Color.Gray, fontSize = 14.sp)
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

@Composable
fun PrevisaoCard(historico: PrevisaoHistorico, kpis: FinancaResponse?) {
    val isDark = isSystemInDarkTheme()
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE) }
    // O mesmo preço e o mesmo custo do Resumo Financeiro. Sem isto, o produtor
    // informava o preço dele numa aba e via o histórico calculado com o da
    // CONAB na outra — duas margens diferentes para a mesma lavoura, no mesmo
    // aplicativo. Num produto de campo, isso destrói a confiança no número.
    val precoDoProdutor = remember { prefs.valorDoProdutor(PREF_PRECO)?.toDouble() }
    val custoDoProdutor = remember { prefs.valorDoProdutor(PREF_CUSTO)?.toDouble() }
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
                    text = if (observado) "%,d kg".format(historico.rendimento_real.toInt())
                           else "não divulgada",
                    fontWeight = FontWeight.Bold,
                    fontSize = if (observado) 16.sp else 12.sp,
                    maxLines = 1,
                    color = if (observado) MaterialTheme.colorScheme.onSurface else Color.Gray
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
                text = "Estimativa %,d kg · erro típico ±%,d kg/ha".format(
                    historico.rendimento_predito.toInt(), historico.margem_erro.toInt()),
                fontSize = 12.sp,
                color = Color.Gray,
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
                            else "Resultado projetado: ") + "R$ %,d/ha".format(r.valor.toInt()),
                    fontSize = 13.sp,
                    color = color,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 8.dp)
                )
                if (r.sinalIncerto && outro != null) {
                    Text(
                        text = "Pode ir de R$ %,d a R$ %,d conforme o rateio do custo, que a CONAB não publica aberto por item.".format(
                            minOf(r.valor, outro).toInt(), maxOf(r.valor, outro).toInt()),
                        fontSize = 11.sp,
                        color = Color.Gray,
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
            Text(text = "Rendimento Esperado", fontSize = 14.sp, color = Color.Gray)
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = "${projYield.toInt()} kg/ha", 
                    fontSize = 28.sp, 
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(text = " (~ ${(projYield / 60).toInt()} sc/ha)", fontSize = 14.sp, color = Color.Gray, modifier = Modifier.padding(start = 8.dp, bottom = 4.dp))
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
                        Text(text = "Safra ${ultimoReal.ano} ($typeStr)", fontSize = 12.sp, color = Color.Gray)
                        Text(text = "${pastYield.toInt()} kg/ha", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(text = "Variação (YoY)", fontSize = 12.sp, color = Color.Gray)
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

    var precoEm by remember { mutableStateOf(prefs.informadoEm(PREF_PRECO)) }
    var temPreco by remember { mutableStateOf(precoSalvo != null) }
    var temCusto by remember { mutableStateOf(custoSalvo != null) }
    var temProd by remember { mutableStateOf(prodSalva != null) }

    var customPreco by remember {
        mutableStateOf((precoSalvo?.toDouble() ?: kpis.soja_preco_saca).toString())
    }
    var customCusto by remember {
        mutableStateOf((custoSalvo?.toDouble() ?: kpis.custo_ha).toString())
    }
    var customProd by remember {
        mutableStateOf("%.1f".format(prodSalva?.toDouble() ?: prodModelo))
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
                            prefs.guardarDoProdutor(PREF_PROD, valor, System.currentTimeMillis())
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
                            prefs.guardarDoProdutor(PREF_PRECO, valor, System.currentTimeMillis())
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
                            prefs.guardarDoProdutor(PREF_CUSTO, valor, System.currentTimeMillis())
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
                Text(text = legenda, fontSize = 11.sp, color = Color.Gray)
            }
            if (seus.isNotEmpty()) {
                Text(
                    text = "Informados em " + quando.format(java.util.Date(
                        maxOf(precoEm, prefs.informadoEm(PREF_CUSTO), prefs.informadoEm(PREF_PROD)))) + ".",
                    fontSize = 11.sp,
                    color = Color.Gray
                )
                // Caminho de volta, para ninguém ficar preso a um número
                // digitado errado sem saber de onde vinha o padrão.
                TextButton(
                    onClick = {
                        prefs.esquecerDoProdutor(PREF_PRECO, PREF_CUSTO, PREF_PROD)
                        temPreco = false; temCusto = false; temProd = false
                        precoEm = 0L
                        customPreco = kpis.soja_preco_saca.toString()
                        customCusto = kpis.custo_ha.toString()
                        customProd = "%.1f".format(prodModelo)
                    },
                    contentPadding = PaddingValues(horizontal = 0.dp, vertical = 0.dp)
                ) {
                    Text(text = "Voltar aos valores padrão", fontSize = 11.sp)
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
                         fontSize = 12.sp, color = Color.Gray)
                    Text(text = "R$ ${receita.toInt()}/ha", fontSize = 18.sp, color = (if(isDark) Color(0xFF58a6ff) else Color(0xFF2563eb)), fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Custo Operacional", fontSize = 12.sp, color = Color.Gray)
                    Text(text = "R$ ${custo.toInt()}/ha", fontSize = 18.sp, color = Color(0xFFf85149), fontWeight = FontWeight.Bold)
                }
            }
            
            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = Color.DarkGray)
            
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "Lucro Líquido Proj.", fontSize = 13.sp, color = Color.Gray)
                    Text(text = "R$ ${lucro.toInt()}/ha", fontSize = 22.sp, color = profitColor, fontWeight = FontWeight.ExtraBold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "ROI (Retorno)", fontSize = 13.sp, color = Color.Gray)
                    Text(text = "${roi.toInt()}%", fontSize = 22.sp, color = profitColor, fontWeight = FontWeight.ExtraBold)
                }
            }
            
            if (r.sinalIncerto && outroRateio != null) {
                Text(
                    text = "Atenção: com estes dados o resultado pode ir de R$ %,d a R$ %,d por hectare, conforme quanto do custo variável acompanha a área e quanto acompanha a produção. A CONAB publica só o total por saca, sem abrir por item. Informe o seu custeio para a conta parar de depender disso.".format(
                        minOf(lucro, outroRateio).toInt(), maxOf(lucro, outroRateio).toInt()),
                    fontSize = 11.sp,
                    color = if (isDark) Color(0xFFd29922) else Color(0xFFbf8700),
                    modifier = Modifier.padding(top = 12.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(text = "Simulação Inteligente", fontSize = 11.sp, color = Color.Gray)
                Text(text = "Ponto Empate: ${(custo / preco).toInt()} sc/ha", fontSize = 11.sp, color = Color.Gray)
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
                Text(text = "Projeção Ajustada", fontSize = 14.sp, color = Color.Gray)
                if (isSimulating) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                }
            }
            
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = "${simulado.toInt()} kg/ha", 
                    fontSize = 28.sp, 
                    fontWeight = FontWeight.Bold,
                    color = if (delta < 0) (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626)) else if (delta > 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else MaterialTheme.colorScheme.primary
                )
                if (kotlin.math.abs(delta) > 1) {
                    val sign = if (delta >= 0) "+" else ""
                    val c = if (delta >= 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626))
                    Text(text = " ($sign${delta.toInt()} kg/ha)", fontSize = 14.sp, color = c, modifier = Modifier.padding(start = 8.dp, bottom = 4.dp))
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            
            Text(text = "Precipitação (${precipFactor.toInt()}%)", fontSize = 12.sp, color = Color.LightGray)
            Slider(
                value = precipFactor,
                onValueChange = { precipFactor = it },
                onValueChangeFinished = { simular() },
                valueRange = 50f..150f,
                steps = 19
            )
            
            Text(text = "Desvio Térmico (${if (tempOffset > 0) "+" else ""}${String.format("%.1f", tempOffset)}°C)", fontSize = 12.sp, color = Color.LightGray)
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
                    fontSize = 11.sp, color = Color.Gray, lineHeight = 15.sp
                )
            }
            resposta?.fora_da_faixa?.takeIf { it.isNotEmpty() }?.let {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Cenário fora da faixa observada na base; o resultado foi " +
                           "preso ao limite do que o modelo viu.",
                    fontSize = 11.sp,
                    color = if (isDark) Color(0xFFd29922) else Color(0xFF9a6700),
                    lineHeight = 15.sp
                )
            }
        }
    }
}

@Composable
fun MetodologiaCard(kpis: FinancaResponse?) {
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
            
            Text(text = "Satélite: MODIS (Resolução 250m)", fontSize = 12.sp, color = Color.Gray)
            Text(text = "Clima: CHIRPS (Chuva) & ERA5-Land (Temp.)", fontSize = 12.sp, color = Color.Gray)
            Text(text = "Base Territorial: MapBiomas e IBGE (PAM)", fontSize = 12.sp, color = Color.Gray)
            // Preço e custo são constantes de um levantamento datado, não cotação
            // diária. Sem a praça e a data o número envelhece sem avisar — por isso
            // o rótulo vem da API, junto com a frase que diz onde o preço está na
            // série da praça: quando a CONAB publica levantamento novo, esta tela
            // acompanha sem recompilar o APK.
            Text(text = "Preço e custo: " + (kpis?.fonte_preco ?: "CONAB (levantamento indisponível offline)"), fontSize = 12.sp, color = Color.Gray)
            Text(text = "Preço de porteira, não cotação de bolsa. Ambos editáveis na tela Resumo.", fontSize = 12.sp, color = Color.Gray)
            kpis?.nota_preco?.let {
                Text(text = it, fontSize = 12.sp, color = Color.Gray)
            }
            kpis?.aviso_preco?.let {
                Text(
                    text = it,
                    fontSize = 12.sp,
                    color = if (isDark) Color(0xFFd29922) else Color(0xFFbf8700)
                )
            }
            
            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = Color.DarkGray)
            
            // Métricas da validação temporal deixando um ano de fora por vez, sobre
            // os 415 registros da base. São as mesmas da Tabela 6 da dissertação e do
            // painel web; a fonte da verdade é pesquisa/dados/metricas_validacao.json.
            // O R² da referência aparece ao lado de propósito: o modelo empata com o
            // histórico municipal somado à tendência, e omitir isso superestimaria o
            // que a ferramenta entrega.
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "R² do modelo", fontSize = 11.sp, color = Color.Gray)
                    Text(text = "0,216", fontSize = 14.sp, color = (if(isDark) Color(0xFFbc8cff) else Color(0xFF7c3aed)), fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "R² da tendência (referência)", fontSize = 11.sp, color = Color.Gray)
                    Text(text = "0,216", fontSize = 14.sp, color = (if(isDark) Color(0xFF8b949e) else Color(0xFF57606a)), fontWeight = FontWeight.Bold)
                }
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = "Erro típico de ± 416 kg/ha, ou 13,9% da produtividade média, " +
                       "sobre 415 registros de 38 municípios.",
                fontSize = 11.sp, color = Color.Gray, lineHeight = 15.sp
            )
            
            Spacer(modifier = Modifier.height(20.dp))
            Text(
                text = "Aviso Legal: Este é um projeto de pesquisa acadêmica em Inteligência Artificial. As estimativas projetadas pela IA e os valores financeiros não configuram recomendação de investimento ou consultoria agronômica. Consulte profissionais certificados antes de tomar decisões financeiras reais.",
                fontSize = 12.sp,
                color = Color.LightGray,
                fontStyle = androidx.compose.ui.text.font.FontStyle.Italic,
                lineHeight = 16.sp,
                textAlign = androidx.compose.ui.text.style.TextAlign.Justify
            )
        }
    }
}



@Composable
fun HistoricoProdutividadeChart(historico: List<PrevisaoHistorico>, previsao: PrevisaoResponse?) {
    val isDark = isSystemInDarkTheme()
    val lineColorPre = if (isDark) Color(0xFF00E5FF) else Color(0xFF0284C7)
    val lineColorReal = if (isDark) Color(0xFF3fb950) else Color(0xFF16a34a)
    val elNinoColor = if(isDark) Color(0x33FF5555) else Color(0x33FF4444)
    val laNinaColor = if(isDark) Color(0x335555FF) else Color(0x334444FF)
    
    val textColor = if (isDark) android.graphics.Color.LTGRAY else android.graphics.Color.DKGRAY
    val alertTextPaint = Paint().apply {
        textSize = 22f
        isFakeBoldText = true
    }

    if (historico.isEmpty()) return

    val minYear = historico.minOf { it.ano }
    val maxYear = historico.maxOf { it.ano }
    
    val maxYield = kotlin.math.max(
        historico.maxOf { it.rendimento_real },
        historico.maxOf { if (it.rendimento_predito > 0) it.rendimento_predito else 0.0 }
    ).toFloat()
    
    val yMax = maxYield * 1.15f
    
    val elNinos = previsao?.elNinos ?: emptyList()
    val laNinas = previsao?.laNinas ?: emptyList()

    Card(
        modifier = Modifier.fillMaxWidth().height(300.dp).padding(vertical = 8.dp),
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text("Evolução Histórica e Projeção (kg/ha)", fontWeight = FontWeight.Bold, fontSize = 16.sp, color = MaterialTheme.colorScheme.onSurface)
            Spacer(modifier = Modifier.height(16.dp))
            Canvas(modifier = Modifier.fillMaxSize().padding(end = 16.dp, bottom = 8.dp)) {
                val paddingX = 90f // Espaço para os números do eixo Y
                val paddingY = 60f // Espaço inferior pros anos
                val w = size.width - paddingX
                val h = size.height - paddingY
                val yearSpan = maxYear - minYear
                if (yearSpan == 0) return@Canvas
                
                // Desenhar El Nino e La Nina
                for (year in minYear..maxYear) {
                    val x = paddingX + (year - minYear) * (w / yearSpan)
                    if (year in elNinos) {
                        drawRect(color = elNinoColor, topLeft = Offset(x - 12f, 0f), size = Size(24f, h))
                        drawContext.canvas.nativeCanvas.apply {
                            alertTextPaint.color = if(isDark) android.graphics.Color.parseColor("#ff8888") else android.graphics.Color.parseColor("#cc0000")
                            save()
                            rotate(-90f, x, h / 2)
                            drawText("EL NIÑO", x - 40f, (h / 2) - 15f, alertTextPaint)
                            restore()
                        }
                    } else if (year in laNinas) {
                        drawRect(color = laNinaColor, topLeft = Offset(x - 12f, 0f), size = Size(24f, h))
                        drawContext.canvas.nativeCanvas.apply {
                            alertTextPaint.color = if(isDark) android.graphics.Color.parseColor("#8888ff") else android.graphics.Color.parseColor("#0000cc")
                            save()
                            rotate(-90f, x, h / 2)
                            drawText("LA NIÑA", x - 40f, (h / 2) - 15f, alertTextPaint)
                            restore()
                        }
                    }
                }

                // Grid Horizontal e Y labels
                val gridPaint = Paint().apply { color = textColor; textSize = 24f }
                for (i in 0..4) {
                    val yLine = h - (i * (h / 4))
                    val yieldVal = (i * (yMax / 4)).toInt()
                    drawLine(color = Color.Gray.copy(alpha = 0.2f), start = Offset(paddingX, yLine), end = Offset(paddingX + w, yLine), strokeWidth = 2f)
                    drawContext.canvas.nativeCanvas.drawText("$yieldVal", 0f, yLine + 8f, gridPaint)
                }
                
                // X labels (anos) de 5 em 5
                for (year in minYear..maxYear step 5) {
                    val x = paddingX + (year - minYear) * (w / yearSpan)
                    drawContext.canvas.nativeCanvas.drawText("$year", x - 20f, h + 45f, gridPaint)
                }

                // Separar os dados em Real (passado) vs Predito (futuro)
                val historicoOrdenado = historico.sortedBy { it.ano }
                val lastRealItem = historicoOrdenado.lastOrNull { it.rendimento_real > 0 }
                val startPredYear = lastRealItem?.ano ?: maxYear

                // Desenhar linha REAL (Verde)
                val pathReal = Path()
                var firstReal = true
                historicoOrdenado.filter { it.rendimento_real > 0 }.forEach { item ->
                    val x = paddingX + (item.ano - minYear) * (w / yearSpan)
                    val y = h - ((item.rendimento_real.toFloat() / yMax) * h)
                    if (firstReal) { pathReal.moveTo(x, y); firstReal = false } 
                    else { pathReal.lineTo(x, y) }
                    drawCircle(color = lineColorReal, radius = 6f, center = Offset(x, y))
                }
                drawPath(path = pathReal, color = lineColorReal, style = Stroke(width = 6f))

                // Desenhar linha PREDIÇÃO (Azul tracejada), começa no ultimo real e vai pro futuro
                val pathPred = Path()
                var firstPred = true
                historicoOrdenado.filter { it.ano >= startPredYear }.forEach { item ->
                    val x = paddingX + (item.ano - minYear) * (w / yearSpan)
                    // Se for o ano de pivô (ultim real), plotamos o valor real para a linha azul conectar suavemente
                    val valPlot = if (item.ano == startPredYear) item.rendimento_real else item.rendimento_predito
                    val y = h - ((valPlot.toFloat() / yMax) * h)
                    
                    if (firstPred) { pathPred.moveTo(x, y); firstPred = false } 
                    else { pathPred.lineTo(x, y) }
                    
                    if (item.ano > startPredYear) {
                        drawCircle(color = lineColorPre, radius = 6f, center = Offset(x, y))
                    }
                }
                drawPath(path = pathPred, color = lineColorPre, style = Stroke(
                    width = 6f,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(15f, 15f), 0f)
                ))
            }
        }
    }
}
