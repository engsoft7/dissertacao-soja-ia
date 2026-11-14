package com.agrointeligencia.app

import android.os.Bundle
import android.content.Context
import android.content.SharedPreferences
import androidx.activity.ComponentActivity
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
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

// Resumo: atalho da Estimativa no campo, produtividade esperada da safra e
// simulador de cenário climático.

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
                Text(stringResource(R.string.campo_atalho_titulo), fontWeight = FontWeight.SemiBold, fontSize = 16.sp,
                     color = MaterialTheme.colorScheme.onSurface)
                Text(stringResource(R.string.campo_atalho_texto),
                     fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp)
            }
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
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
            Text(text = stringResource(R.string.resumo_esperada, projecao.ano), fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = "${milhar(projYield)} kg/ha", 
                    fontSize = 28.sp, 
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(text = " " + stringResource(R.string.resumo_sacas_ha, (projYield / 60).roundToInt()), fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = 8.dp, bottom = 4.dp))
            }
            // O erro típico vai junto do número: é uma estimativa, e a loja
            // promete a margem de erro sempre ao lado dela.
            if (projecao.margem_erro > 0) {
                Text(text = stringResource(R.string.resumo_erro_tipico, milhar(projecao.margem_erro)),
                     fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            
            if (ultimoReal != null) {
                val pastYield = if (ultimoReal.rendimento_real > 0) ultimoReal.rendimento_real else ultimoReal.rendimento_predito
                val typeStr = stringResource(if (ultimoReal.rendimento_real > 0) R.string.resumo_tipo_ibge else R.string.resumo_tipo_estimada)
                val diff = projYield - pastYield
                val diffPct = if (pastYield > 0) (diff / pastYield) * 100 else 0.0
                val color = if (diff >= 0) (if(isDark) Color(0xFF3fb950) else Color(0xFF16a34a)) else (if(isDark) Color(0xFFf85149) else Color(0xFFdc2626))
                val sign = if (diff >= 0) "+" else ""
                
                Spacer(modifier = Modifier.height(16.dp))
                // Cada coluna com metade da largura: com a fonte do sistema em
                // 200%, "Safra 2025, IBGE" e "Em relação a 2025" se encostavam.
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(text = stringResource(R.string.resumo_safra_tipo, ultimoReal.ano, typeStr), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(text = "${milhar(pastYield)} kg/ha", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }
                    Column(Modifier.weight(1f), horizontalAlignment = Alignment.End) {
                        // Entre a safra esperada e a última divulgada pode haver
                        // mais de um ano: "variação anual" dizia outra coisa.
                        Text(text = stringResource(R.string.resumo_em_relacao, ultimoReal.ano), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                             textAlign = androidx.compose.ui.text.style.TextAlign.End)
                        Text(text = "$sign${diffPct.roundToInt()}%", fontSize = 16.sp, color = color, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

@Composable
fun CenarioClimaticoCard(municipio: String, baselineRendimento: Double, ano: Int? = null, uf: String? = null) {
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
                val req = SimulacaoRequest(municipio, precipFactor / 100.0, tempOffset.toDouble(), ano, uf)
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
                // A mesma safra do Resumo, que vai também para a API.
                Text(text = ano?.let { stringResource(R.string.cenario_projecao_safra, it) }
                         ?: stringResource(R.string.cenario_projecao),
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
            val chuva = stringResource(R.string.cenario_chuva_media, precipFactor.roundToInt())
            val temperatura = if (kotlin.math.abs(tempOffset) < 0.05f) stringResource(R.string.cenario_temperatura_media)
                              else stringResource(R.string.cenario_temperatura_desvio, String.format(LOCAL_NUMEROS, "%+.1f", tempOffset))
            val descricaoChuva = stringResource(R.string.cenario_chuva_descricao)
            val descricaoTemperatura = stringResource(R.string.cenario_temperatura_descricao)
            Text(text = stringResource(R.string.cenario_chuva_rotulo, chuva), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Slider(
                modifier = Modifier.semantics { contentDescription = descricaoChuva; stateDescription = chuva },
                value = precipFactor,
                onValueChange = { precipFactor = it },
                onValueChangeFinished = { simular() },
                valueRange = 50f..150f,
                steps = 19
            )
            
            Text(text = stringResource(R.string.cenario_temperatura_rotulo, temperatura), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Slider(
                modifier = Modifier.semantics { contentDescription = descricaoTemperatura; stateDescription = temperatura },
                value = tempOffset,
                onValueChange = { tempOffset = it },
                onValueChangeFinished = { simular() },
                valueRange = -2f..3f,
                steps = 9
            )

            if (falhou) {
                Text(
                    text = stringResource(R.string.cenario_falhou),
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
                    // Com a API nova, o efeito que o cenário de fato usou
                    // (fraseDaAssociacao); com a antiga, a conclusão do teste da
                    // chuva, cujos números (r, p, n) estão na dissertação.
                    text = (resposta?.associacao?.let { fraseDaAssociacao(LocalContext.current, it) }
                            ?: stringResource(if (sens.p >= 0.05) R.string.cenario_chuva_sem_efeito else R.string.cenario_chuva_pequeno)) +
                           (resposta?.margem_kg_ha?.let {
                               " " + stringResource(if (kotlin.math.abs(delta) <= it) R.string.cenario_cabe_margem
                                                    else R.string.cenario_passa_margem, milhar(it))
                           } ?: ""),
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp
                )
            }
            resposta?.fora_da_faixa?.takeIf { it.isNotEmpty() }?.let {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = stringResource(R.string.cenario_fora_faixa),
                    fontSize = 12.sp,
                    color = if (isDark) Color(0xFFd29922) else Color(0xFF9a6700),
                    lineHeight = 16.sp
                )
            }
        }
    }
}

/**
 * O efeito que o cenário usou, em palavras: só o que a base mostra com IC95
 * sem o zero (model.associacao_climatica, na API). Em Mato Grosso, por
 * exemplo, nem a chuva nem a temperatura passam nesse teste, e o cenário não
 * move a projeção; no Maranhão, a chuva passa.
 */
fun fraseDaAssociacao(context: Context, a: AssociacaoClimatica): String {
    val claros = mutableListOf<String>()
    val semEfeito = mutableListOf<String>()
    a.chuva?.let { c ->
        if (c.vale) claros += context.getString(
            if (c.kg_ha > 0) R.string.assoc_chuva_menos else R.string.assoc_chuva_mais, milhar(kotlin.math.abs(c.kg_ha) * 10))
        else semEfeito += context.getString(R.string.assoc_a_chuva)
    }
    a.temperatura?.let { t ->
        if (t.vale) claros += context.getString(
            if (t.kg_ha < 0) R.string.assoc_temp_tirou else R.string.assoc_temp_somou, milhar(kotlin.math.abs(t.kg_ha)))
        else semEfeito += context.getString(R.string.assoc_a_temperatura)
    }
    val e = " " + context.getString(R.string.assoc_e) + " "
    return when {
        claros.isEmpty() -> context.getString(R.string.assoc_nenhum)
        semEfeito.isEmpty() -> context.getString(R.string.assoc_claros, claros.joinToString(e))
        else -> context.getString(R.string.assoc_claros_sem_efeito, claros.joinToString(e), semEfeito.joinToString(e))
    }
}
