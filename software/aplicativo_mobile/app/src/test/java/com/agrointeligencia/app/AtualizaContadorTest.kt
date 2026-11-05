package com.agrointeligencia.app

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Regras de AtualizaContador.kt: quando o aplicativo aceita um modelo anunciado. */
class AtualizaContadorTest {

    private val sha = "a".repeat(64)

    private fun manifesto(
        versao: Int = 2,
        url: String = ORIGEM_PERMITIDA + "0123456789abcdef0123456789abcdef01234567/celular/",
        appMinimo: Int? = 23,
        arquivos: List<String> = listOf("contador_vagens_v1.tflite", "contador_vagens_v2.tflite"),
        hash: String = sha,
        bytes: Long = 3_500_000,
    ) = ManifestoContador(versao, appMinimo, arquivos.associateWith { ArquivoModelo(url + it, hash, bytes) })

    @Test
    fun aceitaVersaoNovaDoRepositorio() {
        assertTrue(precisaBaixar(manifesto(), versaoLocal = 1, versaoApp = 23))
    }

    @Test
    fun recusaOQueNaoServe() {
        assertFalse("mesma versão", precisaBaixar(manifesto(versao = 1), 1, 23))
        assertFalse("versão mais velha", precisaBaixar(manifesto(versao = 2), 3, 23))
        assertFalse("aplicativo antigo demais", precisaBaixar(manifesto(appMinimo = 30), 1, 23))
        assertFalse("falta um arquivo", precisaBaixar(manifesto(arquivos = listOf("contador_vagens_v1.tflite")), 1, 23))
        assertFalse("outro endereço", precisaBaixar(manifesto(url = "https://exemplo.com/"), 1, 23))
        assertFalse("http", precisaBaixar(manifesto(url = "http://raw.githubusercontent.com/engsoft7/dissertacao-soja-ia/" +
            "0123456789abcdef0123456789abcdef01234567/celular/"), 1, 23))
        assertFalse("branch em vez de commit", precisaBaixar(manifesto(url = ORIGEM_PERMITIDA + "main/celular/"), 1, 23))
        assertFalse("sobe de pasta", precisaBaixar(manifesto(url = ORIGEM_PERMITIDA +
            "0123456789abcdef0123456789abcdef01234567/../../outro/"), 1, 23))
        assertFalse("resumo inválido", precisaBaixar(manifesto(hash = "xyz"), 1, 23))
        assertFalse("tamanho absurdo", precisaBaixar(manifesto(bytes = 10), 1, 23))
        assertFalse("sem anúncio", precisaBaixar(null, 1, 23))
    }

    @Test
    fun resumoSha256() {
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", sha256Hex("abc".toByteArray()))
    }

    /** O anúncio da API descreve os modelos que vêm no aplicativo e, por isso, não pede download. */
    @Test
    fun anuncioDaApiConfereComOsAssets() {
        val m = Gson().fromJson(File("../../api_backend/contador_modelo.json").readText(), ManifestoContador::class.java)
        assertEquals(VERSAO_EMBUTIDA, m.versao)
        assertFalse(precisaBaixar(m, VERSAO_EMBUTIDA, BuildConfig.VERSION_CODE))
        for ((nome, a) in m.arquivos!!) {
            val bytes = File("src/main/assets/$nome").readBytes()
            assertEquals(nome, a.sha256, sha256Hex(bytes))
            assertEquals(nome, a.bytes, bytes.size.toLong())
            assertTrue(nome, a.url.startsWith(ORIGEM_PERMITIDA))
        }
    }
}
