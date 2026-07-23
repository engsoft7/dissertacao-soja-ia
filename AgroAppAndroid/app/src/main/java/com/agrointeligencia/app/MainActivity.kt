package com.agrointeligencia.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
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
            MaterialTheme(
                colorScheme = darkColorScheme(
                    background = Color(0xFF0F172A),
                    surface = Color(0xFF1E293B),
                    primary = Color(0xFF10B981),
                    onBackground = Color(0xFFE2E8F0),
                    onSurface = Color(0xFFE2E8F0)
                )
            ) {
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
    
    fun loadData() {
        coroutineScope.launch {
            try {
                errorMsg = null
                isLoading = true
                val response = RetrofitClient.getInstance().getMunicipios()
                municipios = response.municipios
                if (municipios.isNotEmpty()) {
                    selectedMunicipio = municipios[0]
                }
                kpis = RetrofitClient.getInstance().getKpisEconomia()
            } catch (e: Exception) {
                e.printStackTrace()
                errorMsg = "Erro na API: ${e.message}"
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
            isLoading = true
            try {
                previsao = RetrofitClient.getInstance().getPrevisao(mun)
            } catch (e: Exception) {
                e.printStackTrace()
            } finally {
                isLoading = false
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
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF331515)),
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp)
                    ) {
                        Text(
                            text = "🚨 $errorMsg",
                            color = Color(0xFFff8888),
                            modifier = Modifier.padding(16.dp),
                            fontWeight = FontWeight.Bold
                        )
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
                    val color = if (lucro > 0) Color(0xFF3fb950) else Color(0xFFf85149)
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
                val color = if (diff >= 0) Color(0xFF3fb950) else Color(0xFFf85149)
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
                        focusedContainerColor = Color(0xFF161b22),
                        unfocusedContainerColor = Color(0xFF161b22)
                    )
                )
                OutlinedTextField(
                    value = customCusto,
                    onValueChange = { customCusto = it },
                    label = { Text("Custo/ha (R$)", fontSize = 12.sp) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = Color(0xFF161b22),
                        unfocusedContainerColor = Color(0xFF161b22)
                    )
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))

            val scHa = projecao.rendimento_predito / 60
            val receita = scHa * preco
            val lucro = receita - custo
            val roi = if (custo > 0) (lucro / custo) * 100 else 0.0
            val profitColor = if (lucro >= 0) Color(0xFF3fb950) else Color(0xFFf85149)

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "Receita Bruta Est.", fontSize = 12.sp, color = Color.Gray)
                    Text(text = "R$ ${receita.toInt()}/ha", fontSize = 18.sp, color = Color(0xFF58a6ff), fontWeight = FontWeight.Bold)
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
                    color = if (delta < 0) Color(0xFFf85149) else if (delta > 0) Color(0xFF3fb950) else MaterialTheme.colorScheme.primary
                )
                if (kotlin.math.abs(delta) > 1) {
                    val sign = if (delta >= 0) "+" else ""
                    val c = if (delta >= 0) Color(0xFF3fb950) else Color(0xFFf85149)
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
            
            Divider(modifier = Modifier.padding(vertical = 12.dp), color = Color.DarkGray)
            
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "Aderência Preditiva (R²)", fontSize = 11.sp, color = Color.Gray)
                    Text(text = "0.963", fontSize = 14.sp, color = Color(0xFFbc8cff), fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Variação Relativa", fontSize = 11.sp, color = Color.Gray)
                    Text(text = "± 12.4%", fontSize = 14.sp, color = Color(0xFF58a6ff), fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}


