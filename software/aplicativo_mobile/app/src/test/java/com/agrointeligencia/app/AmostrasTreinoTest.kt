package com.agrointeligencia.app

import org.junit.Assert.assertEquals
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
}
