package com.agrointeligencia.app

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Assessment
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Grass
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import com.google.gson.Gson
import java.io.File
import java.time.LocalDate
import java.time.format.DateTimeFormatter

// O CADERNO DA SAFRA
//
// O produtor anota o que fez na safra: plantio, insumos, operações, colheita e
// vendas. Os lançamentos ficam num arquivo na pasta privada do app (sem backup,
// como o resto: AndroidManifest.xml) e só saem do celular se ele exportar a
// planilha. As contas estão em CadernoCalculo.kt.

private const val ARQUIVO_CADERNO = "caderno_safra.json"
private val DATA_BR: DateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy")

/** Os lançamentos guardados; lista vazia sem arquivo ou com o arquivo ilegível. */
fun leCaderno(context: Context): List<RegistroCaderno> = runCatching {
    val f = File(context.filesDir, ARQUIVO_CADERNO)
    if (!f.exists()) emptyList()
    else Gson().fromJson(f.readText(), Array<RegistroCaderno>::class.java).filterNotNull()
}.getOrDefault(emptyList())

/** Grava num arquivo temporário e troca de uma vez: uma queda no meio não corrompe o caderno. */
fun gravaCaderno(context: Context, registros: List<RegistroCaderno>) {
    val tmp = File(context.filesDir, "$ARQUIVO_CADERNO.tmp")
    tmp.writeText(Gson().toJson(registros))
    tmp.renameTo(File(context.filesDir, ARQUIVO_CADERNO))
}

class EstadoCaderno(private val context: Context) {
    var registros by mutableStateOf(leCaderno(context))
        private set

    fun adiciona(r: RegistroCaderno) {
        registros = registros + r
        gravaCaderno(context, registros)
    }

    fun remove(id: Long) {
        registros = registros.filterNot { it.id == id }
        gravaCaderno(context, registros)
    }
}

/** 2027 -> "2026/27": a safra pelo ano da colheita, como no resto do app. */
fun rotuloDaSafra(safra: Int): String = "${safra - 1}/${(safra % 100).toString().padStart(2, '0')}"

private fun numeroCaderno(v: Double, casas: Int = 1): String =
    String.format(PT_BR, "%,.${casas}f", v).let { if (casas > 0) it.trimEnd('0').trimEnd(',') else it }

private fun dataBr(iso: String): String = runCatching { LocalDate.parse(iso).format(DATA_BR) }.getOrDefault(iso)

@Composable
fun CadernoResumoCard(estado: EstadoCaderno, aoAbrir: () -> Unit) {
    val safra = anoDaSafraEmCurso()
    val daSafra = estado.registros.filter { it.safra == safra }
    val custo = resumoDoCaderno(daSafra).custoTotal
    Card(
        onClick = aoAbrir,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(16.dp)) {
            Icon(Icons.AutoMirrored.Filled.MenuBook, contentDescription = null, tint = MaterialTheme.colorScheme.primary,
                 modifier = Modifier.size(32.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.caderno_titulo_cartao, rotuloDaSafra(safra)), fontSize = 12.sp,
                     color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    if (daSafra.isEmpty()) stringResource(R.string.caderno_cartao_vazio)
                    else stringResource(R.string.caderno_cartao_resumo, daSafra.size, reais(custo)),
                    fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface
                )
            }
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = stringResource(R.string.caderno_abrir),
                 tint = MaterialTheme.colorScheme.primary)
        }
    }
}

/** A planilha de todas as safras no cache, pronta para o compartilhamento do Android. */
private fun exportaCaderno(context: Context, registros: List<RegistroCaderno>): Boolean {
    val pasta = File(context.cacheDir, "exportar").apply { mkdirs() }
    val arquivo = File(pasta, "caderno_safra.csv")
    // A marca de ordem de bytes faz o Excel abrir os acentos certos.
    arquivo.writeText("﻿" + cadernoEmCsv(registros))
    val uri = FileProvider.getUriForFile(context, context.packageName + ".fotos", arquivo)
    val envio = Intent(Intent.ACTION_SEND).apply {
        type = "text/csv"
        putExtra(Intent.EXTRA_STREAM, uri)
        putExtra(Intent.EXTRA_SUBJECT, context.getString(R.string.caderno_exportar_assunto))
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    return try {
        context.startActivity(Intent.createChooser(envio, context.getString(R.string.caderno_exportar))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    } catch (_: ActivityNotFoundException) {
        false
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CadernoTela(
    estado: EstadoCaderno,
    plantio: EstadoPlantio,
    estimativaScHa: Double?,
    municipio: String?,
    aoVoltar: () -> Unit,
    hoje: LocalDate = LocalDate.now(),
) {
    val context = LocalContext.current
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    var safra by rememberSaveable { mutableIntStateOf(anoDaSafraEmCurso(hoje)) }
    var aviso by remember { mutableStateOf<String?>(null) }
    val semExportar = stringResource(R.string.caderno_exportar_sem_app)
    val daSafra = estado.registros.filter { it.safra == safra }.sortedWith(compareBy({ it.data }, { it.id }))

    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = aoVoltar) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.caderno_voltar))
            }
            Text(stringResource(R.string.caderno_titulo), fontWeight = FontWeight.Bold, fontSize = 20.sp,
                 color = MaterialTheme.colorScheme.onBackground, modifier = Modifier.weight(1f))
            IconButton(onClick = { if (!exportaCaderno(context, estado.registros)) aviso = semExportar },
                       enabled = estado.registros.isNotEmpty()) {
                Icon(Icons.Filled.Share, contentDescription = stringResource(R.string.caderno_exportar))
            }
        }
        Text(stringResource(R.string.caderno_privacidade), fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
        aviso?.let { Text(it, fontSize = 12.sp, color = MaterialTheme.colorScheme.error) }

        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            safrasDoCaderno(estado.registros, hoje).forEach { s ->
                FilterChip(selected = s == safra, onClick = { safra = s },
                           label = { Text(stringResource(R.string.caderno_safra, rotuloDaSafra(s))) },
                           modifier = Modifier.heightIn(min = 48.dp))
            }
        }

        CartaoComTitulo(stringResource(R.string.caderno_resumo), Icons.Filled.Assessment) {
            ResumoDaSafra(resumoDoCaderno(daSafra), estimativaScHa.takeIf { safra == anoDaSafraEmCurso(hoje) }, municipio)
        }

        val plantios = daSafra.filter { it.tipo == TipoRegistro.PLANTIO }
        if (plantios.isNotEmpty()) {
            CartaoComTitulo(stringResource(R.string.caderno_datas_plantio), Icons.Filled.Grass) {
                ConferenciaDosPlantios(plantios, plantio)
            }
        }

        CartaoComTitulo(stringResource(R.string.caderno_novo), Icons.Filled.Add) {
            NovoLancamento(safra, hoje) { estado.adiciona(it) }
        }

        CartaoComTitulo(stringResource(R.string.caderno_lancamentos), Icons.AutoMirrored.Filled.MenuBook) {
            if (daSafra.isEmpty()) {
                Text(stringResource(R.string.caderno_sem_lancamentos), fontSize = 13.sp, color = secundaria)
            }
            daSafra.forEachIndexed { i, r ->
                if (i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                LinhaDoLancamento(r) { estado.remove(r.id) }
            }
        }
    }
}

@Composable
private fun ResumoDaSafra(s: ResumoCaderno, estimativaScHa: Double?, municipio: String?) {
    val texto = MaterialTheme.colorScheme.onSurface
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    if (s.areaPlantada <= 0.0 && s.custoTotal <= 0.0 && s.sacasColhidas <= 0.0 && s.sacasVendidas <= 0.0) {
        Text(stringResource(R.string.caderno_resumo_vazio), fontSize = 13.sp, color = secundaria, lineHeight = 18.sp)
        return
    }
    if (s.areaPlantada > 0.0) {
        Text(stringResource(R.string.caderno_area_plantada, numeroCaderno(s.areaPlantada, 2)), fontSize = 14.sp, color = texto)
    }
    if (s.custoTotal > 0.0) {
        val partes = listOfNotNull(
            s.custoPorHa?.let { stringResource(R.string.caderno_por_ha, reais(it)) },
            s.custoPorSaca?.let { stringResource(R.string.caderno_por_saca, reais(it)) },
        )
        Text(stringResource(R.string.caderno_custos, reais(s.custoTotal)) +
                 (if (partes.isEmpty()) "" else " (" + partes.joinToString("; ") + ")"),
             fontSize = 14.sp, color = texto)
    }
    if (s.sacasColhidas > 0.0) {
        Text(s.produtividade?.let {
            stringResource(R.string.caderno_colhido_produtividade, milhar(s.sacasColhidas), numeroCaderno(s.areaColhida, 2),
                           numeroCaderno(it, 1))
        } ?: stringResource(R.string.caderno_colhido, milhar(s.sacasColhidas)), fontSize = 14.sp, color = texto)
        if (s.produtividade != null && estimativaScHa != null && municipio != null) {
            Text(stringResource(R.string.caderno_comparacao, municipio, numeroCaderno(estimativaScHa, 1)),
                 fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
        }
    }
    if (s.sacasVendidas > 0.0) {
        Text(stringResource(R.string.caderno_vendido, milhar(s.sacasVendidas), reais(s.precoMedio ?: 0.0), reais(s.receita)),
             fontSize = 14.sp, color = texto)
    }
    if (s.estoque > 0.0) {
        Text(stringResource(R.string.caderno_estoque, milhar(s.estoque)), fontSize = 14.sp, color = texto)
    }
    s.resultado?.let { r ->
        Text(stringResource(R.string.caderno_resultado, (if (r < 0) "−" else "") + reais(kotlin.math.abs(r))),
             fontSize = 15.sp, fontWeight = FontWeight.Bold,
             color = if (r < 0) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
        Text(stringResource(R.string.caderno_resultado_nota), fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
    }
}

@Composable
private fun ConferenciaDosPlantios(plantios: List<RegistroCaderno>, plantio: EstadoPlantio) {
    val d = plantio.dados
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    if (d == null) {
        Text(stringResource(R.string.caderno_sem_janela), fontSize = 13.sp, color = secundaria, lineHeight = 18.sp)
        return
    }
    val z = d.zarc
    val grupo = z?.ciclos?.firstOrNull { it.codigo == plantio.ciclo }?.nome.orEmpty()
    val solo = z?.solos?.firstOrNull { it.codigo == plantio.solo }?.nome.orEmpty()
    plantios.forEach { r ->
        val data = runCatching { LocalDate.parse(r.data) }.getOrNull() ?: return@forEach
        val c = conferePlantio(data, d.calendario, plantio.riscos(), anoInicialDaSafra(d.safra))
        val partes = mutableListOf<Pair<String, Color?>>()
        when (c.situacao) {
            SituacaoCalendario.SEMEADURA -> partes += stringResource(R.string.caderno_dentro_calendario) to null
            SituacaoCalendario.VAZIO_SANITARIO -> partes += stringResource(R.string.caderno_no_vazio) to MaterialTheme.colorScheme.error
            SituacaoCalendario.FORA_DO_CALENDARIO -> partes += stringResource(R.string.caderno_fora_calendario) to MaterialTheme.colorScheme.error
            null -> {}
        }
        when (val risco = c.risco) {
            null -> {}
            0 -> partes += stringResource(R.string.caderno_fora_zarc, grupo, solo) to Color(0xFFEF6C00)
            else -> partes += stringResource(R.string.caderno_risco_zarc, risco, grupo, solo) to null
        }
        Column(Modifier.padding(vertical = 4.dp)) {
            Text(listOf(dataBr(r.data), r.descricao.takeIf { it.isNotBlank() },
                        r.area?.let { numeroCaderno(it, 2) + " ha" }).filterNotNull().joinToString(" · "),
                 fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
            if (partes.isEmpty()) {
                Text(stringResource(R.string.caderno_sem_conferencia), fontSize = 12.sp, color = secundaria)
            }
            partes.forEach { (t, cor) ->
                Text(t, fontSize = 12.sp, color = cor ?: MaterialTheme.colorScheme.onSurface, lineHeight = 16.sp)
            }
        }
    }
}

private val TIPOS = listOf(
    TipoRegistro.PLANTIO to R.string.caderno_tipo_plantio,
    TipoRegistro.INSUMO to R.string.caderno_tipo_insumo,
    TipoRegistro.OPERACAO to R.string.caderno_tipo_operacao,
    TipoRegistro.COLHEITA to R.string.caderno_tipo_colheita,
    TipoRegistro.VENDA to R.string.caderno_tipo_venda,
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun NovoLancamento(safra: Int, hoje: LocalDate, aoGuardar: (RegistroCaderno) -> Unit) {
    var tipo by rememberSaveable { mutableStateOf(TipoRegistro.PLANTIO) }
    var data by rememberSaveable { mutableStateOf(hoje.format(DATA_BR)) }
    var descricao by rememberSaveable { mutableStateOf("") }
    var area by rememberSaveable { mutableStateOf("") }
    var quantidade by rememberSaveable { mutableStateOf("") }
    var unidade by rememberSaveable { mutableStateOf("") }
    var valor by rememberSaveable { mutableStateOf("") }

    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        TIPOS.forEach { (t, rotulo) ->
            FilterChip(selected = t == tipo, onClick = { tipo = t }, label = { Text(stringResource(rotulo)) },
                       modifier = Modifier.heightIn(min = 48.dp))
        }
    }
    val dataLida = dataDigitada(data)
    Campo(data, { data = it }, stringResource(R.string.caderno_data), erro = dataLida == null)
    when (tipo) {
        TipoRegistro.PLANTIO -> {
            Campo(descricao, { descricao = it }, stringResource(R.string.caderno_cultivar))
            Campo(area, { area = it }, stringResource(R.string.caderno_area_ha), numero = true)
        }
        TipoRegistro.INSUMO -> {
            Campo(descricao, { descricao = it }, stringResource(R.string.caderno_produto))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Campo(quantidade, { quantidade = it }, stringResource(R.string.caderno_quantidade), numero = true,
                      modifier = Modifier.weight(1f))
                Campo(unidade, { unidade = it }, stringResource(R.string.caderno_unidade), modifier = Modifier.weight(1f))
            }
            Campo(valor, { valor = it }, stringResource(R.string.caderno_custo_total), numero = true)
        }
        TipoRegistro.OPERACAO -> {
            Campo(descricao, { descricao = it }, stringResource(R.string.caderno_operacao))
            Campo(valor, { valor = it }, stringResource(R.string.caderno_custo_total), numero = true)
        }
        TipoRegistro.COLHEITA -> {
            Campo(area, { area = it }, stringResource(R.string.caderno_area_colhida), numero = true)
            Campo(quantidade, { quantidade = it }, stringResource(R.string.caderno_sacas_colhidas), numero = true)
        }
        TipoRegistro.VENDA -> {
            Campo(quantidade, { quantidade = it }, stringResource(R.string.caderno_sacas_vendidas), numero = true)
            Campo(valor, { valor = it }, stringResource(R.string.caderno_preco_saca), numero = true)
            Campo(descricao, { descricao = it }, stringResource(R.string.caderno_comprador))
        }
    }
    val a = numeroDigitado(area)
    val q = numeroDigitado(quantidade)
    val v = numeroDigitado(valor)
    val valido = dataLida != null && when (tipo) {
        TipoRegistro.PLANTIO -> a != null && a > 0.0
        TipoRegistro.INSUMO -> descricao.isNotBlank() && v != null
        TipoRegistro.OPERACAO -> descricao.isNotBlank()
        TipoRegistro.COLHEITA -> q != null && q > 0.0
        TipoRegistro.VENDA -> q != null && q > 0.0 && v != null && v > 0.0
    }
    Button(
        onClick = {
            aoGuardar(RegistroCaderno(
                id = System.currentTimeMillis(), safra = safra, tipo = tipo, data = dataLida!!.toString(),
                descricao = descricao.trim(),
                area = a.takeIf { tipo == TipoRegistro.PLANTIO || tipo == TipoRegistro.COLHEITA },
                quantidade = q.takeIf { tipo == TipoRegistro.INSUMO || tipo == TipoRegistro.COLHEITA || tipo == TipoRegistro.VENDA },
                unidade = unidade.trim().takeIf { tipo == TipoRegistro.INSUMO && it.isNotEmpty() },
                valor = v.takeIf { tipo == TipoRegistro.INSUMO || tipo == TipoRegistro.OPERACAO || tipo == TipoRegistro.VENDA },
            ))
            descricao = ""; area = ""; quantidade = ""; unidade = ""; valor = ""
        },
        enabled = valido,
        modifier = Modifier.heightIn(min = 48.dp)
    ) { Text(stringResource(R.string.caderno_guardar)) }
}

@Composable
private fun Campo(
    valor: String,
    aoMudar: (String) -> Unit,
    rotulo: String,
    numero: Boolean = false,
    erro: Boolean = false,
    modifier: Modifier = Modifier.fillMaxWidth(),
) {
    OutlinedTextField(
        value = valor,
        onValueChange = aoMudar,
        label = { Text(rotulo) },
        singleLine = true,
        isError = erro || (numero && valor.isNotBlank() && numeroDigitado(valor) == null),
        keyboardOptions = if (numero) KeyboardOptions(keyboardType = KeyboardType.Decimal) else KeyboardOptions.Default,
        modifier = modifier
    )
}

@Composable
private fun LinhaDoLancamento(r: RegistroCaderno, aoApagar: () -> Unit) {
    var confirmar by remember { mutableStateOf(false) }
    val rotulo = stringResource(TIPOS.first { it.first == r.tipo }.second)
    val detalhe = when (r.tipo) {
        TipoRegistro.PLANTIO -> listOfNotNull(r.descricao.takeIf { it.isNotBlank() }, r.area?.let { numeroCaderno(it, 2) + " ha" })
        TipoRegistro.INSUMO -> listOfNotNull(
            r.descricao.takeIf { it.isNotBlank() },
            r.quantidade?.let { numeroCaderno(it, 2) + (r.unidade?.let { u -> " $u" } ?: "") },
            r.valor?.let { "R$ " + reais(it) })
        TipoRegistro.OPERACAO -> listOfNotNull(r.descricao.takeIf { it.isNotBlank() }, r.valor?.let { "R$ " + reais(it) })
        TipoRegistro.COLHEITA -> listOfNotNull(
            r.quantidade?.let { stringResource(R.string.caderno_sacas, milhar(it)) },
            r.area?.let { numeroCaderno(it, 2) + " ha" })
        TipoRegistro.VENDA -> listOfNotNull(
            r.quantidade?.let { stringResource(R.string.caderno_sacas, milhar(it)) },
            r.valor?.let { stringResource(R.string.caderno_a_preco, reais(it)) },
            r.descricao.takeIf { it.isNotBlank() })
    }.joinToString(" · ")
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Column(Modifier.weight(1f)) {
            Text("$rotulo · ${dataBr(r.data)}", fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                 color = MaterialTheme.colorScheme.onSurface)
            if (detalhe.isNotEmpty()) {
                Text(detalhe, fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 17.sp)
            }
        }
        IconButton(onClick = { confirmar = true }) {
            Icon(Icons.Filled.Delete, contentDescription = stringResource(R.string.caderno_apagar_rotulo, rotulo, dataBr(r.data)),
                 tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
    if (confirmar) {
        AlertDialog(
            onDismissRequest = { confirmar = false },
            title = { Text(stringResource(R.string.caderno_apagar_titulo)) },
            text = { Text("$rotulo · ${dataBr(r.data)}" + if (detalhe.isNotEmpty()) "\n$detalhe" else "") },
            confirmButton = { TextButton(onClick = { confirmar = false; aoApagar() }) { Text(stringResource(R.string.caderno_apagar)) } },
            dismissButton = { TextButton(onClick = { confirmar = false }) { Text(stringResource(R.string.caderno_cancelar)) } },
        )
    }
}
