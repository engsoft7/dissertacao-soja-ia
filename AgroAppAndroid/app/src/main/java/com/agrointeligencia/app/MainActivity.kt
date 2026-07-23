package com.agrointeligencia.app

import android.os.Bundle
import android.content.Context
import androidx.activity.ComponentActivity
import androidx.compose.ui.platform.LocalContext
import androidx.core.view.WindowCompat
import android.app.Activity
import androidx.compose.ui.graphics.toArgb
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
                        window.statusBarColor = colors.background.toArgb()
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
    var kpis by remember { mutableStateOf<KpiEconomiaResponse?>(null) }
    var isLoading by remember { mutableStateOf(false) }
    var expanded by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }
    var currentTab by remember { mutableStateOf(0) }
    var isOfflineMode by remember { mutableStateOf(false) }
    
    val context = LocalContext.current
    val sharedPrefs = remember { context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE) }
    val gson = remember { Gson() }
    
    fun loadData() {
        errorMsg = null
        
        // --- 1. Optimistic Cache Load ---
        val cachedMunStr = sharedPrefs.getString("municipios", null)
        val cachedKpiStr = sharedPrefs.getString("kpis", null)
        
        if (cachedMunStr != null && cachedKpiStr != null) {
            val mResponse = gson.fromJson(cachedMunStr, MunicipioResponse::class.java)
            municipios = mResponse.municipios
            if (municipios.isNotEmpty() && selectedMunicipio == null) {
                selectedMunicipio = municipios[0]
            }
            kpis = gson.fromJson(cachedKpiStr, KpiEconomiaResponse::class.java)
            // Do not assume offline yet to avoid flickering
        } else {
            isLoading = true // Only show spinner if absolutely no data is available
        }
        
        // --- 2. Background Sync ---
        coroutineScope.launch {
            try {
                val response = RetrofitClient.getInstance().getMunicipios()
                val kpisResponse = RetrofitClient.getInstance().getKpisEconomia()
                
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
                    onClick = { currentTab = 0 },
                    icon = { Icon(Icons.Filled.Home, contentDescription = "Resumo") },
                    label = { Text("Resumo") }
                )
                NavigationBarItem(
                    selected = currentTab == 1,
                    onClick = { currentTab = 1 },
                    icon = { Icon(Icons.Filled.List, contentDescription = "Histórico") },
                    label = { Text("Histórico") }
                )
                NavigationBarItem(
                    selected = currentTab == 2,
                    onClick = { currentTab = 2 },
                    icon = { Icon(Icons.Filled.Info, contentDescription = "Sobre") },
                    label = { Text("Sobre") }
                )
            }
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
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
                            modifier = Modifier.menuAnchor().fillMaxWidth()
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
                        1 -> { // Histórico
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
                            }
                            items(historicoOrdenado) { hist ->
                                PrevisaoCard(hist, kpis)
                            }
                        }
                        2 -> { // Sobre
                            item {
                                MetodologiaCard()
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun PrevisaoCard(historico: PrevisaoHistorico, kpis: KpiEconomiaResponse?) {
    val isDark = isSystemInDarkTheme()
    Card(
        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(text = "Ano ${historico.ano}", fontWeight = FontWeight.Bold)
                Text(text = "Margem: ±${historico.margem_erro.toInt()} kg/ha", fontSize = 12.sp, color = Color.Gray)
                if (kpis != null && historico.rendimento_predito > 0) {
                    val scHa = historico.rendimento_predito / 60
                    val receita = scHa * kpis.soja_preco_saca
                    val lucro = receita - kpis.custo_ha
                    val color = if (lucro > 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626))
                    Text(
                        text = "Margem Liq.: R$ ${lucro.toInt()}/ha",
                        fontSize = 13.sp,
                        color = color,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(top = 8.dp)
                    )
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "Real: ${historico.rendimento_real.toInt()} kg",
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = "IA: ${historico.rendimento_predito.toInt()} kg",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
fun ResumoAgronomicoCard(projecao: PrevisaoHistorico, ultimoReal: PrevisaoHistorico?) {
    val isDark = isSystemInDarkTheme()
    Card(
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 8.dp),
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
fun ResumoFinanceiroCard(projecao: PrevisaoHistorico, kpis: KpiEconomiaResponse) {
    val isDark = isSystemInDarkTheme()
    var customPreco by remember { mutableStateOf(kpis.soja_preco_saca.toString()) }
    var customCusto by remember { mutableStateOf(kpis.custo_ha.toString()) }

    Card(
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 8.dp),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            val preco = customPreco.toDoubleOrNull() ?: kpis.soja_preco_saca
            val custo = customCusto.toDoubleOrNull() ?: kpis.custo_ha

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                OutlinedTextField(
                    value = customPreco,
                    onValueChange = { customPreco = it },
                    label = { Text("Preço Saca (R$)", fontSize = 12.sp) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9),
                        unfocusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9)
                    )
                )
                OutlinedTextField(
                    value = customCusto,
                    onValueChange = { customCusto = it },
                    label = { Text("Custo/ha (R$)", fontSize = 12.sp) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9),
                        unfocusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9)
                    )
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))

            val scHa = projecao.rendimento_predito / 60
            val receita = scHa * preco
            val lucro = receita - custo
            val roi = if (custo > 0) (lucro / custo) * 100 else 0.0
            val profitColor = if (lucro >= 0) (if (isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if (isDark) Color(0xFFf85149) else Color(0xFFdc2626))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "Receita Bruta Est.", fontSize = 12.sp, color = Color.Gray)
                    Text(text = "R$ ${receita.toInt()}/ha", fontSize = 18.sp, color = (if(isDark) Color(0xFF58a6ff) else Color(0xFF2563eb)), fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Custo Operacional", fontSize = 12.sp, color = Color.Gray)
                    Text(text = "R$ ${custo.toInt()}/ha", fontSize = 18.sp, color = Color(0xFFf85149), fontWeight = FontWeight.Bold)
                }
            }
            
            Divider(modifier = Modifier.padding(vertical = 12.dp), color = Color.DarkGray)
            
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
    val coroutineScope = rememberCoroutineScope()

    fun simular() {
        coroutineScope.launch {
            isSimulating = true
            try {
                val req = SimulacaoRequest(municipio, precipFactor / 100.0, tempOffset.toDouble())
                val resp = RetrofitClient.getInstance().simularCenario(req)
                simulado = resp.estimativa_kg_ha
                delta = resp.delta_kg_ha
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
        }
    }
}

@Composable
fun MetodologiaCard() {
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
            Text(text = "Mercado Financeiro: CBOT/Yahoo Finance (Soja & Dólar)", fontSize = 12.sp, color = Color.Gray)
            
            Divider(modifier = Modifier.padding(vertical = 12.dp), color = Color.DarkGray)
            
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "Aderência Preditiva (R²)", fontSize = 11.sp, color = Color.Gray)
                    Text(text = "0.963", fontSize = 14.sp, color = (if(isDark) Color(0xFFbc8cff) else Color(0xFF7c3aed)), fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Variação Relativa", fontSize = 11.sp, color = Color.Gray)
                    Text(text = "± 12.4%", fontSize = 14.sp, color = (if(isDark) Color(0xFF58a6ff) else Color(0xFF2563eb)), fontWeight = FontWeight.Bold)
                }
            }
            
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


