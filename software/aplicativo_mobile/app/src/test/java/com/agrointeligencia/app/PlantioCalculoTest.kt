package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate

/**
 * As contas da janela de plantio. Uma data errada aqui diria ao produtor que
 * ele pode semear num dia em que a portaria proíbe, ou que está no ZARC quando
 * não está, e o Proagro não cobre.
 */
class PlantioCalculoTest {
    private fun d(s: String) = LocalDate.parse(s)

    @Test
    fun decendiosAtravessamOAnoEOFevereiro() {
        assertEquals(d("2026-10-01") to d("2026-10-10"), decendio(28, 2026))
        assertEquals(d("2026-12-21") to d("2026-12-31"), decendio(36, 2026))
        assertEquals(d("2027-01-01") to d("2027-01-10"), decendio(1, 2026))
        assertEquals(d("2027-02-21") to d("2027-02-28"), decendio(6, 2026))
        assertEquals(d("2028-02-21") to d("2028-02-29"), decendio(6, 2027))
    }

    @Test
    fun janelasJuntamDecendiosSeguidosDeMesmoRisco() {
        val r = CharArray(36) { '0' }
        for (i in listOf(34, 35, 36, 1, 2)) r[i - 1] = '2'
        r[3 - 1] = '3'
        val j = janelasZarc(String(r), 2026)
        assertEquals(listOf(JanelaZarc(d("2026-12-01"), d("2027-01-20"), 20),
                            JanelaZarc(d("2027-01-21"), d("2027-01-31"), 30)), j)
        assertEquals(20, riscoNoDia(String(r), 2026, d("2026-12-25")))
        assertEquals(30, riscoNoDia(String(r), 2026, d("2027-01-25")))
        assertEquals(0, riscoNoDia(String(r), 2026, d("2026-11-14")))
    }

    @Test
    fun sequenciaComTamanhoErradoNaoViraJanela() {
        assertEquals(emptyList<JanelaZarc>(), janelasZarc("222", 2026))
    }

    @Test
    fun situacaoDoDiaNoCalendario() {
        val c = CalendarioPlantio(vazio = listOf("2026-06-08", "2026-09-06"),
                                  semeadura = listOf("2026-09-07", "2027-01-07"))
        assertEquals(SituacaoCalendario.VAZIO_SANITARIO, situacaoNoDia(c, d("2026-07-01")))
        assertEquals(SituacaoCalendario.SEMEADURA, situacaoNoDia(c, d("2026-11-14")))
        assertEquals(SituacaoCalendario.SEMEADURA, situacaoNoDia(c, d("2027-01-07")))
        assertEquals(SituacaoCalendario.FORA_DO_CALENDARIO, situacaoNoDia(c, d("2027-01-08")))
        assertNull(situacaoNoDia(null, d("2026-11-14")))
    }

    @Test
    fun janelaDoZarcCortadaPeloCalendario() {
        val j = JanelaZarc(d("2026-12-01"), d("2027-01-20"), 20)
        assertEquals(JanelaZarc(d("2026-12-01"), d("2027-01-07"), 20),
                     dentroDoCalendario(j, d("2026-09-07") to d("2027-01-07")))
        assertNull(dentroDoCalendario(JanelaZarc(d("2027-01-11"), d("2027-01-20"), 20),
                                      d("2026-09-07") to d("2027-01-07")))
    }

    @Test
    fun proximaJanelaZarcIgnoraAsQueJaPassaram() {
        val js = listOf(JanelaZarc(d("2026-10-01"), d("2026-10-31"), 20), JanelaZarc(d("2026-11-11"), d("2026-11-30"), 30))
        assertEquals(js[1], proximaJanelaZarc(js, d("2026-11-05")))
        assertNull(proximaJanelaZarc(js, d("2026-11-05"), riscoMaximo = 20))
        assertEquals(2026, anoInicialDaSafra("2026/2027"))
    }
}
