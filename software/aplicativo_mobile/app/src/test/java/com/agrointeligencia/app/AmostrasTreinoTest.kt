package com.agrointeligencia.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.io.File

/**
 * Até o 2.10.0, o app guardava fotos marcadas para treinar o contador. A versão
 * nova apaga o que ficou, sem tocar nos arquivos do caderno e do relatório, e
 * mantém a conta da colheita que a comparação da tela usa.
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class AmostrasTreinoTest {
    private val app = RuntimeEnvironment.getApplication()

    @Test
    fun apagaAsFotosMarcadasDasVersoesAntigas() {
        val pasta = File(app.filesDir, "amostras_treino").apply { mkdirs() }
        File(pasta, "vagem_20261101_101500.jpg").writeText("foto")
        File(pasta, "vagem_20261101_101500.json").writeText("{}")
        File(pasta, "talhoes.json").writeText("{\"talhoes\":[]}")
        val exportar = File(app.cacheDir, "exportar").apply { mkdirs() }
        val zip = File(exportar, "fotos_marcadas_2026-11-01.zip").apply { writeText("zip") }
        val doCaderno = File(exportar, "caderno_da_safra.csv").apply { writeText("caderno") }

        assertEquals(4, apagaAmostrasAntigas(app))
        assertFalse("a pasta das fotos marcadas sai", pasta.exists())
        assertFalse("o .zip de exportação antigo sai", zip.exists())
        assertTrue("o arquivo do caderno fica", doCaderno.exists())
        assertEquals("sem nada da época, não apaga nada", 0, apagaAmostrasAntigas(app))
    }

    @Test
    fun colheitaEmKgPorHectare() {
        assertEquals(3600.0, colheitaKgHa(600.0, 10.0)!!, 1e-9)
        assertNull("sem área", colheitaKgHa(600.0, null))
        assertNull("sem colheita", colheitaKgHa(null, 10.0))
        assertNull("zero", colheitaKgHa(0.0, 10.0))
    }
}
