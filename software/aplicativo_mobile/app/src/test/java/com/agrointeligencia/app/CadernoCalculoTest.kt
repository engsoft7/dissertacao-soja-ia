package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate

/**
 * As contas do caderno da safra. Um erro aqui mostra ao produtor um custo por
 * saca ou um resultado que não são os da lavoura dele.
 */
class CadernoCalculoTest {
    private var proximo = 0L
    private fun r(tipo: TipoRegistro, data: String, area: Double? = null, qtd: Double? = null, valor: Double? = null,
                  descricao: String = "", safra: Int = 2027) =
        RegistroCaderno(++proximo, safra, tipo, data, descricao, area, qtd, null, valor)

    private val safra = listOf(
        r(TipoRegistro.PLANTIO, "2026-11-05", area = 100.0, descricao = "BRS 8383"),
        r(TipoRegistro.INSUMO, "2026-10-20", qtd = 50.0, valor = 25_000.0, descricao = "semente"),
        r(TipoRegistro.OPERACAO, "2026-12-10", valor = 5_000.0, descricao = "fungicida"),
        r(TipoRegistro.COLHEITA, "2027-03-15", area = 100.0, qtd = 5_500.0),
        r(TipoRegistro.VENDA, "2027-03-20", qtd = 3_000.0, valor = 120.0),
        r(TipoRegistro.VENDA, "2027-04-10", qtd = 1_000.0, valor = 130.0),
    )

    @Test
    fun resumoDaSafra() {
        val s = resumoDoCaderno(safra)
        assertEquals(100.0, s.areaPlantada, 1e-9)
        assertEquals(30_000.0, s.custoTotal, 1e-9)
        assertEquals(300.0, s.custoPorHa!!, 1e-9)
        assertEquals(55.0, s.produtividade!!, 1e-9)
        assertEquals(30_000.0 / 5_500.0, s.custoPorSaca!!, 1e-9)
        assertEquals(490_000.0, s.receita, 1e-9)
        assertEquals(122.5, s.precoMedio!!, 1e-9)
        assertEquals(1_500.0, s.estoque, 1e-9)
        assertEquals(460_000.0, s.resultado!!, 1e-9)
    }

    @Test
    fun cadernoVazioNaoDivideNemInventaResultado() {
        val s = resumoDoCaderno(listOf(r(TipoRegistro.PLANTIO, "2026-11-05", area = 10.0)))
        assertNull(s.custoPorHa)
        assertNull(s.produtividade)
        assertNull(s.precoMedio)
        assertNull(s.resultado)
        assertEquals(0.0, resumoDoCaderno(emptyList()).estoque, 1e-9)
    }

    @Test
    fun safrasComLancamentoEAEmCurso() {
        val antigos = listOf(r(TipoRegistro.PLANTIO, "2025-11-05", safra = 2026))
        assertEquals(listOf(2027, 2026), safrasDoCaderno(antigos, LocalDate.parse("2026-11-14")))
    }

    @Test
    fun plantioConferidoComPortariaEZarc() {
        val cal = CalendarioPlantio(vazio = listOf("2026-08-01", "2026-10-31"), semeadura = listOf("2026-11-01", "2027-02-28"))
        val riscos = "222222000000000000000000000000433222"
        val dentro = conferePlantio(LocalDate.parse("2026-11-14"), cal, riscos, 2026)
        assertEquals(SituacaoCalendario.SEMEADURA, dentro.situacao)
        assertEquals(30, dentro.risco)
        val noVazio = conferePlantio(LocalDate.parse("2026-10-20"), cal, riscos, 2026)
        assertEquals(SituacaoCalendario.VAZIO_SANITARIO, noVazio.situacao)
        assertEquals(0, noVazio.risco)
        // outra safra: o ZARC desta não vale
        assertNull(conferePlantio(LocalDate.parse("2027-11-14"), cal, riscos, 2026).risco)
        assertNull(conferePlantio(LocalDate.parse("2026-11-14"), null, null, null).situacao)
    }

    @Test
    fun planilhaComPontoEVirgulaEDecimalComVirgula() {
        val csv = cadernoEmCsv(listOf(
            r(TipoRegistro.VENDA, "2027-03-20", qtd = 3_000.0, valor = 120.5, descricao = "Cooperativa; filial \"Norte\""),
        ))
        val linhas = csv.trim().lines()
        assertEquals("safra;tipo;data;descricao;area_ha;quantidade;unidade;valor_rs", linhas[0])
        assertEquals("2027;venda;2027-03-20;\"Cooperativa; filial \"\"Norte\"\"\";;3000;;120,5", linhas[1])
    }

    @Test
    fun numerosEDatasDigitados() {
        assertEquals(1234.5, numeroDigitado("1.234,5")!!, 1e-9)
        assertEquals(12.5, numeroDigitado("12.5")!!, 1e-9)
        assertNull(numeroDigitado(""))
        assertNull(numeroDigitado("-3"))
        assertEquals(LocalDate.parse("2026-11-04"), dataDigitada("4/11/2026"))
        assertEquals(LocalDate.parse("2026-11-04"), dataDigitada("2026-11-04"))
        assertNull(dataDigitada("31/02/2026"))
    }
}
