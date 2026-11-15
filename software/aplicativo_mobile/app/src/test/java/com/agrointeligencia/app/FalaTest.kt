package com.agrointeligencia.app

import android.speech.tts.TextToSpeech
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.time.LocalDateTime

/**
 * A leitura em voz alta: o texto chega à voz do Android mesmo pedido antes de
 * ela ficar pronta, para quando se pede, e as frases não têm abreviações que a
 * voz lê mal.
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [35], qualifiers = "pt-rBR")
class FalaTest {
    private val app = RuntimeEnvironment.getApplication()

    @Test
    fun textoPedidoAntesDaVozFicarProntaEhLido() {
        val leitor = Leitor(app)
        leitor.fala("Paragominas. Produtividade.")
        assertTrue(leitor.falando)
        leitor.onInit(TextToSpeech.SUCCESS)
        assertEquals("Paragominas. Produtividade.", shadowOf(leitor.tts).lastSpokenText)
        leitor.para()
        assertFalse(leitor.falando)
        leitor.encerra()
    }

    @Test
    fun semVozNoAparelhoAvisa() {
        val leitor = Leitor(app)
        leitor.onInit(TextToSpeech.ERROR)
        assertTrue(leitor.indisponivel)
        assertFalse(leitor.falando)
    }

    @Test
    fun resumoFaladoSemAbreviacoes() {
        val r = Relatorio("AgroInteligência · Paragominas (PA)", "Resumo de 14/11/2026", listOf(SecaoRelatorio(
            "Produtividade",
            listOf("Esperada na safra 2027: 3.150 kg/ha (cerca de 53 sacas por hectare), com erro típico de ± 420 kg/ha."))),
            "rodapé")
        assertEquals("Paragominas (PA). Produtividade. Esperada na safra 2027: 3.150 quilos por hectare (cerca de 53 " +
                     "sacas por hectare), com erro típico de mais ou menos 420 quilos por hectare.", falaDoResumo(app, r))
    }

    @Test
    fun tempoFalado() {
        val horas = (0 until 48).map { LocalDateTime.parse("2026-11-14T00:00").plusHours(it.toLong()) }
        val p = PrevisaoTempo(
            current = TempoAtual(time = "2026-11-14T06:00", temperature_2m = 24.6, relative_humidity_2m = 81.0,
                                 wind_speed_10m = 7.0, weather_code = 2),
            hourly = TempoHorario(
                time = horas.map { it.toString() },
                temperature_2m = horas.map { if (it.hour in 7..10) 25.0 else 35.0 },
                relative_humidity_2m = horas.map { 70.0 },
                precipitation = horas.map { 0.0 },
                wind_speed_10m = horas.map { 7.0 },
            ),
            daily = TempoDiario(time = listOf("2026-11-14"), temperature_2m_max = listOf(33.2),
                                temperature_2m_min = listOf(22.4), precipitation_probability_max = listOf(40.0)),
        )
        val texto = falaDoTempo(app, p, null, "Paragominas", LocalDateTime.parse("2026-11-14T06:00"))!!
        assertTrue(texto, texto.startsWith("Tempo em Paragominas agora: 25 graus, parcialmente nublado, umidade de 81 " +
                                           "por cento e vento na lavoura de 5 quilômetros por hora."))
        assertTrue(texto, texto.contains("Evite pulverizar nesta hora."))
        assertTrue(texto, texto.contains("Próxima janela boa para pulverizar: hoje, das 7 às 11 horas."))
        assertTrue(texto, texto.endsWith("Hoje, máxima de 33 e mínima de 22 graus, com 40 por cento de chance de chuva."))
    }
}
