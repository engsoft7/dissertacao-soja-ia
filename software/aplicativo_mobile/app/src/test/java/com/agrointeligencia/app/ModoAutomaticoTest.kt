package com.agrointeligencia.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Regras de ModoAutomatico.kt: quando o número do contador entra sem conferência. */
class ModoAutomaticoTest {

    private val lim = LimitesAutomatico()
    private val boa = QualidadeFoto(brilhoP95 = 169.0, nitidez = 1246.0)

    private fun baixado(versao: Int, modo: Boolean?) = ModeloBaixado(versao, emptyMap(), null, modo)

    @Test
    fun soLigaComModeloBaixadoQueOAnuncioLiberou() {
        assertFalse("sem modelo baixado", modoAutomaticoLigado(null))
        assertFalse("o embutido nunca liga", modoAutomaticoLigado(baixado(VERSAO_EMBUTIDA, true)))
        assertFalse("anúncio sem o campo", modoAutomaticoLigado(baixado(2, null)))
        assertFalse("anúncio desligado", modoAutomaticoLigado(baixado(2, false)))
        assertTrue(modoAutomaticoLigado(baixado(2, true)))
    }

    @Test
    fun limitesAusentesNoAnuncioValemOPadrao() {
        val l = LimitesAutomatico(nitidezMin = 80.0)
        assertEquals(80.0, l.nitidez, 0.0)
        assertEquals(60.0, l.brilho, 0.0)
        assertEquals(5, l.aCada)
        assertEquals(1, LimitesAutomatico(conferirACada = 0).aCada)
    }

    @Test
    fun fotoLisaEBorradaEXadrezNitida() {
        val lisa = IntArray(64 * 48) { 0xFF808080.toInt() }
        assertEquals(0.0, qualidadeDaFoto(lisa, 64, 48).nitidez, 1e-9)
        val xadrez = IntArray(64 * 48) { i -> if ((i % 64 + i / 64) % 2 == 0) 0xFFFFFFFF.toInt() else 0xFF000000.toInt() }
        assertTrue(qualidadeDaFoto(xadrez, 64, 48).nitidez > 1000)
    }

    @Test
    fun brilhoNoPercentil95() {
        // 90% preto e 10% branco: o percentil 95 cai no branco.
        val px = IntArray(100) { i -> if (i < 90) 0xFF000000.toInt() else 0xFFFFFFFF.toInt() }
        assertEquals(255.0, qualidadeDaFoto(px, 10, 10).brilhoP95, 0.0)
        val escura = IntArray(100) { 0xFF202020.toInt() }
        assertEquals(32.0, qualidadeDaFoto(escura, 10, 10).brilhoP95, 0.0)
    }

    @Test
    fun pedeConferenciaNaFotoRuimNoNumeroEstranhoENaAmostragem() {
        // 200 vagens em 5 plantas, segundo ponto automático: entra sozinho.
        assertNull(motivoParaConferir(boa, 200, 5, automaticosAntes = 1, lim = lim))
        assertNotNull("escura", motivoParaConferir(boa.copy(brilhoP95 = 40.0), 200, 5, 1, lim))
        assertNotNull("borrada", motivoParaConferir(boa.copy(nitidez = 10.0), 200, 5, 1, lim))
        assertNotNull("poucas vagens", motivoParaConferir(boa, 10, 5, 1, lim))
        assertNotNull("vagens demais", motivoParaConferir(boa, 1000, 5, 1, lim))
        assertNotNull("primeiro do talhão", motivoParaConferir(boa, 200, 5, 0, lim))
        assertNull(motivoParaConferir(boa, 200, 5, 4, lim))
        assertNotNull("um em cada cinco", motivoParaConferir(boa, 200, 5, 5, lim))
        assertNull("sem medida da foto, vale o resto", motivoParaConferir(null, 200, 5, 1, lim))
    }
}
