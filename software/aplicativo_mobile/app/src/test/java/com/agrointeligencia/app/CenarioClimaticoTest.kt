package com.agrointeligencia.app

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** A frase do simulador diz só o efeito que o cenário usou. */
class CenarioClimaticoTest {

    @Test
    fun semEfeitoClaroOCenarioNaoMove() {
        val a = AssociacaoClimatica(EfeitoClimatico(-2.1, vale = false), EfeitoClimatico(-163.0, vale = false))
        assertEquals("Nesta base, nem a chuva nem a temperatura mostraram efeito claro na produtividade: " +
                     "o cenário não muda a projeção.", fraseDaAssociacao(a))
    }

    @Test
    fun chuvaComEfeitoNoMaranhao() {
        val a = AssociacaoClimatica(EfeitoClimatico(4.5, vale = true), EfeitoClimatico(-153.0, vale = false))
        assertEquals("Nesta base, cada 10% a menos de chuva tirou, em média, 45 kg/ha; " +
                     "a temperatura não mostrou efeito claro.", fraseDaAssociacao(a))
    }

    @Test
    fun respostaAntigaSemAssociacaoAindaELida() {
        val r = Gson().fromJson("""{"municipio":"Altamira","baseline_kg_ha":3000,"estimativa_kg_ha":3000,
            "delta_kg_ha":0}""", SimulacaoResponse::class.java)
        assertNull(r.associacao)
        val nova = Gson().fromJson("""{"municipio":"Balsas","baseline_kg_ha":3000,"estimativa_kg_ha":2910,
            "delta_kg_ha":-90,"associacao":{"chuva":{"kg_ha":4.5,"ic95":[0.5,8.0],"vale":true,"faixa":[-30.1,26.6]},
            "temperatura":{"kg_ha":-153.1,"vale":false},"registros":1121}}""", SimulacaoResponse::class.java)
        assertEquals(true, nova.associacao?.chuva?.vale)
    }
}
