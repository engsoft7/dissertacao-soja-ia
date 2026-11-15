package com.agrointeligencia.app

import java.time.LocalDate
import java.util.Locale

// AS CONTAS DO CADERNO DA SAFRA
//
// O produtor anota, só no celular, o que fez na safra: plantio, insumos,
// operações, colheita e vendas (Caderno.kt). Daqui saem o resumo (custo por
// hectare e por saca, produtividade colhida, preço médio de venda, resultado),
// a conferência das datas de plantio contra o calendário da portaria e o ZARC
// (PlantioCalculo.kt) e a planilha para exportar. Testadas em CadernoCalculoTest.

enum class TipoRegistro { PLANTIO, INSUMO, OPERACAO, COLHEITA, VENDA }

/**
 * Um lançamento. Os campos usados dependem do tipo:
 * - PLANTIO: descrição (cultivar) e área em hectares;
 * - INSUMO: descrição (produto), quantidade e unidade, e o custo total em R$;
 * - OPERACAO: descrição (o que foi feito) e o custo total em R$;
 * - COLHEITA: área colhida em hectares e sacas colhidas (quantidade);
 * - VENDA: sacas vendidas (quantidade), preço por saca (valor) e comprador.
 * A safra é o ano da colheita, como no IBGE e no resto do app (Safra.kt).
 */
data class RegistroCaderno(
    val id: Long,
    val safra: Int,
    val tipo: TipoRegistro,
    val data: String,
    val descricao: String = "",
    val area: Double? = null,
    val quantidade: Double? = null,
    val unidade: String? = null,
    val valor: Double? = null,
)

data class ResumoCaderno(
    val areaPlantada: Double,
    val custoTotal: Double,
    val custoPorHa: Double?,
    val areaColhida: Double,
    val sacasColhidas: Double,
    /** Sacas por hectare colhido. */
    val produtividade: Double?,
    val custoPorSaca: Double?,
    val sacasVendidas: Double,
    val receita: Double,
    val precoMedio: Double?,
    /** Colhido e ainda não vendido (nunca negativo). */
    val estoque: Double,
    /** Receita das vendas menos os custos lançados; null sem custo nem venda. */
    val resultado: Double?,
)

private fun List<RegistroCaderno>.soma(tipo: TipoRegistro, campo: (RegistroCaderno) -> Double?): Double =
    filter { it.tipo == tipo }.sumOf { campo(it) ?: 0.0 }

fun resumoDoCaderno(registros: List<RegistroCaderno>): ResumoCaderno {
    val area = registros.soma(TipoRegistro.PLANTIO) { it.area }
    val custo = registros.soma(TipoRegistro.INSUMO) { it.valor } + registros.soma(TipoRegistro.OPERACAO) { it.valor }
    val areaColhida = registros.soma(TipoRegistro.COLHEITA) { it.area }
    val sacas = registros.soma(TipoRegistro.COLHEITA) { it.quantidade }
    val vendidas = registros.soma(TipoRegistro.VENDA) { it.quantidade }
    val receita = registros.filter { it.tipo == TipoRegistro.VENDA }.sumOf { (it.quantidade ?: 0.0) * (it.valor ?: 0.0) }
    val temCustoOuVenda = registros.any {
        (it.tipo == TipoRegistro.INSUMO || it.tipo == TipoRegistro.OPERACAO) && it.valor != null ||
            it.tipo == TipoRegistro.VENDA && it.quantidade != null && it.valor != null
    }
    return ResumoCaderno(
        areaPlantada = area,
        custoTotal = custo,
        custoPorHa = custo.takeIf { area > 0.0 && custo > 0.0 }?.div(area),
        areaColhida = areaColhida,
        sacasColhidas = sacas,
        produtividade = sacas.takeIf { areaColhida > 0.0 }?.div(areaColhida),
        custoPorSaca = custo.takeIf { sacas > 0.0 && custo > 0.0 }?.div(sacas),
        sacasVendidas = vendidas,
        receita = receita,
        precoMedio = receita.takeIf { vendidas > 0.0 }?.div(vendidas),
        estoque = (sacas - vendidas).coerceAtLeast(0.0),
        resultado = if (temCustoOuVenda) receita - custo else null,
    )
}

/** As safras com lançamento e a safra em curso, da mais nova para a mais antiga. */
fun safrasDoCaderno(registros: List<RegistroCaderno>, hoje: LocalDate = LocalDate.now()): List<Int> =
    (registros.map { it.safra } + anoDaSafraEmCurso(hoje)).distinct().sortedDescending()

/** O plantio contra a portaria e o ZARC; os dois nulos quando não há dados para a data. */
data class ConferenciaPlantio(val situacao: SituacaoCalendario?, val risco: Int?)

/**
 * Situação da data de plantio no calendário de semeadura e o risco do ZARC
 * nela, para o grupo e o solo escolhidos na janela de plantio. O ZARC só vale
 * para a safra dele (de julho a junho); fora dela, o risco fica nulo.
 */
fun conferePlantio(data: LocalDate, calendario: CalendarioPlantio?, riscos: String?, safraIni: Int?): ConferenciaPlantio {
    val noCalendario = periodoDeSemeadura(calendario)?.let { situacaoNoDia(calendario, data) }
    val risco = if (riscos != null && safraIni != null && riscos.length == 36 &&
        !data.isBefore(LocalDate.of(safraIni, 7, 1)) && !data.isAfter(LocalDate.of(safraIni + 1, 6, 30))
    ) riscoNoDia(riscos, safraIni, data) else null
    return ConferenciaPlantio(noCalendario, risco)
}

private fun numeroCsv(v: Double?, decimal: Char): String =
    v?.let { String.format(Locale.US, "%.2f", it).trimEnd('0').trimEnd('.').replace('.', decimal) } ?: ""

private fun textoCsv(s: String?, separador: Char): String {
    val t = s.orEmpty()
    return if (t.any { it == separador || it == '"' || it == '\n' }) "\"" + t.replace("\"", "\"\"") + "\"" else t
}

/**
 * A planilha do caderno. O padrão é o do Excel e do LibreOffice em português:
 * ponto e vírgula entre colunas e vírgula nos decimais; em inglês, vírgula e
 * ponto (Caderno.kt escolhe pelo idioma do app).
 */
fun cadernoEmCsv(registros: List<RegistroCaderno>, separador: Char = ';', decimal: Char = ','): String = buildString {
    append(listOf("safra", "tipo", "data", "descricao", "area_ha", "quantidade", "unidade", "valor_rs")
               .joinToString(separador.toString())).append('\n')
    registros.sortedWith(compareBy({ it.safra }, { it.data }, { it.id })).forEach { r ->
        append(listOf(
            r.safra.toString(), r.tipo.name.lowercase(), r.data, textoCsv(r.descricao, separador),
            numeroCsv(r.area, decimal), numeroCsv(r.quantidade, decimal), textoCsv(r.unidade, separador),
            numeroCsv(r.valor, decimal),
        ).joinToString(separador.toString()))
        append('\n')
    }
}

/** "14/11/2026" ou "2026-11-14" para a data; null se não for uma data válida. */
fun dataDigitada(texto: String): LocalDate? {
    val t = texto.trim()
    Regex("""(\d{1,2})/(\d{1,2})/(\d{4})""").matchEntire(t)?.let { m ->
        val (d, mes, a) = m.destructured
        return runCatching { LocalDate.of(a.toInt(), mes.toInt(), d.toInt()) }.getOrNull()
    }
    return runCatching { LocalDate.parse(t) }.getOrNull()
}

private val MILHAR_EM_INGLES = Regex("""\d{1,3}(,\d{3})+""")

/**
 * Número digitado, no separador decimal do idioma ([decimal]). Em português,
 * "1.234,5" ou "12.5" (sem vírgula, o ponto é decimal); em inglês, "1,234.5",
 * "12.5" ou "12,5" (a vírgula só é de milhar quando separa grupos de três,
 * como em "1,234"). Null se vazio ou inválido; negativo não vale.
 */
fun numeroDigitado(texto: String, decimal: Char = Formatos.separadorDecimal): Double? {
    val t = texto.trim()
    if (t.isEmpty()) return null
    val n = when {
        decimal == '.' && ('.' in t || MILHAR_EM_INGLES.matches(t)) -> t.replace(",", "")
        ',' in t -> t.replace(".", "").replace(',', '.')
        else -> t
    }
    return n.toDoubleOrNull()?.takeIf { it >= 0.0 && it.isFinite() }
}
