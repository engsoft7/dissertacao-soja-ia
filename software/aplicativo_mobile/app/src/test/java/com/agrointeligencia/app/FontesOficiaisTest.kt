package com.agrointeligencia.app

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** As fontes da tela Sobre e as da descrição da loja (textos_da_loja.txt) são as mesmas, todas em https. */
class FontesOficiaisTest {

    private val loja = File("../loja/textos_da_loja.txt").readText()

    @Test
    fun todaFonteDoAppEstaNaLoja() {
        for (f in FONTES_OFICIAIS + OUTRAS_FONTES) {
            assertTrue(f.url, f.url.startsWith("https://"))
            assertTrue("${f.url} falta em textos_da_loja.txt", loja.contains(f.url))
        }
    }

    @Test
    fun todaFonteOficialDaLojaEstaNoApp() {
        val trecho = loja.substringAfter("FONTES OFICIAIS").substringBefore("OUTRAS FONTES")
        val urls = Regex("https://\\S+").findAll(trecho).map { it.value }.toList()
        assertTrue("nenhum link oficial na loja", urls.isNotEmpty())
        for (u in urls) assertTrue("$u falta em FONTES_OFICIAIS", FONTES_OFICIAIS.any { it.url == u })
    }

    @Test
    fun avisoDeNaoAfiliacao() {
        assertTrue(AVISO_NAO_GOVERNO.contains("não é um aplicativo do governo"))
        assertTrue(loja.contains("NÃO é um aplicativo do governo"))
    }
}
