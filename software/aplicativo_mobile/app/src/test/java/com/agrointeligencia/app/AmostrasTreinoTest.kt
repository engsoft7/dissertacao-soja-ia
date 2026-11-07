package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** As marcas guardadas para treino precisam cair no pixel que o produtor tocou. */
class AmostrasTreinoTest {

    @Test
    fun marca_vai_para_o_pixel_da_imagem() {
        val px = pontosEmPixels(listOf(0.5f to 0.25f, 0.1f to 0.9f), largura = 2048, altura = 1536)
        assertEquals(listOf(listOf(1024, 384), listOf(204, 1382)), px)
    }

    @Test
    fun marca_na_borda_nao_sai_da_imagem() {
        val px = pontosEmPixels(listOf(1f to 1f, 0f to 0f), largura = 100, altura = 50)
        assertEquals(listOf(listOf(99, 49), listOf(0, 0)), px)
    }

    @Test
    fun colheitaEmKgPorHectare() {
        assertEquals(3600.0, colheitaKgHa(600.0, 10.0)!!, 1e-9)
        assertNull("sem área", colheitaKgHa(600.0, null))
        assertNull("sem colheita", colheitaKgHa(null, 10.0))
        assertNull("zero", colheitaKgHa(0.0, 10.0))
    }

    @Test
    fun talhaoLevaPontosEstimativaEColheita() {
        val ponto = PontoAmostra(plantas = 14, metrosDeLinha = 1.0, arrancadas = 5, vagens = 200,
                                 vagensDoContador = 196, conferido = true)
        val estado = EstadoCampo(listOf(ponto), ParametrosCampo(), areaHa = 10.0, talhao = "abc", colhidoSacas = 550.0)
        val r = registroDoTalhao(estado, "2027-03-01T10:00:00-03:00", "2.8.0", 1, false)!!
        assertEquals("abc", r.talhao)
        assertEquals(estimaLavoura(listOf(ponto), ParametrosCampo())!!.kgHa, r.estimativa_kg_ha!!, 1e-9)
        assertEquals(3300.0, r.colheita_kg_ha!!, 1e-9)
        assertEquals(196, r.pontos.single().vagensDoContador)
        assertNull("estado antigo, sem talhão", registroDoTalhao(estado.copy(talhao = null), "", "", 1, false))
        assertNull("talhão vazio", registroDoTalhao(EstadoCampo(talhao = "x"), "", "", 1, false))
    }

    @Test
    fun registroNovoDoMesmoTalhaoTrocaOAntigo() {
        val estado = EstadoCampo(listOf(PontoAmostra(14, 1.0, 5, 200)), talhao = "a")
        val a1 = registroDoTalhao(estado, "1", "", 1, false)!!
        val b = registroDoTalhao(estado.copy(talhao = "b"), "1", "", 1, false)!!
        val a2 = registroDoTalhao(estado.copy(colhidoSacas = 500.0, areaHa = 10.0), "2", "", 1, false)!!
        val todos = comTalhao(comTalhao(comTalhao(emptyList(), a1), b), a2)
        assertEquals(listOf("b", "a"), todos.map { it.talhao })
        assertEquals(3000.0, todos.last().colheita_kg_ha!!, 1e-9)
    }
}
