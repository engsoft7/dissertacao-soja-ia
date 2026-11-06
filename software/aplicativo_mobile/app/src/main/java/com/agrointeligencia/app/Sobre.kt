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

// Sobre: aviso de não afiliação, fontes oficiais, origem do preço e do custo e
// métricas da validação do modelo.

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
