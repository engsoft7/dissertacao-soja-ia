package com.agrointeligencia.app

import java.time.LocalDate
import java.time.YearMonth

// AS CONTAS DA JANELA DE PLANTIO
//
// A API manda, para o município, o calendário de semeadura e o vazio sanitário
// da Portaria SDA/MAPA nº 1.579/2026 e os riscos do ZARC por grupo de cultivar
// e classe de solo, um por decêndio (plantio.py). As contas ficam aqui, no
// celular: trocar o grupo ou o solo não depende de rede, e as funções são
// testadas sem Android (PlantioCalculoTest).

/** Uma janela do ZARC: decêndios seguidos com o mesmo risco. */
data class JanelaZarc(val inicio: LocalDate, val fim: LocalDate, val risco: Int)

/** Onde o dia cai no calendário da portaria. */
enum class SituacaoCalendario { VAZIO_SANITARIO, SEMEADURA, FORA_DO_CALENDARIO }

/** "2026/2027" -> 2026. */
fun anoInicialDaSafra(safra: String?): Int? = safra?.substringBefore("/")?.trim()?.toIntOrNull()

/**
 * Datas do decêndio [i] (1 a 36) na safra que começa em [safraIni]. De julho a
 * dezembro é o ano de início; de janeiro a junho, o seguinte. O terceiro
 * decêndio do mês vai do dia 21 ao último dia.
 */
fun decendio(i: Int, safraIni: Int): Pair<LocalDate, LocalDate> {
    require(i in 1..36) { "decêndio fora de 1 a 36: $i" }
    val mes = (i - 1) / 3 + 1
    val ano = if (mes >= 7) safraIni else safraIni + 1
    val parte = (i - 1) % 3
    val inicio = LocalDate.of(ano, mes, 1 + 10 * parte)
    val fim = if (parte == 2) YearMonth.of(ano, mes).atEndOfMonth() else inicio.plusDays(9)
    return inicio to fim
}

/** Risco de um caractere da sequência do ZARC: '2' é 20%, '3' é 30%, '4' é 40%, '0' não indicado. */
fun riscoDoCaractere(c: Char): Int = when (c) { '2' -> 20; '3' -> 30; '4' -> 40; else -> 0 }

/** As janelas indicadas, de julho a junho, juntando decêndios seguidos de mesmo risco. */
fun janelasZarc(riscos: String, safraIni: Int): List<JanelaZarc> {
    if (riscos.length != 36) return emptyList()
    val ordem = (19..36) + (1..18)
    val saida = mutableListOf<JanelaZarc>()
    var anterior = -1
    for ((pos, i) in ordem.withIndex()) {
        val risco = riscoDoCaractere(riscos[i - 1])
        val (ini, fim) = decendio(i, safraIni)
        val ultima = saida.lastOrNull()
        if (risco > 0 && ultima != null && ultima.risco == risco && anterior == pos - 1) {
            saida[saida.lastIndex] = ultima.copy(fim = fim)
            anterior = pos
        } else if (risco > 0) {
            saida += JanelaZarc(ini, fim, risco)
            anterior = pos
        }
    }
    return saida
}

/** O risco do ZARC no [dia]; 0 quando o decêndio não é indicado ou o dia está fora da safra. */
fun riscoNoDia(riscos: String, safraIni: Int, dia: LocalDate): Int =
    janelasZarc(riscos, safraIni).firstOrNull { !dia.isBefore(it.inicio) && !dia.isAfter(it.fim) }?.risco ?: 0

/** A primeira janela que ainda não terminou no [dia], com risco até [riscoMaximo]. */
fun proximaJanelaZarc(janelas: List<JanelaZarc>, dia: LocalDate, riscoMaximo: Int = 40): JanelaZarc? =
    janelas.firstOrNull { it.risco <= riscoMaximo && !it.fim.isBefore(dia) }

private fun periodo(par: List<String>?): Pair<LocalDate, LocalDate>? =
    par?.takeIf { it.size == 2 }?.let { runCatching { LocalDate.parse(it[0]) to LocalDate.parse(it[1]) }.getOrNull() }

/** Início e fim da semeadura; null quando a resposta não traz as duas datas. */
fun periodoDeSemeadura(c: CalendarioPlantio?): Pair<LocalDate, LocalDate>? = periodo(c?.semeadura)

/** Início e fim do vazio sanitário. */
fun periodoDoVazio(c: CalendarioPlantio?): Pair<LocalDate, LocalDate>? = periodo(c?.vazio)

/** Em que parte do calendário o [dia] cai; null sem calendário. */
fun situacaoNoDia(c: CalendarioPlantio?, dia: LocalDate): SituacaoCalendario? {
    val semeadura = periodoDeSemeadura(c) ?: return null
    val vazio = periodoDoVazio(c)
    return when {
        vazio != null && !dia.isBefore(vazio.first) && !dia.isAfter(vazio.second) -> SituacaoCalendario.VAZIO_SANITARIO
        !dia.isBefore(semeadura.first) && !dia.isAfter(semeadura.second) -> SituacaoCalendario.SEMEADURA
        else -> SituacaoCalendario.FORA_DO_CALENDARIO
    }
}

/** A parte da janela do ZARC que cai dentro do calendário de semeadura. */
fun dentroDoCalendario(j: JanelaZarc, semeadura: Pair<LocalDate, LocalDate>?): JanelaZarc? {
    if (semeadura == null) return j
    val ini = maxOf(j.inicio, semeadura.first)
    val fim = minOf(j.fim, semeadura.second)
    return if (ini.isAfter(fim)) null else j.copy(inicio = ini, fim = fim)
}
