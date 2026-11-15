package com.agrointeligencia.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.time.LocalDateTime

/**
 * Os textos da tela Tempo, de strings.xml: em português, os mesmos de antes
 * da tradução, e em inglês, com os limites da conta (TempoCalculo.kt) nos
 * números. Os testes em inglês não passam por Formatos.doIdioma, que valeria
 * para os testes seguintes.
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [35], qualifiers = "pt-rBR")
class TempoTextosTest {
    private val app get() = RuntimeEnvironment.getApplication()

    private val tempestade = AvisoMeteorologico(id = "1", evento = "Tempestade", severidade = "Perigo Potencial")
    private val outraTempestade = AvisoMeteorologico(id = "2", evento = "Tempestade", severidade = "Perigo")
    private val chuva = AvisoMeteorologico(id = "3", evento = "Chuvas Intensas")

    @Test
    fun motivosComOsLimitesDaConta() {
        assertEquals("umidade abaixo de 60%", textoDoMotivo(app, MotivoHora.UMIDADE_BAIXA))
        assertEquals("temperatura acima de 30 °C", textoDoMotivo(app, MotivoHora.CALOR))
        assertEquals("vento entre 8 e 10 km/h: só com ponta antideriva", textoDoMotivo(app, MotivoHora.VENTO_ANTIDERIVA))
        assertEquals("chuva prevista nas 2 horas seguintes", textoDoMotivo(app, MotivoHora.CHUVA_LOGO))
        assertEquals("chuva prevista nesta hora", textoDoMotivo(app, MotivoHora.CHUVA_NA_HORA))
    }

    @Test
    fun descricoesDirecaoEUv() {
        assertEquals("Nublado", app.getString(descricaoTempo(3)))
        assertEquals("Trovoada com granizo", app.getString(descricaoTempo(99)))
        assertEquals("NE", app.getString(direcaoVento(48.0)!!))
        assertEquals("O", app.getString(direcaoVento(-90.0)!!))
        assertEquals("muito alto", app.getString(categoriaUv(9.15)!!))
    }

    @Test
    fun avisosDoMesmoEventoEntramUmaVezNoResumo() {
        // Dois avisos do mesmo evento, com outro nível, apareciam como
        // "tempestade, tempestade" (Teste Premium de 14/11/2026).
        assertEquals("1 aviso do INMET: tempestade", resumoDosAvisos(app, listOf(tempestade)))
        assertEquals("2 avisos do INMET: tempestade", resumoDosAvisos(app, listOf(tempestade, outraTempestade)))
        assertEquals("3 avisos do INMET: tempestade, chuvas intensas",
                     resumoDosAvisos(app, listOf(tempestade, outraTempestade, chuva)))
    }

    @Test
    fun horaEJanelaEmPortugues() {
        val agora = LocalDateTime.parse("2026-10-25T17:45")
        assertEquals("7h", horaCurta(app, agora.withHour(7)))
        assertEquals("Perigo Potencial", nomeDoInmet(app, "Perigo Potencial"))
        // Um evento que o app não conhece fica como o INMET publica.
        assertEquals("Ressaca", nomeDoInmet(app, "Ressaca"))
    }

    @Test
    @Config(qualifiers = "en")
    fun emIngles() {
        assertEquals("humidity below 60%", textoDoMotivo(app, MotivoHora.UMIDADE_BAIXA))
        assertEquals("wind between 8 and 10 km/h: only with drift-reducing nozzles",
                     textoDoMotivo(app, MotivoHora.VENTO_ANTIDERIVA))
        assertEquals("Overcast", app.getString(descricaoTempo(3)))
        assertEquals("W", app.getString(direcaoVento(-90.0)!!))
        assertEquals("SW", app.getString(direcaoVento(225.0)!!))
        assertEquals("very high", app.getString(categoriaUv(9.15)!!))
        assertEquals("7:00", horaCurta(app, LocalDateTime.parse("2026-10-26T07:00")))
        assertEquals("1 INMET warning: storm", resumoDosAvisos(app, listOf(tempestade)))
        assertEquals("3 INMET warnings: storm, heavy rain", resumoDosAvisos(app, listOf(tempestade, outraTempestade, chuva)))
        assertEquals("Potential danger", nomeDoInmet(app, "Perigo Potencial"))
        assertEquals("Ressaca", nomeDoInmet(app, "Ressaca"))
    }
}
