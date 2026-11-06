package com.agrointeligencia.app

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

// ── cotação diária das praças do Pará ─────────────────────────────────────
//
// A Agrolink publica a cotação diária da soja em algumas praças do Pará
// (Barcarena, Redenção, Paragominas em nov/2026). É o número real do dia, e o
// app o oferece antes da estimativa feita com Chicago e a base do mês.

/** Onde fica cada praça, para escolher a mais perto do município. */
val COORDENADAS_PRACAS: Map<String, Pair<Double, Double>> =
    SEDES_MUNICIPAIS.mapValues { it.value.lat to it.value.lon } + mapOf(
        "Barcarena" to (-1.5058 to -48.6258),
        "Belém" to (-1.4558 to -48.5039),
        "Belem" to (-1.4558 to -48.5039),
        "Parauapebas" to (-6.0678 to -49.9037),
    )

/** Uma cotação com mais dias que isto é tratada como parada. */
const val DIAS_COTACAO_EM_DIA = 7L

/** Dias desde a atualização ("AAAA-MM-DD"); nulo se a data não for lida. */
fun idadeEmDias(data: String, hoje: LocalDate = LocalDate.now()): Long? =
    runCatching { ChronoUnit.DAYS.between(LocalDate.parse(data), hoje) }.getOrNull()

fun cotacaoEmDia(p: PracaPara, hoje: LocalDate = LocalDate.now()): Boolean =
    idadeEmDias(p.data, hoje)?.let { it in 0..DIAS_COTACAO_EM_DIA } == true

/**
 * A praça que o app oferece: entre as atualizadas na última semana, a mais perto
 * da sede do município; sem município conhecido, a mais recente. Nula quando
 * nenhuma está em dia.
 */
fun pracaParaUsar(municipio: String?, pracas: List<PracaPara>, hoje: LocalDate = LocalDate.now()): PracaPara? {
    val emDia = pracas.filter { cotacaoEmDia(it, hoje) }
    if (emDia.isEmpty()) return null
    val sede = municipio?.let { SEDES_MUNICIPAIS[it] } ?: return emDia.maxByOrNull { it.data }
    return emDia.minByOrNull { p ->
        COORDENADAS_PRACAS[p.praca]?.let { (lat, lon) -> distanciaKm(sede.lat, sede.lon, lat, lon) } ?: Double.MAX_VALUE
    }
}

/** "2026-11-05" -> "05/11". */
fun dataCurta(data: String): String =
    runCatching { LocalDate.parse(data).format(DateTimeFormatter.ofPattern("dd/MM")) }.getOrDefault(data)
