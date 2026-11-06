package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate

/** Qual cotação de praça do Pará o app oferece na Viabilidade. */
class PracasTest {

    private val hoje = LocalDate.of(2026, 11, 6)

    // Como a Agrolink publicava em 05/11/2026: Paragominas parada desde 05/10.
    private val pracas = listOf(
        PracaPara("Redenção", "PA", 148.5, "2026-11-05"),
        PracaPara("Barcarena", "PA", 148.5, "2026-11-05"),
        PracaPara("Paragominas", "PA", 133.12, "2026-10-05"),
    )

    @Test
    fun pracaParadaNaoEntra() {
        // Em Paragominas, a praça do município está parada: vai a mais perto em dia.
        assertEquals("Barcarena", pracaParaUsar("Paragominas", pracas, hoje)?.praca)
    }

    @Test
    fun aMaisPertoDoMunicipio() {
        assertEquals("Redenção", pracaParaUsar("Redenção", pracas, hoje)?.praca)
        assertEquals("Redenção", pracaParaUsar("Santana do Araguaia", pracas, hoje)?.praca)
        assertEquals("Barcarena", pracaParaUsar("Tomé-Açu", pracas, hoje)?.praca)
    }

    @Test
    fun semMunicipioAMaisRecente() {
        assertEquals("2026-11-05", pracaParaUsar(null, pracas, hoje)?.data)
    }

    @Test
    fun todasParadasNenhuma() {
        assertNull(pracaParaUsar("Paragominas", pracas, LocalDate.of(2026, 12, 1)))
        assertNull(pracaParaUsar("Paragominas", emptyList(), hoje))
    }

    @Test
    fun idadeEData() {
        assertEquals(1L, idadeEmDias("2026-11-05", hoje))
        assertNull(idadeEmDias("05/11/26", hoje))
        assertEquals("05/11", dataCurta("2026-11-05"))
    }
}
