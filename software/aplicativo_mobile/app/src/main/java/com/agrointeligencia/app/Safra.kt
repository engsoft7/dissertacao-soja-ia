package com.agrointeligencia.app

import java.time.LocalDate
import kotlin.math.abs

// ── qual safra o app mostra ───────────────────────────────────────────────
//
// A API devolve o histórico do IBGE e projeções para os três anos seguintes ao
// último divulgado (com a PAM de 2025, projeta 2026, 2027 e 2028). O Resumo
// mostrava a mais distante, 2028, como "rendimento esperado", enquanto o
// produtor plantava a de 2027 e o simulador partia de 2026. Aqui fica a regra:
// o Resumo, a Viabilidade e a Estimativa no campo mostram a safra em curso.

/**
 * Ano de colheita da safra em curso ou da próxima. O IBGE identifica a safra
 * pelo ano da colheita. No Pará a soja é plantada de outubro (sul do estado) a
 * fevereiro (nordeste) e colhida até julho: de agosto em diante, a colheita
 * seguinte já é a do ano que vem.
 */
fun anoDaSafraEmCurso(hoje: LocalDate = LocalDate.now()): Int =
    if (hoje.monthValue >= 8) hoje.year + 1 else hoje.year

/** A safra mais recente com produtividade divulgada pelo IBGE. */
fun ultimoObservado(historico: List<PrevisaoHistorico>): PrevisaoHistorico? =
    historico.filter { it.rendimento_real > 0 }.maxByOrNull { it.ano }

/** Projeções: os anos depois do último divulgado. */
private fun projecoes(historico: List<PrevisaoHistorico>): List<PrevisaoHistorico> {
    val ultimo = ultimoObservado(historico)?.ano ?: Int.MIN_VALUE
    return historico.filter { it.ano > ultimo && it.rendimento_predito > 0 }
}

/**
 * A projeção da safra em curso. Se a API não a tiver (base atrasada ou
 * adiantada), a mais próxima dela; no empate, a mais adiante.
 */
fun projecaoDaSafra(historico: List<PrevisaoHistorico>, hoje: LocalDate = LocalDate.now()): PrevisaoHistorico? {
    val alvo = anoDaSafraEmCurso(hoje)
    return projecoes(historico).minWithOrNull(compareBy({ abs(it.ano - alvo) }, { -it.ano }))
}

/** O que dizer de uma safra sem dado do IBGE (o texto, em strings.xml): ainda por colher, ou colhida e não divulgada. */
fun situacaoSemDado(ano: Int, hoje: LocalDate = LocalDate.now()): Int =
    if (ano >= anoDaSafraEmCurso(hoje)) R.string.safra_a_colher else R.string.safra_sem_ibge

/** "a", "a e b", "a, b e c"; [e] é a conjunção do idioma (conjuncao_e). */
fun juntaComE(partes: List<String>, e: String = "e"): String = when (partes.size) {
    0 -> ""
    1 -> partes[0]
    else -> partes.dropLast(1).joinToString(", ") + " " + e + " " + partes.last()
}
