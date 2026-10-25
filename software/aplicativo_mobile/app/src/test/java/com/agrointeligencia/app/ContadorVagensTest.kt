package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * O caminho da foto até o modelo e do mapa de volta às marcas, sem o modelo:
 * é o que converte_para_celular.py repete na conferência, e precisa bater.
 */
class ContadorVagensTest {

    @Test
    fun foto_deitada_ocupa_o_quadro_inteiro() {
        assertEquals(Triple(768, 576, false), tamanhoNoQuadro(2048, 1536, MODELO_CONTAGEM))
        assertEquals(Triple(1024, 768, false), tamanhoNoQuadro(4000, 3000, MODELO_MARCAS))
    }

    @Test
    fun foto_em_pe_e_girada_e_mantem_a_escala_do_treino() {
        assertEquals(Triple(768, 576, true), tamanhoNoQuadro(1536, 2048, MODELO_CONTAGEM))
    }

    @Test
    fun foto_de_outra_proporcao_cabe_no_quadro() {
        assertEquals(Triple(1024, 576, false), tamanhoNoQuadro(4000, 2250, MODELO_MARCAS))
        assertEquals(Triple(768, 768, false), tamanhoNoQuadro(1000, 1000, MODELO_MARCAS))
    }

    @Test
    fun normaliza_como_no_treino_e_completa_com_zero() {
        val m = MODELO_CONTAGEM
        val x = normaliza(intArrayOf(0xFFFFFFFF.toInt(), 0xFF000000.toInt()), nw = 2, nh = 1, m = m)
        val plano = m.largura * m.altura
        assertEquals((1f - 0.485f) / 0.229f, x[0], 1e-5f)
        assertEquals((0f - 0.406f) / 0.225f, x[2 * plano + 1], 1e-5f)
        assertEquals(0f, x[2], 0f)                  // fora da foto
        assertEquals(0f, x[m.largura], 0f)          // linha de baixo, fora da foto
    }

    @Test
    fun soma_o_mapa_so_na_foto_e_acha_os_maximos() {
        val m = MODELO_CONTAGEM
        val largura = m.largura / m.passo           // 96 células
        val mapa = FloatArray(largura * (m.altura / m.passo))
        fun poe(x: Int, y: Int, v: Float) { mapa[y * largura + x] = v }
        poe(10, 10, 50f)
        poe(11, 10, 30f)
        poe(40, 40, 20f)
        poe(0, 0, -500f)                            // negativo é cortado
        poe(95, 10, 900f)                           // fora da parte ocupada pela foto
        val (soma, marcas) = interpreta(mapa, nw = 760, nh = 570, m = m)
        assertEquals(1.0, soma, 1e-6)
        assertEquals(2, marcas.size)
        assertEquals(10.5f * 8 / 760, marcas[0].first, 1e-6f)
        assertEquals(10.5f * 8 / 570, marcas[0].second, 1e-6f)
        assertEquals(40.5f * 8 / 760, marcas[1].first, 1e-6f)
    }

    @Test
    fun abaixo_do_limiar_nao_vira_marca() {
        val m = MODELO_MARCAS
        val mapa = FloatArray((m.largura / m.passo) * (m.altura / m.passo))
        mapa[5] = 100f * m.limiar
        val (_, marcas) = interpreta(mapa, m.largura, m.altura, m)
        assertTrue(marcas.isEmpty())
    }

    @Test
    fun marca_da_foto_girada_volta_para_a_foto_em_pe() {
        // O canto de cima à esquerda da foto girada no sentido horário é o de
        // baixo à esquerda da foto em pé.
        assertEquals(listOf(0f to 1f), desgira(listOf(0f to 0f), girou = true))
        assertEquals(listOf(0.25f to 0.5f), desgira(listOf(0.5f to 0.25f), girou = true))
        assertEquals(listOf(0.3f to 0.7f), desgira(listOf(0.3f to 0.7f), girou = false))
        assertFalse(desgira(emptyList(), girou = true).isNotEmpty())
    }
}
