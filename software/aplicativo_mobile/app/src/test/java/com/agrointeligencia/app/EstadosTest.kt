package com.agrointeligencia.app

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Regras de Estados.kt: o Pará igual às versões antigas, e os outros estados só com resposta deles. */
class EstadosTest {

    @Test
    fun paraPedeEGuardaComoAntes() {
        assertNull(ufParaApi("PA"))
        assertEquals("MT", ufParaApi("MT"))
        assertEquals("previsao_Paragominas", chaveDoEstado("previsao_Paragominas", "PA"))
        assertEquals("previsao_Sorriso_MT", chaveDoEstado("previsao_Sorriso", "MT"))
        assertEquals("PA", estadoDoApp(null).uf)
        assertEquals("PA", estadoDoApp("SP").uf)
        assertEquals("no Maranhão", estadoDoApp("MA").no)
        assertEquals("de Mato Grosso", estadoDoApp("MT").de)
        assertEquals("no Tocantins", estadoDoApp("TO").no)
        assertEquals("de Rondônia", estadoDoApp("RO").de)
        assertEquals("previsao_Vilhena_RO", chaveDoEstado("previsao_Vilhena", "RO"))
    }

    @Test
    fun respostaDaApiAntigaNaoValeParaOutroEstado() {
        assertTrue(respostaDoEstado("PA", null))
        assertTrue(respostaDoEstado("MT", "MT"))
        assertFalse("a API antiga ignora ?uf= e responde pelo Pará", respostaDoEstado("MT", null))
        assertFalse(respostaDoEstado("MA", "MT"))
    }

    @Test
    fun sedesDoServidorViramLugares() {
        val r = Gson().fromJson("""{"municipios":["Sorriso"],"uf":"MT",
            "sedes":[{"nome":"Sorriso","cod_ibge7":5107925,"latitude":-12.5425,"longitude":-55.7211}]}""",
            MunicipioResponse::class.java)
        val sedes = sedesDoEstado("MT", r.sedes)
        assertEquals("5107925", sedes.getValue("Sorriso").geocode)
        assertEquals(-12.5425, sedes.getValue("Sorriso").lat, 1e-9)
        assertEquals(SEDES_MUNICIPAIS, sedesDoEstado("PA", null))
        assertTrue(sedesDoEstado("MA", null).isEmpty())
        // A resposta antiga, sem sedes, ainda é lida.
        assertNull(Gson().fromJson("""{"municipios":["Altamira"]}""", MunicipioResponse::class.java).sedes)
    }

    @Test
    fun pracasDoEstadoEPracaMaisPerto() {
        val hoje = java.time.LocalDate.of(2027, 3, 2)
        val mt = MercadoResponse(uf = "MT", pracas_para = emptyList(), pracas = listOf(
            PracaPara("Sorriso", "MT", 110.0, "2027-03-01"), PracaPara("Rondonópolis", "MT", 115.0, "2027-03-01")))
        assertEquals(2, mt.pracasDoEstado().size)
        assertEquals(0, MercadoResponse(pracas = mt.pracas).pracasDoEstado().size)  // sem uf, o campo do Pará
        val sedes = mapOf(
            "Sorriso" to LugarTempo("Sorriso", -12.5425, -55.7211, "5107925"),
            "Rondonópolis" to LugarTempo("Rondonópolis", -16.4673, -54.6372, "5107602"),
            "Lucas do Rio Verde" to LugarTempo("Lucas do Rio Verde", -13.0588, -55.9042, "5105259"))
        assertEquals("Sorriso", pracaParaUsar("Lucas do Rio Verde", mt.pracasDoEstado(), hoje, sedes)?.praca)
    }
}
