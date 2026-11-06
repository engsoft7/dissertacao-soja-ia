package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate

/** Qual safra o app mostra, e como diz o que ainda não tem dado do IBGE. */
class SafraTest {

    // Como a API devolve hoje: IBGE até 2025 e projeções para 2026, 2027 e 2028.
    private val historico = (2020..2028).map { ano ->
        PrevisaoHistorico(ano, 3000.0 + ano - 2020, if (ano <= 2025) 2900.0 else 0.0, 300.0)
    }

    @Test
    fun safraEmCursoPeloCalendario() {
        assertEquals(2027, anoDaSafraEmCurso(LocalDate.of(2026, 11, 6)))
        assertEquals(2027, anoDaSafraEmCurso(LocalDate.of(2026, 8, 1)))
        assertEquals(2026, anoDaSafraEmCurso(LocalDate.of(2026, 7, 31)))
        assertEquals(2026, anoDaSafraEmCurso(LocalDate.of(2026, 3, 15)))
    }

    @Test
    fun resumoMostraASafraEmCursoENaoAMaisDistante() {
        assertEquals(2027, projecaoDaSafra(historico, LocalDate.of(2026, 11, 6))?.ano)
        assertEquals(2026, projecaoDaSafra(historico, LocalDate.of(2026, 5, 1))?.ano)
        // Base adiantada ou atrasada: a projeção mais próxima da safra em curso.
        assertEquals(2028, projecaoDaSafra(historico, LocalDate.of(2031, 1, 1))?.ano)
        assertEquals(2026, projecaoDaSafra(historico, LocalDate.of(2024, 1, 1))?.ano)
    }

    @Test
    fun simuladorPartiDoAnoSeguinteAoUltimoDivulgado() {
        assertEquals(2026, projecaoDoSimulador(historico)?.ano)
        assertEquals(2025, ultimoObservado(historico)?.ano)
        assertNull(projecaoDaSafra(historico.filter { it.rendimento_real > 0 }))
    }

    @Test
    fun anoSemDadoDoIbge() {
        val hoje = LocalDate.of(2026, 11, 6)
        assertEquals("IBGE ainda não divulgou", situacaoSemDado(2026, hoje))
        assertEquals("a colher", situacaoSemDado(2027, hoje))
        assertEquals("a colher", situacaoSemDado(2028, hoje))
    }

    @Test
    fun reaisComSinalAntesDoSimbolo() {
        assertEquals("−R$ 86", reaisInteiros(-86.4))
        assertEquals("R$ 5.811", reaisInteiros(5811.2))
        assertEquals("R$ 0", reaisInteiros(-0.3))
    }

    @Test
    fun juntaPartesComE() {
        assertEquals("o preço em 05/11/2026", juntaComE(listOf("o preço em 05/11/2026")))
        assertEquals("a, b e c", juntaComE(listOf("a", "b", "c")))
        assertEquals("", juntaComE(emptyList()))
    }
}
