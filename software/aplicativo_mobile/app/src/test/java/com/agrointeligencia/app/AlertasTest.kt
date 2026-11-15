package com.agrointeligencia.app

import android.Manifest
import android.app.NotificationManager
import android.app.job.JobScheduler
import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.time.LocalDateTime

/**
 * Os alertas no Android de verdade (Robolectric): a agenda só existe com algum
 * alerta ligado, e uma rodada da conferência notifica cada coisa uma vez, com
 * o toque abrindo a aba do assunto. As fontes são respostas fixas.
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [35], qualifiers = "pt-rBR")
class AlertasTest {
    private val app = RuntimeEnvironment.getApplication()
    private val prefs = app.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE)
    private val agora = LocalDateTime.parse("2026-11-14T06:30")

    @Before
    fun limpa() {
        prefs.edit().clear().commit()
        shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
    }

    @Test
    fun agendaSoComAlgumAlertaLigado() {
        val agenda = app.getSystemService(JobScheduler::class.java)
        Alertas.atualizaAgenda(app, prefs)
        assertNull(agenda.getPendingJob(Alertas.JOB_ID))
        prefs.edit().putBoolean(PREF_ALERTA_PRECO, true).commit()
        Alertas.atualizaAgenda(app, prefs)
        val job = agenda.getPendingJob(Alertas.JOB_ID)!!
        assertTrue(job.isPeriodic && job.isPersisted)
        assertEquals(3 * 60 * 60 * 1000L, job.intervalMillis)
        prefs.edit().putBoolean(PREF_ALERTA_PRECO, false).commit()
        Alertas.atualizaAgenda(app, prefs)
        assertNull(agenda.getPendingJob(Alertas.JOB_ID))
    }

    /** Boas das 7h às 10h (25 °C, 70%, vento de ~5 km/h na lavoura); fora disso, 35 °C. */
    private fun previsaoComJanela(): PrevisaoTempo {
        val horas = (0 until 48).map { LocalDateTime.parse("2026-11-14T00:00").plusHours(it.toLong()) }
        return PrevisaoTempo(
            timezone = "America/Belem",
            hourly = TempoHorario(
                time = horas.map { it.toString() },
                temperature_2m = horas.map { if (it.hour in 7..10) 25.0 else 35.0 },
                relative_humidity_2m = horas.map { 70.0 },
                precipitation = horas.map { 0.0 },
                wind_speed_10m = horas.map { 7.0 },
            )
        )
    }

    private val fontes = FontesDosAlertas(
        avisos = {
            AvisosResponse(disponivel = true, avisos = listOf(AvisoMeteorologico(
                id = "inmet-1", evento = "Chuvas Intensas", severidade = "Perigo Potencial",
                inicio = "2026-11-14 10:00", fim = "2026-11-15 10:00")))
        },
        previsao = { previsaoComJanela() },
        mercado = { MercadoResponse(pracas_para = listOf(PracaPara("Paragominas", "PA", 133.12, "2026-11-13"))) },
        agora = { agora },
    )

    @Test
    fun conferenciaNotificaCadaCoisaUmaVez() = runBlocking {
        prefs.edit().putBoolean(PREF_ALERTA_INMET, true).putBoolean(PREF_ALERTA_PULVERIZACAO, true)
            .putBoolean(PREF_ALERTA_PRECO, true).putFloat(PREF_ALERTA_PRECO_ALVO, 130f)
            .putString(PREF_ALERTA_PRECO_PRACA, "Paragominas").commit()
        Alertas.guardaContexto(prefs, SEDES_MUNICIPAIS["Paragominas"], "PA")

        confereAlertas(app, fontes)
        val gerente = shadowOf(app.getSystemService(NotificationManager::class.java))
        val textos = gerente.allNotifications.map { it.extras.getCharSequence("android.title")?.toString() }
        assertEquals(3, textos.size)
        assertTrue(textos.toString(), textos.contains("Aviso do INMET: Chuvas Intensas (Perigo Potencial)"))
        assertTrue(textos.toString(), textos.contains("Janela boa para pulverizar"))
        assertTrue(textos.toString(), textos.contains("Soja a R$ 133,12 em Paragominas"))
        val janela = gerente.allNotifications.first { it.extras.getCharSequence("android.title")?.toString() == "Janela boa para pulverizar" }
        assertEquals("Hoje, das 7h às 11h, em Paragominas. Confira a bula e o vento no local antes de aplicar.",
                     janela.extras.getCharSequence("android.text").toString())

        // A rodada seguinte, com as mesmas respostas, não repete nada.
        confereAlertas(app, fontes)
        assertEquals(3, gerente.allNotifications.size)
    }

    @Test
    fun semPermissaoNaoNotificaNemQuebra() = runBlocking {
        shadowOf(app).denyPermissions(Manifest.permission.POST_NOTIFICATIONS)
        prefs.edit().putBoolean(PREF_ALERTA_INMET, true).commit()
        Alertas.guardaContexto(prefs, SEDES_MUNICIPAIS["Paragominas"], "PA")
        confereAlertas(app, fontes)
        val gerente = shadowOf(app.getSystemService(NotificationManager::class.java))
        assertEquals(0, gerente.allNotifications.size)
        // Com a permissão dada depois, o aviso que ainda vale chega.
        shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
        confereAlertas(app, fontes)
        assertEquals(1, gerente.allNotifications.size)
    }

    @Test
    fun precoDigitadoComVirgulaOuPonto() {
        assertEquals(138.5, precoDigitado("138,50")!!, 1e-9)
        assertEquals(138.5, precoDigitado("138.5")!!, 1e-9)
        assertEquals(1234.56, precoDigitado("R$ 1.234,56")!!, 1e-9)
        assertNull(precoDigitado("abc"))
        assertNull(precoDigitado("0"))
    }
}
