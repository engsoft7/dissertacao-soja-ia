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

// Viabilidade da safra: receita, custo e margem por hectare com os números do
// produtor, e o resultado pelos dois rateios possíveis do custo da CONAB.

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
internal const val PREF_PRECO = "preco_usuario_saca"
internal const val PREF_CUSTO = "custo_usuario_ha"
internal const val PREF_PROD = "produtividade_usuario_sc"
// Passado esse tempo, o app pede confirmação do preço. Não o descarta: um
// número velho do produtor ainda vale mais que um padrão de levantamento.
internal const val DIAS_PARA_RECONFERIR_PRECO = 45L

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
 * Resultado por hectare.
 *
 * Com o custo aberto por item da CONAB (planilha da série histórica), há um
 * valor só: quase todo o custo é por hectare (semente, adubo, defensivo,
 * máquinas, juros, fixos), e só o transporte externo, por saca, e a CESSR,
 * fração da receita, acompanham a produção. Antes o app dizia que a CONAB não
 * abria o custo por item e mostrava dois rateios extremos.
 *
 * Sem os itens (API antiga, levantamento sem planilha), volta aos dois
 * rateios: o custo variável tratado como fixo por hectare ou como proporcional
 * à produção. Entre os dois o SINAL se inverte quando a produtividade supera a
 * de referência e a margem é estreita, e a tela mostra a faixa.
 *
 * Quando o produtor informa o próprio custo não há o que repartir: o número é
 * dele, e a função devolve só ele.
 */
/**
 * Sacas por hectare com uma casa, como o campo da Viabilidade mostra e usa na
 * conta. O Histórico projeta com o mesmo número: com 3.297 kg/ha, a Viabilidade
 * contava 55,0 sc e o cartão do ano, 54,95, e o mesmo ano saía R$ 7/ha
 * diferente nas duas telas.
 */
internal fun sacasDoCampo(sacas: Double): Double =
    String.format(java.util.Locale.US, "%.1f", sacas).toDouble()

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
    val area = kpis.custo_area_ha
    val transporte = kpis.custo_transporte_saca
    val taxa = kpis.taxa_cessr
    if (area != null && transporte != null && taxa != null) {
        val custo = area + (transporte + taxa * preco) * sacasPorHectare
        return Resultado(receita - custo, null, false)
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

/**
 * Sacas por hectare que cobrem o custo. Com o custo aberto por item, o frete e a
 * CESSR crescem com cada saca, e a conta resolve área / (preço líquido por saca);
 * sem os itens, ou com o custo do produtor, custo / preço. Nulo sem preço.
 */
internal fun pontoDeEquilibrio(preco: Double, custoDoProdutor: Double?, kpis: FinancaResponse): Double? {
    if (preco <= 0) return null
    if (custoDoProdutor != null) return custoDoProdutor / preco
    val area = kpis.custo_area_ha
    val transporte = kpis.custo_transporte_saca
    val taxa = kpis.taxa_cessr
    if (area != null && transporte != null && taxa != null) {
        val liquido = preco * (1 - taxa) - transporte
        return if (liquido > 0) area / liquido else null
    }
    return kpis.custo_ha / preco
}

// O valor que o produtor digita é dinheiro, e dinheiro não cabe em float de
// 32 bits: 135,15 vira 135.14999389648438 na volta, porque não existe em
// binário de 32 bits. Guardado assim, o campo devolvia ao produtor um número
// que ele não digitou. Vai em Double, pelos bits, que é o jeito de pôr um
// Double em SharedPreferences — ela só conhece Long.
internal fun SharedPreferences.valorDoProdutor(chave: String): Double? {
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

internal fun SharedPreferences.informadoEm(chave: String): Long =
    getLong(chave + "_em", 0L)

internal fun SharedPreferences.guardarDoProdutor(chave: String, valor: Double, quando: Long) {
    edit().putLong(chave, valor.toRawBits()).putLong(chave + "_em", quando).apply()
}

internal fun SharedPreferences.esquecerDoProdutor(vararg chaves: String) {
    val editor = edit()
    for (chave in chaves) {
        editor.remove(chave)
        editor.remove(chave + "_em")
    }
    editor.apply()
}

@Composable
fun ResumoFinanceiroCard(
    projecao: PrevisaoHistorico,
    kpis: FinancaResponse,
    paraHoje: EstimativaPara? = null,
    pracas: List<PracaPara> = emptyList(),
    municipio: String? = null,
    sedes: Map<String, LugarTempo> = SEDES_MUNICIPAIS
) {
    // A cotação do dia na praça do estado mais perto do município; sem ela, no
    // Pará, a média do Pará estimada com Chicago e a base do mês.
    val praca = remember(pracas, municipio, sedes) { pracaParaUsar(municipio, pracas, sedes = sedes) }
    val precoHoje: Double? = praca?.valor ?: paraHoje?.estimado_brl_saca
    val rotuloHoje: String = praca?.let { "${it.praca}, ${dataCurta(it.data)}" } ?: "Pará, estimado agora"
    // O padrão do preço é a cotação do dia na praça (a mesma do Histórico e da
    // Estimativa no campo); o levantamento da CONAB, só quando não há praça em dia.
    val precoPadrao: Double = praca?.valor ?: kpis.soja_preco_saca
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
    // Com a chave, o campo passa ao preço da praça quando ele chega da rede
    // (o do produtor, se houver, continua valendo).
    var customPreco by remember(precoPadrao) {
        mutableStateOf(String.format(PT_BR, "%.2f", prefs.valorDoProdutor(PREF_PRECO) ?: precoPadrao))
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
            val preco = customPreco.replace(',', '.').toDoubleOrNull() ?: precoPadrao
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
                // Preço em dia (do produtor ou da praça): o que envelhece é o
                // custo do levantamento, a menos que o produtor informe o dele.
                (temPreco || praca != null) && !temCusto -> kpis.defasagem_meses?.let { m ->
                    if (m >= 5) "Custo padrão da CONAB de $m meses atrás: informe o seu para a conta ficar certa." else null
                } ?: kpis.aviso_custo
                temPreco || praca != null -> null
                // Preço padrão da CONAB: a idade dele e, ao lado, o preço de hoje.
                // O texto longo do servidor fica só quando ele não manda a idade.
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
                val usandoEste = kotlin.math.abs(preco - pa) < 0.005
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
            val daConab = listOfNotNull(if (temPreco || praca != null) null else "preço", if (temCusto) null else "custo")
            val padrao = listOfNotNull(
                if (temProd) null else "produtividade do modelo",
                if (!temPreco && praca != null) "preço de ${praca.praca} em ${dataCurta(praca.data)} (Agrolink)" else null,
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
                else "Padrão: ${juntaComE(padrao)}." + (if (seus.isEmpty()) " Toque num campo para usar os seus números." else "")
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
                        customPreco = String.format(PT_BR, "%.2f", precoPadrao)
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
            // O custo que entrou na conta: com o custo aberto por item, o da CONAB
            // cresce com o frete e a CESSR das sacas a mais, e a linha de custo, o
            // retorno e o equilíbrio têm de usar o mesmo número do lucro.
            val custoUsado = receita - lucro
            val roi = if (custoUsado > 0) (lucro / custoUsado) * 100 else 0.0
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
                    // O campo traz o custo da CONAB na produtividade dela (48 sc/ha); aqui vai o
                    // custo para a produtividade da conta, com frete e CESSR das sacas.
                    Text(text = if (temCusto) "Seu custo operacional"
                                else "Custo para ${String.format(PT_BR, "%.0f", scHa)} sc/ha",
                         fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(text = "${reaisInteiros(custoUsado)}/ha", fontSize = 18.sp,
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
            pontoDeEquilibrio(preco, if (temCusto) custo else null, kpis)?.let { eq ->
                Text(text = "Ponto de equilíbrio: ${kotlin.math.ceil(eq).toInt()} sc/ha para cobrir o custo",
                     fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
