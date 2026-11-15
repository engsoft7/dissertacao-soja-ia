package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate
import java.time.LocalDateTime

/**
 * As regras dos alertas. Um erro aqui acorda o produtor de madrugada, repete a
 * mesma notificação a cada 3 horas ou deixa de avisar o preço que ele pediu.
 */
class AlertasCalculoTest {
    private fun t(s: String) = LocalDateTime.parse(s)
    private fun aviso(id: String, fim: String?) = AvisoMeteorologico(id = id, evento = "Chuvas intensas", fim = fim)

    /** 24 horas a partir de [inicio], boas nas horas de [boas]. */
    private fun horas(inicio: String, boas: Set<Int>) = (0 until 24).map { k ->
        val hora = t(inicio).plusHours(k.toLong())
        HoraPulverizacao(hora, if (hora.hour in boas) NivelJanela.BOA else NivelJanela.EVITAR,
                         emptyList(), 25.0, 70.0, 5.0, 0.0)
    }

    @Test
    fun avisoDoInmetNotificaUmaVezEEnquantoValer() {
        val agora = t("2026-11-14T15:00")
        val avisos = listOf(aviso("a", "2026-11-15 12:00:00.0"), aviso("b", "2026-11-14 10:00"), aviso("c", null))
        assertEquals(listOf("a", "c"), avisosParaNotificar(avisos, emptySet(), agora).map { it.id })
        assertEquals(listOf("c"), avisosParaNotificar(avisos, setOf("a"), agora).map { it.id })
        assertEquals(t("2026-10-26T00:00"), horaDoAviso("2026-10-26 00:00"))
        assertNull(horaDoAviso("amanhã"))
    }

    @Test
    fun janelaDePulverizacaoSoDeDiaEUmaPorDia() {
        // boas das 2h às 4h (madrugada) e das 7h às 10h
        val h = horas("2026-11-15T00:00", setOf(2, 3, 4, 7, 8, 9, 10))
        assertEquals(2, janelasBoas(h).size)
        val j = janelaParaNotificar(h, t("2026-11-15T06:30"), ultimoDiaAvisado = null)!!
        assertEquals(t("2026-11-15T07:00"), j.inicio)
        assertEquals(t("2026-11-15T11:00"), j.fim)
        assertEquals(QuandoJanela.HOJE, diaDaJanela(j, t("2026-11-15T06:30")))
        // o mesmo dia já avisado não avisa de novo
        assertNull(janelaParaNotificar(h, t("2026-11-15T06:30"), LocalDate.parse("2026-11-15")))
        // de madrugada não notifica, mesmo com janela
        assertNull(janelaParaNotificar(h, t("2026-11-15T03:00"), null))
    }

    @Test
    fun janelaDeAmanhaSoDentroDoHorizonte() {
        val h = horas("2026-11-14T15:00", setOf(6, 7, 8))
        val j = janelaParaNotificar(h, t("2026-11-14T15:00"), null)!!
        assertEquals(QuandoJanela.AMANHA, diaDaJanela(j, t("2026-11-14T15:00")))
        assertNull(janelaParaNotificar(h, t("2026-11-14T15:00"), null, horizonte = 6))
    }

    @Test
    fun precoAvisaAoChegarEDeNovoSoDepoisDeCair() {
        val agora = t("2026-11-14T10:00")
        fun p(v: Double, data: String = "2026-11-13") = PracaPara("Paragominas", "PA", v, data)
        assertEquals(true to true, precoParaNotificar(p(140.0), 138.0, jaAvisado = false, agora))
        assertEquals(false to true, precoParaNotificar(p(141.0), 138.0, jaAvisado = true, agora))
        assertEquals(false to false, precoParaNotificar(p(136.0), 138.0, jaAvisado = true, agora))
        assertEquals(true to true, precoParaNotificar(p(138.0), 138.0, jaAvisado = false, agora))
        // cotação parada, sem alvo ou de madrugada: nada muda
        assertEquals(false to false, precoParaNotificar(p(140.0, "2026-10-01"), 138.0, false, agora))
        assertEquals(false to false, precoParaNotificar(p(140.0), null, false, agora))
        assertEquals(false to false, precoParaNotificar(p(140.0), 138.0, false, t("2026-11-14T02:00")))
        assertEquals(false to true, precoParaNotificar(null, 138.0, true, agora))
    }
}
