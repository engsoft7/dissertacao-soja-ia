package com.agrointeligencia.app

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/** Respostas e caches estranhos não chegam às telas. */
class RespostasTest {

    private val gson = Gson()

    @Test
    fun previsaoSemHistoricoEDescartada() {
        // Cache cortado ou de outra versão: o Gson deixa nulo um campo não nulo.
        assertNull(gson.fromJson("{}", PrevisaoResponse::class.java).valida())
        assertNull(gson.fromJson("""{"municipio":"Marabá"}""", PrevisaoResponse::class.java).valida())
    }

    @Test
    fun previsaoCompletaPassa() {
        val json = """{"municipio":"Marabá","historico":[{"ano":2025,"rendimento_predito":3200.0,
            "rendimento_real":3000.0,"margem_erro":300.0}]}"""
        assertNotNull(gson.fromJson(json, PrevisaoResponse::class.java).valida())
    }

    @Test
    fun mercadoGuardadoSemPracasNaoQuebra() {
        val m = gson.fromJson("""{"cotacao":null}""", MercadoResponse::class.java)
        assertNull(pracaParaUsar("Marabá", m.pracas_para.orEmpty()))
    }

    @Test
    fun mercadoComMediaMensalDaConab() {
        val m = gson.fromJson("""{"cotacao":null,"conab_mensal":{"uf":"PA","mes":"2026-10","preco_saca":133.8,
            "fonte":"CONAB"}}""", MercadoResponse::class.java)
        assertEquals("2026-10", m.conab_mensal?.mes)
        assertEquals(133.8, m.conab_mensal!!.preco_saca, 1e-9)
        // A API antiga não manda o campo: a tela omite a linha.
        assertNull(gson.fromJson("""{"cotacao":null}""", MercadoResponse::class.java).conab_mensal)
    }
}
