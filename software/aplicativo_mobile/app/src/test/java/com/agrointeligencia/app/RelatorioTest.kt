package com.agrointeligencia.app

import android.graphics.BitmapFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.time.LocalDate

/**
 * O resumo para compartilhar: o texto de cada linha (os mesmos números das
 * telas) e a imagem no tamanho que o WhatsApp mostra inteira.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35])
class RelatorioTest {
    private val app = RuntimeEnvironment.getApplication()
    private val dados = DadosDoRelatorio(
        municipio = "Paragominas", uf = "PA", hoje = LocalDate.of(2026, 11, 14),
        projecao = PrevisaoHistorico(2027, 3150.0, 0.0, 420.0),
        ultimoReal = PrevisaoHistorico(2025, 3300.0, 3310.0, 0.0),
        praca = PracaPara("Paragominas", "PA", 133.12, "2026-11-13"),
        precoUsado = 133.12, resultadoPorHa = 1234.5, sacasPorHa = 52.5,
        plantioCalendario = "Semeadura permitida até 28/02/2027",
        plantioZarc = "ZARC hoje: risco de 30% (Grupo II, AD3)", plantioRegiao = "II",
        caderno = resumoDoCaderno(listOf(
            RegistroCaderno(1, 2027, TipoRegistro.PLANTIO, "2026-11-12", area = 120.0),
            RegistroCaderno(2, 2027, TipoRegistro.INSUMO, "2026-11-05", valor = 33_600.0))),
        safraDoCaderno = 2027,
    )

    @Test
    fun linhasDoResumo() {
        val r = montaRelatorio(app, dados)
        assertEquals("AgroInteligência · Paragominas (PA)", r.titulo)
        assertEquals("Resumo de 14/11/2026", r.subtitulo)
        assertEquals(listOf("Produtividade", "Preço e resultado", "Janela de plantio", "Caderno da safra 2026/27"),
                     r.secoes.map { it.titulo })
        assertEquals("Esperada na safra 2027: 3.150 kg/ha (cerca de 53 sacas por hectare), com erro típico de ± 420 kg/ha.",
                     r.secoes[0].linhas[0])
        assertEquals("Último dado do IBGE, safra 2025: 3.310 kg/ha.", r.secoes[0].linhas[1])
        assertEquals("Saca em Paragominas: R$ 133,12 (Agrolink, 13/11).", r.secoes[1].linhas[0])
        assertEquals("Resultado estimado: R$ 1.234,50 por hectare, com 52,5 sacas por hectare a R$ 133,12.",
                     r.secoes[1].linhas[1])
        assertEquals("Semeadura permitida até 28/02/2027 (Região II do estado na portaria).", r.secoes[2].linhas[0])
        assertEquals("ZARC hoje: risco de 30% (Grupo II, AD3).", r.secoes[2].linhas[1])
        assertEquals("Área plantada: 120,0 ha; custos lançados: R$ 33.600,00.", r.secoes[3].linhas[0])
    }

    @Test
    fun semDadosFicamSoOTituloEORodape() {
        val r = montaRelatorio(app, DadosDoRelatorio("Sorriso", "MT", LocalDate.of(2026, 11, 14)))
        assertTrue(r.secoes.isEmpty())
        assertTrue(r.rodape.contains("não é um aplicativo do governo"))
    }

    @Test
    fun imagemNoTamanhoQueOWhatsappMostraInteira() {
        val arquivo = geraImagem(app, montaRelatorio(app, dados))
        val opcoes = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(arquivo.path, opcoes)
        assertEquals(1080, opcoes.outWidth)
        assertEquals(1350, opcoes.outHeight)
    }
}
