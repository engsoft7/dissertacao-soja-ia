package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * As contas do gráfico de velas de trader (GraficoVelasCalculo.kt): médias
 * móveis, zoom pela pinça sem tirar a vela de sob os dedos, arrasto que não
 * sai do período, a vela sob o dedo e a escala que acompanha o zoom.
 */
class GraficoVelasCalculoTest {

    private val erro = 1e-4f

    private fun vela(i: Int, l: Double, h: Double, pa: Double? = null) =
        Vela(t = 1_792_670_400L + i * 900L, o = (l + h) / 2, h = h, l = l, c = (l + h) / 2, pa = pa)

    @Test
    fun media_movel_simples_dos_fechamentos() {
        val m = mediaMovel(listOf(1.0, 2.0, 3.0, 4.0, 5.0), 3)
        assertEquals(listOf(null, null, 2.0, 3.0, 4.0), m)
    }

    @Test
    fun media_movel_com_menos_velas_que_o_periodo_fica_vazia() {
        assertEquals(listOf<Double?>(null, null), mediaMovel(listOf(130.0, 131.0), MEDIA_LONGA))
        assertEquals(listOf<Double?>(null), mediaMovel(listOf(130.0), 0))
    }

    @Test
    fun media_movel_de_9_confere_com_a_conta_a_mao() {
        val fechamentos = (1..30).map { 120.0 + it }
        val m = mediaMovel(fechamentos, MEDIA_CURTA)
        assertNull(m[7])
        assertEquals(fechamentos.subList(0, 9).average(), m[8]!!, 1e-9)
        assertEquals(fechamentos.subList(21, 30).average(), m[29]!!, 1e-9)
    }

    @Test
    fun janela_inteira_e_seus_indices() {
        val j = janelaInteira(85)
        assertTrue(j.inteira(85))
        assertEquals(0..84, j.indices(85))
    }

    @Test
    fun pinca_aproxima_sem_tirar_a_vela_de_sob_os_dedos() {
        val j = janelaInteira(100).comZoom(fator = 2f, ancora = 0.75f, total = 100)
        assertEquals(50f, j.tamanho, erro)
        // A vela sob os dedos era a 75 (0,75 de 100) e continua sob o mesmo ponto.
        assertEquals(75f, j.inicio + 0.75f * j.tamanho, erro)
        assertFalse(j.inteira(100))
    }

    @Test
    fun pinca_nao_aproxima_alem_do_minimo_nem_afasta_alem_do_periodo() {
        val perto = janelaInteira(100).comZoom(fator = 100f, ancora = 0.5f, total = 100)
        assertEquals(VELAS_MINIMAS_NA_TELA.toFloat(), perto.tamanho, erro)
        val longe = perto.comZoom(fator = 0.01f, ancora = 0.5f, total = 100)
        assertEquals(janelaInteira(100), longe)
        // Com menos velas que o mínimo, o período inteiro é o máximo de zoom.
        assertEquals(janelaInteira(5), janelaInteira(5).comZoom(fator = 3f, ancora = 0.5f, total = 5))
    }

    @Test
    fun pinca_na_borda_nao_sai_do_periodo() {
        val j = janelaInteira(100).comZoom(fator = 4f, ancora = 1f, total = 100)
        assertEquals(25f, j.tamanho, erro)
        assertEquals(100f, j.fim, erro)
    }

    @Test
    fun arrasto_anda_pelo_periodo_e_para_nas_pontas() {
        val j = JanelaVelas(50f, 20f)
        // O dedo para a direita leva ao passado.
        assertEquals(40f, j.arrastada(10f, 100).inicio, erro)
        assertEquals(0f, j.arrastada(500f, 100).inicio, erro)
        assertEquals(80f, j.arrastada(-500f, 100).inicio, erro)
    }

    @Test
    fun vela_sob_o_dedo() {
        val j = JanelaVelas(10f, 20f)
        assertEquals(10, j.velaEm(0f, 100))
        assertEquals(20, j.velaEm(0.5f, 100))
        assertEquals(29, j.velaEm(1f, 100))
        assertEquals(29, j.velaEm(1.5f, 100))
        assertNull(JanelaVelas(0f, 10f).velaEm(0.5f, 0))
    }

    @Test
    fun velas_novas_acompanham_quem_via_o_fim() {
        // Período inteiro continua inteiro.
        assertEquals(janelaInteira(86), janelaInteira(85).comVelasNovas(85, 86))
        // No fim, a janela anda junto com a vela nova.
        val noFim = JanelaVelas(65f, 20f).comVelasNovas(85, 86)
        assertEquals(66f, noFim.inicio, erro)
        assertEquals(20f, noFim.tamanho, erro)
        // No passado, fica onde estava.
        assertEquals(JanelaVelas(10f, 20f), JanelaVelas(10f, 20f).comVelasNovas(85, 86))
    }

    @Test
    fun escala_acompanha_o_zoom_e_inclui_as_linhas() {
        val velas = (0 until 40).map { i -> if (i < 20) vela(i, 100.0, 102.0) else vela(i, 140.0, 141.0) }
        assertEquals(100.0 to 141.0, faixaVisivel(velas, janelaInteira(40)))
        assertEquals(140.0 to 141.0, faixaVisivel(velas, JanelaVelas(25f, 10f)))
        // A média, desenhada por cima, entra na escala.
        val media = List<Double?>(40) { 138.0 }
        assertEquals(138.0 to 141.0, faixaVisivel(velas, JanelaVelas(25f, 10f), listOf(media)))
        // A linha do Pará também.
        val comPara = velas.mapIndexed { i, v -> if (i == 30) v.copy(pa = 136.5) else v }
        assertEquals(136.5 to 141.0, faixaVisivel(comPara, JanelaVelas(25f, 10f)))
        assertNull(faixaVisivel(emptyList(), janelaInteira(0)))
    }
}
