package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Test

/**
 * A margem por hectare — o número que decide se o produtor vende.
 *
 * Até aqui o aplicativo não tinha teste nenhum, e esta é a função que mais
 * merecia: ela produz o valor em reais que aparece em verde ou vermelho na
 * tela, e o produtor decide olhando para ele.
 *
 * Os números vêm do levantamento MAR-2026 da CONAB para Pedro Afonso (TO), o
 * mesmo que o produto exibe: preço recebido R$ 105,09/sc, custo variável
 * R$ 85,03/sc, custo fixo R$ 1.195,68/ha (R$ 24,91/sc sobre a produtividade
 * de referência de 48 sc/ha) e custo operacional R$ 5.277,12/ha. Não são
 * números inventados para o teste passar: se o levantamento mudar e alguém
 * atualizar só um lado, o teste denuncia.
 *
 * DELTA existe porque somar e multiplicar Double não devolve o decimal exato;
 * um centavo de tolerância é mais que suficiente para afirmações sobre reais
 * por hectare, e não esconde erro de verdade nenhum.
 */
class ResultadoPorHectareTest {

    private val delta = 0.01

    private fun kpis(
        variavel: Double? = 85.03,
        fixo: Double? = 1195.68,
    ) = FinancaResponse(
        soja_preco_saca = 105.09,
        custo_ha = 5277.12,
        custo_variavel_saca = variavel,
        custo_fixo_ha = fixo,
        // Obrigatório no modelo, e sem valor padrão de propósito: é o ano que
        // a tela cita ao lado do custo. Não entra em nenhum cálculo desta
        // função, mas omitir não compila — e é assim que tem de ser, para
        // ninguém exibir margem sem dizer de que safra ela é.
        ano_referencia = 2026,
    )

    /**
     * O caso que motivou os dois rateios existirem.
     *
     * A 55 sc/ha, tratar o custo variável como fixo por hectare devolve lucro
     * de R$ 502,83; tratá-lo como proporcional à produção devolve prejuízo de
     * R$ 92,38. Os mesmos dados, o sinal invertido. É a situação em que pintar
     * a tela de verde manda o produtor decidir com uma certeza que o dado não
     * sustenta, e por isso a função tem de marcar sinalIncerto.
     */
    @Test
    fun `acima da produtividade de referencia o sinal do resultado fica incerto`() {
        val r = resultadoPorHectare(55.0, 105.09, null, kpis())

        assertEquals(502.83, r.valor, delta)
        assertEquals(-92.38, r.outroRateio!!, delta)
        assertTrue("os dois rateios discordam sobre lucro e prejuízo", r.sinalIncerto)
    }

    /** Safra boa: os dois rateios concordam que houve lucro, e a tela pode afirmar. */
    @Test
    fun `com folga os dois rateios concordam e o sinal e certo`() {
        val r = resultadoPorHectare(70.0, 105.09, null, kpis())

        assertEquals(2079.18, r.valor, delta)
        assertEquals(208.52, r.outroRateio!!, delta)
        assertFalse(r.sinalIncerto)
    }

    /** Safra ruim: concordam que houve prejuízo. Concordar no vermelho também é concordar. */
    @Test
    fun `abaixo do custo os dois rateios concordam no prejuizo`() {
        val r = resultadoPorHectare(40.0, 105.09, null, kpis())

        assertEquals(-1073.52, r.valor, delta)
        assertEquals(-393.28, r.outroRateio!!, delta)
        assertFalse(r.sinalIncerto)
    }

    /**
     * Quando o produtor informa o próprio custo não há rateio a discutir: o
     * número é dele. A função devolve só um valor, e a tela não tem por que
     * exibir ressalva sobre uma ambiguidade que deixou de existir.
     */
    @Test
    fun `custo informado pelo produtor dispensa o rateio e a ressalva`() {
        val r = resultadoPorHectare(55.0, 105.09, 4800.0, kpis())

        assertEquals(979.95, r.valor, delta)
        assertNull("sem rateio alternativo quando o custo é do produtor", r.outroRateio)
        assertFalse(r.sinalIncerto)
    }

    /**
     * API mais antiga que o aplicativo: não manda a abertura do custo. Sem os
     * dois componentes não há segundo rateio para calcular, e a função devolve
     * o que consegue em vez de inventar um número ou quebrar.
     */
    @Test
    fun `sem a abertura do custo devolve so o rateio por hectare`() {
        val semVariavel = resultadoPorHectare(55.0, 105.09, null, kpis(variavel = null))
        assertEquals(502.83, semVariavel.valor, delta)
        assertNull(semVariavel.outroRateio)
        assertFalse(semVariavel.sinalIncerto)

        val semFixo = resultadoPorHectare(55.0, 105.09, null, kpis(fixo = null))
        assertEquals(502.83, semFixo.valor, delta)
        assertNull(semFixo.outroRateio)
        assertFalse(semFixo.sinalIncerto)
    }

    /**
     * O preço que entra na receita é o do argumento, não o do levantamento.
     * É o que sustenta o produtor informar o preço que recebe: se a função
     * ignorasse o argumento e usasse kpis.soja_preco_saca, a tela mostraria
     * o preço dele e calcularia a margem com o da CONAB.
     */
    @Test
    fun `a receita usa o preco informado e nao o do levantamento`() {
        val comPrecoProprio = resultadoPorHectare(55.0, 135.15, null, kpis())
        val comPrecoConab = resultadoPorHectare(55.0, 105.09, null, kpis())

        assertEquals(55.0 * 135.15 - 5277.12, comPrecoProprio.valor, delta)
        assertTrue(
            "preço maior tem de produzir margem maior",
            comPrecoProprio.valor > comPrecoConab.valor
        )
    }

    // ── custo aberto por item (planilha da série histórica da CONAB) ─────────
    // MAR-2026, Pedro Afonso (TO): R$ 5.042,88/ha por área, transporte de
    // R$ 3,30/sc e CESSR de 1,5% da receita, que somam os R$ 5.277,12/ha na
    // produtividade (48 sc/ha) e no preço (R$ 105,09) de referência.
    private fun kpisComItens() = kpis().copy(custo_area_ha = 5042.88, custo_transporte_saca = 3.30, taxa_cessr = 0.015)

    @Test
    fun comItensNaReferenciaDaOResultadoDaConab() {
        val r = resultadoPorHectare(48.0, 105.09, null, kpisComItens())
        assertEquals(48.0 * 105.09 - 5277.12, r.valor, 1.0)
        assertNull(r.outroRateio)
        assertFalse(r.sinalIncerto)
    }

    @Test
    fun comItensUmValorSoAcimaDaReferencia() {
        // A 52 sc/ha os dois rateios discordavam do sinal; com os itens há um valor só.
        val r = resultadoPorHectare(52.0, 105.09, null, kpisComItens())
        val esperado = 52.0 * 105.09 - (5042.88 + (3.30 + 0.015 * 105.09) * 52.0)
        assertEquals(esperado, r.valor, delta)
        assertNull(r.outroRateio)
        assertFalse(r.sinalIncerto)
        assertTrue(r.valor > 0)
    }

    @Test
    fun custoDoProdutorVenceOsItens() {
        val r = resultadoPorHectare(52.0, 105.09, 4000.0, kpisComItens())
        assertEquals(52.0 * 105.09 - 4000.0, r.valor, delta)
    }

    @Test
    fun pontoDeEquilibrioComItens() {
        // área / (preço × (1 − CESSR) − transporte) = 5042,88 / (105,09 × 0,985 − 3,30)
        val eq = pontoDeEquilibrio(105.09, null, kpisComItens())!!
        assertEquals(5042.88 / (105.09 * 0.985 - 3.30), eq, 1e-6)
        assertEquals(5277.12 / 105.09, pontoDeEquilibrio(105.09, null, kpis())!!, 1e-6)
        assertEquals(4000.0 / 105.09, pontoDeEquilibrio(105.09, 4000.0, kpisComItens())!!, 1e-6)
        assertNull(pontoDeEquilibrio(0.0, null, kpisComItens()))
    }

    @Test
    fun historicoUsaAsSacasDoCampoDaViabilidade() {
        // 3.297 kg/ha: a Viabilidade mostra 55,0 sc e conta com 55,0; o cartão
        // do ano contava com 54,95 e dava R$ 7/ha a menos para a mesma safra.
        assertEquals(55.0, sacasDoCampo(3297 / 60.0), 0.0)
        assertEquals(54.9, sacasDoCampo(54.94), 0.0)
        assertEquals(50.0, sacasDoCampo(3000 / 60.0), 0.0)
        val campo = resultadoPorHectare(55.0, 148.5, null, kpisComItens())
        val cartao = resultadoPorHectare(sacasDoCampo(3297 / 60.0), 148.5, null, kpisComItens())
        assertEquals(campo.valor, cartao.valor, 0.0)
    }
}
