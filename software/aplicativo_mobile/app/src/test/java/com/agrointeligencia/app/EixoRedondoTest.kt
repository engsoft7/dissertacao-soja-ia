package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * As marcas do eixo de preço dos gráficos da tela Mercado.
 *
 * O eixo dividia a faixa exata dos dados em três e saía com 135,87 / 141,04 /
 * 146,20 / 151,37: números que ninguém lê de relance. Estes testes fixam o
 * contrato novo: passo redondo, faixa coberta, rótulo sem casas quando o passo
 * é inteiro.
 */
class EixoRedondoTest {

    @Test
    fun faixa_do_mes_de_chicago_sai_com_passo_redondo() {
        // A faixa da captura de 23/10/2026: mínima 135,87, máxima 151,37.
        val marcas = eixoRedondo(135.87, 151.37)
        assertEquals(listOf(135.0, 140.0, 145.0, 150.0, 155.0), marcas)
    }

    @Test
    fun as_marcas_cobrem_os_dados() {
        val marcas = eixoRedondo(118.88, 148.04)
        assertTrue(marcas.first() <= 118.88)
        assertTrue(marcas.last() >= 148.04)
        assertTrue(marcas.size in 3..7)
    }

    @Test
    fun faixa_estreita_de_um_dia_usa_passo_menor_que_um_real() {
        val marcas = eixoRedondo(139.42, 140.31)
        val passo = marcas[1] - marcas[0]
        assertEquals(0.25, passo, 1e-9)
    }

    @Test
    fun rotulo_sem_casas_com_passo_inteiro_e_com_duas_com_passo_fracionado() {
        assertEquals("140", rotuloEixo(140.0, listOf(135.0, 140.0)))
        assertEquals("139,50", rotuloEixo(139.5, listOf(139.25, 139.5)))
    }

    @Test
    fun faixa_vazia_nao_quebra() {
        val marcas = eixoRedondo(140.0, 140.0)
        assertTrue(marcas.size >= 2)
        assertTrue(marcas.first() <= 140.0 && marcas.last() >= 140.0)
    }
}
