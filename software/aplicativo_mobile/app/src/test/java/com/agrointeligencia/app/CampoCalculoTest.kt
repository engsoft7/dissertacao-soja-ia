package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * As contas da Estimativa no campo. São elas que viram sacas e reais na tela:
 * um erro de unidade aqui passaria por número plausível.
 */
class CampoCalculoTest {

    private val par = ParametrosCampo(espacamento = 0.45, graosPorVagem = 2.2, pesoMilGraos = 150.0)

    @Test
    fun conta_por_componentes_em_kg_por_hectare() {
        // 13 plantas em 1 m de linha a 0,45 m: 28,9 plantas/m².
        // 200 vagens em 5 plantas: 40 vagens/planta.
        // 28,89 × 40 × 2,2 × 150 / 100 = 3.813 kg/ha = 63,6 sc/ha.
        val e = estimaLavoura(listOf(PontoAmostra(13, 1.0, 5, 200)), par)!!
        assertEquals(28.89, e.plantasPorM2, 0.01)
        assertEquals(40.0, e.vagensPorPlanta, 1e-9)
        assertEquals(3813.3, e.kgHa, 0.1)
        assertEquals(63.56, e.scHa, 0.01)
    }

    @Test
    fun media_e_por_ponto_e_a_faixa_vai_junto() {
        val pontos = listOf(PontoAmostra(13, 1.0, 5, 200), PontoAmostra(9, 1.0, 10, 300))
        val e = estimaLavoura(pontos, par)!!
        val a = kgPorHectare(13 / 0.45, 40.0, 2.2, 150.0)
        val b = kgPorHectare(9 / 0.45, 30.0, 2.2, 150.0)
        assertEquals((a + b) / 2, e.kgHa, 1e-6)
        assertEquals(b, e.kgHaMin, 1e-6)
        assertEquals(a, e.kgHaMax, 1e-6)
        assertEquals(2, e.pontos)
    }

    @Test
    fun ponto_incompleto_fica_de_fora() {
        val pontos = listOf(PontoAmostra(13, 1.0, 5, 200), PontoAmostra(0, 1.0, 5, 180))
        assertEquals(1, estimaLavoura(pontos, par)!!.pontos)
    }

    @Test
    fun sem_ponto_ou_com_parametro_zerado_nao_ha_estimativa() {
        assertNull(estimaLavoura(emptyList(), par))
        assertNull(estimaLavoura(listOf(PontoAmostra(13, 1.0, 5, 200)), par.copy(espacamento = 0.0)))
    }

    @Test
    fun area_de_um_quadrado_de_100_m_em_paragominas() {
        // 100 m de lado a 3° S: 1 ha. Um grau de latitude tem 111.195 m.
        val lat = -3.0
        val dLat = 100.0 / 111_195.0
        val dLon = dLat / kotlin.math.cos(Math.toRadians(lat))
        val quadrado = listOf(lat to -47.0, lat to -47.0 + dLon, lat + dLat to -47.0 + dLon, lat + dLat to -47.0)
        assertEquals(1.0, areaHectares(quadrado), 0.01)
        // A ordem de marcação (horário ou anti-horário) não muda a área.
        assertEquals(1.0, areaHectares(quadrado.reversed()), 0.01)
    }

    @Test
    fun menos_de_tres_cantos_nao_tem_area() {
        assertEquals(0.0, areaHectares(listOf(-3.0 to -47.0, -3.001 to -47.0)), 0.0)
    }
}
