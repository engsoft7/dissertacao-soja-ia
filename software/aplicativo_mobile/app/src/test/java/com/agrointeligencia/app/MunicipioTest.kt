package com.agrointeligencia.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

/**
 * Escolha do município: o guardado, o mais próximo pelo GPS e a busca da lista.
 * Com Robolectric em pt-BR: a frase do mais próximo vem de strings.xml.
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [35], qualifiers = "pt-rBR")
class MunicipioTest {
    private val app = RuntimeEnvironment.getApplication()

    private val todos = SEDES_MUNICIPAIS.keys.sorted()

    @Test
    fun distanciaConhecida() {
        // Marabá a Paragominas, em linha reta: cerca de 330 km.
        val m = SEDES_MUNICIPAIS.getValue("Marabá")
        val p = SEDES_MUNICIPAIS.getValue("Paragominas")
        val d = distanciaKm(m.lat, m.lon, p.lat, p.lon)
        assertTrue("$d", d in 320.0..340.0)
        assertEquals(0.0, distanciaKm(p.lat, p.lon, p.lat, p.lon), 1e-9)
    }

    @Test
    fun maisProximoNaSede() {
        val p = SEDES_MUNICIPAIS.getValue("Paragominas")
        val r = municipioMaisProximo(p.lat + 0.02, p.lon - 0.02, todos)!!
        assertEquals("Paragominas", r.nome)
        assertTrue(r.distanciaKm < 5)
    }

    @Test
    fun soEntramOsDaLista() {
        // Na sede de Paragominas, mas a lista não tem Paragominas: vai para o vizinho mais perto.
        val p = SEDES_MUNICIPAIS.getValue("Paragominas")
        val r = municipioMaisProximo(p.lat, p.lon, todos - "Paragominas")!!
        assertTrue(r.nome != "Paragominas")
        assertNull(municipioMaisProximo(p.lat, p.lon, listOf("Belém")))
        assertNull(municipioMaisProximo(p.lat, p.lon, emptyList()))
    }

    @Test
    fun fraseDizQuandoEstaLonge() {
        val perto = fraseDoMaisProximo(app, MunicipioProximo("Paragominas", 12.4), 38)
        assertTrue(perto, perto.contains("Paragominas, a 12 km da sede"))
        // Belém fica a uns 114 km de Tomé-Açu, a sede mais próxima da lista.
        val b = municipioMaisProximo(-1.4558, -48.5039, todos)!!
        val longe = fraseDoMaisProximo(app, b, 38)
        assertTrue(longe, longe.startsWith("O mais próximo de você é"))
        assertTrue(longe, longe.contains("38 municípios"))
    }

    @Test
    fun buscaSemAcento() {
        assertEquals(listOf("Marabá"), filtraMunicipios(todos, "maraba"))
        assertEquals(listOf("Pau D'Arco"), filtraMunicipios(todos, "pau darco"))
        assertEquals(listOf("Pau D'Arco"), filtraMunicipios(todos, "PAU D'ARCO"))
        assertEquals(todos, filtraMunicipios(todos, "  "))
        assertTrue(filtraMunicipios(todos, "xyz").isEmpty())
    }

    @Test
    fun buscaPoeQuemComecaPrimeiro() {
        // Marabá começa com "ma" e vem antes dos que só contêm "ma" no meio.
        assertEquals(listOf("Marabá", "Cumaru do Norte", "Rio Maria", "Santa Maria das Barreiras", "Tucumã"),
                     filtraMunicipios(todos, "ma"))
    }

    @Test
    fun guardadoSoValeSeEstiverNaLista() {
        assertEquals("Marabá", municipioGuardadoValido(todos, "Marabá"))
        assertNull(municipioGuardadoValido(todos, "Belém"))
        assertNull(municipioGuardadoValido(todos, null))
        // Lista ainda não carregada: a escolha guardada vale até a lista chegar.
        assertEquals("Marabá", municipioGuardadoValido(emptyList(), "Marabá"))
    }
}
