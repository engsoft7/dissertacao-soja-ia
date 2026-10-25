package com.agrointeligencia.app

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.LocalDateTime

/**
 * As contas da tela Tempo. A janela de pulverização decide se o produtor
 * aplica ou não: um limite trocado (vento a 10 m lido como vento na lavoura,
 * umidade de 50% em vez de 60%) passaria por tela bonita.
 *
 * A resposta de exemplo é real: Open-Meteo para Paragominas, lida pelo
 * GitHub Actions em 25/10/2026 às 17h45 (dados sob CC BY 4.0).
 */
class TempoCalculoTest {

    private val previsao: PrevisaoTempo = Gson().fromJson(
        javaClass.classLoader!!.getResource("openmeteo_paragominas_2026-10-25.json")!!.readText(),
        PrevisaoTempo::class.java
    )
    private val agora = LocalDateTime.parse("2026-10-25T17:45")

    @Test
    fun vento_de_10_m_vira_75_por_cento_a_2_m() {
        // FAO-56, eq. 47: 4,87 / ln(672,58) = 0,748.
        assertEquals(7.48, ventoA2m(10.0), 0.01)
    }

    @Test
    fun hora_boa_sem_motivos() {
        val (nivel, motivos) = avaliaHora(25.0, 70.0, 8.0, chuvaNaHora = false, chuvaLogo = false)
        assertEquals(NivelJanela.BOA, nivel)
        assertTrue(motivos.isEmpty())
    }

    @Test
    fun limites_da_embrapa() {
        assertEquals(NivelJanela.EVITAR, avaliaHora(30.5, 70.0, 8.0, false, false).first)
        assertEquals(NivelJanela.BOA, avaliaHora(30.0, 70.0, 8.0, false, false).first)
        assertEquals(NivelJanela.EVITAR, avaliaHora(25.0, 59.0, 8.0, false, false).first)
        assertEquals(NivelJanela.BOA, avaliaHora(25.0, 60.0, 8.0, false, false).first)
        // 12 km/h a 10 m são 9 km/h na lavoura: só com ponta antideriva.
        val (n, m) = avaliaHora(25.0, 70.0, 12.0, false, false)
        assertEquals(NivelJanela.ATENCAO, n)
        assertTrue(m.single().contains("antideriva"))
        // 15 km/h a 10 m são 11 km/h na lavoura.
        assertEquals(NivelJanela.EVITAR, avaliaHora(25.0, 70.0, 15.0, false, false).first)
        // 3 km/h a 10 m são 2 km/h: calmaria, gotas suspensas.
        assertEquals(NivelJanela.ATENCAO, avaliaHora(25.0, 70.0, 3.0, false, false).first)
        assertEquals(NivelJanela.ATENCAO, avaliaHora(8.0, 70.0, 8.0, false, false).first)
    }

    @Test
    fun chuva_na_hora_evita_e_chuva_logo_pede_atencao() {
        assertEquals(NivelJanela.EVITAR, avaliaHora(25.0, 70.0, 8.0, chuvaNaHora = true, chuvaLogo = true).first)
        val (n, m) = avaliaHora(25.0, 70.0, 8.0, chuvaNaHora = false, chuvaLogo = true)
        assertEquals(NivelJanela.ATENCAO, n)
        assertEquals(listOf("chuva prevista nas 2 horas seguintes"), m)
    }

    @Test
    fun previsao_incompleta_nao_vira_hora_boa() {
        assertEquals(NivelJanela.ATENCAO, avaliaHora(null, 70.0, 8.0, false, false).first)
    }

    @Test
    fun motivos_mais_graves_primeiro() {
        val (_, m) = avaliaHora(32.3, 52.0, 11.6, false, false)
        assertEquals(listOf("temperatura acima de 30 °C", "umidade abaixo de 60%",
                            "vento entre 8 e 10 km/h: só com ponta antideriva"), m)
    }

    @Test
    fun resposta_real_comeca_na_hora_em_curso() {
        val horas = horasDePulverizacao(previsao.hourly!!, agora)
        assertEquals(24, horas.size)
        assertEquals(LocalDateTime.parse("2026-10-25T17:00"), horas.first().hora)
        assertEquals(32.3, horas.first().temperatura!!, 1e-9)
        assertEquals(NivelJanela.EVITAR, horas.first().nivel)
    }

    @Test
    fun janela_boa_da_resposta_real_e_de_madrugada() {
        // Das 2h às 8h de 26/10: fresco, úmido e com vento entre 5 e 7 km/h na
        // lavoura. A partir das 8h o vento passa de 10 km/h, e depois o calor.
        val j = proximaJanela(horasDePulverizacao(previsao.hourly!!, agora))!!
        assertEquals(LocalDateTime.parse("2026-10-26T02:00"), j.inicio)
        assertEquals(LocalDateTime.parse("2026-10-26T08:00"), j.fim)
    }

    @Test
    fun hora_boa_isolada_nao_e_janela() {
        fun h(i: Int, n: NivelJanela) = HoraPulverizacao(LocalDateTime.parse("2026-10-25T00:00").plusHours(i.toLong()),
                                                          n, emptyList(), null, null, null, null)
        val b = NivelJanela.BOA
        val e = NivelJanela.EVITAR
        assertNull(proximaJanela(listOf(h(0, b), h(1, e), h(2, b), h(3, e))))
        assertEquals(LocalDateTime.parse("2026-10-25T05:00"),
                     proximaJanela(listOf(h(0, b), h(1, e), h(2, b), h(3, b), h(4, b)))!!.fim)
    }

    @Test
    fun balanco_de_chuva_da_resposta_real() {
        val b = balancoChuva(dias(previsao.daily!!), LocalDate.parse("2026-10-25"))
        assertEquals(7, b.diasPassados)
        assertEquals(2.5, b.chuvaPassada, 1e-6)
        assertEquals(41.17, b.et0Passada, 1e-6)
        assertEquals(-38.67, b.saldo, 1e-6)
        assertEquals(7, b.diasPrevistos)
        assertEquals(1.1, b.chuvaPrevista, 1e-6)
    }

    @Test
    fun descricoes_e_categorias() {
        assertEquals("Nublado", descricaoTempo(3))
        assertEquals("Trovoada com granizo", descricaoTempo(99))
        assertEquals("NE", direcaoVento(48.0))
        assertEquals("N", direcaoVento(350.0))
        assertEquals("O", direcaoVento(-90.0))
        assertEquals("muito alto", categoriaUv(9.15))
        assertEquals("extremo", categoriaUv(11.0))
        assertEquals("baixo", categoriaUv(2.4))
    }

    @Test
    fun data_do_aviso_do_inmet() {
        assertEquals("26/10 às 00:00", dataDoAviso("2026-10-26 00:00"))
        assertEquals("formato novo", dataDoAviso("formato novo"))
        assertEquals("?", dataDoAviso(null))
    }

    @Test
    fun posicao_arredondada_a_um_quilometro() {
        assertEquals(-3.0, arredonda(-3.00212), 1e-9)
        assertEquals(-47.35, arredonda(-47.3527), 1e-9)
    }

    @Test
    fun sedes_dos_38_municipios_no_para() {
        assertEquals(38, SEDES_MUNICIPAIS.size)
        SEDES_MUNICIPAIS.forEach { (nome, l) ->
            assertEquals(nome, l.nome)
            assertTrue(nome, l.lat in -10.0..2.7 && l.lon in -59.0..-46.0)
            assertTrue(nome, l.geocode!!.startsWith("15"))
        }
        // Pau D'Arco fica no sul do Pará; a tabela de origem a punha no nordeste.
        assertTrue(SEDES_MUNICIPAIS.getValue("Pau D'Arco").lat < -7.5)
    }
}
