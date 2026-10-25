package com.agrointeligencia.app

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * O contador de vagens rodando de verdade, com a biblioteca nativa do LiteRT,
 * num Android (o emulador do contador-no-emulador.yml). Os testes de unidade
 * conferem as contas em volta do modelo; este confere que o modelo carrega,
 * recebe a entrada no formato certo e devolve o mesmo que o Python.
 *
 * A foto é um dos exemplos do teste da YOLO POD (Xiang et al., 2023, CC BY
 * 4.0) publicados com o modelo, já reduzida a 1024 px e com marcas desenhadas.
 * Os números esperados saem de converte_para_celular.py com os mesmos .tflite:
 * contagem 187,65 (v1) e 131 marcas (v2). A redução da foto no Android não é
 * idêntica à do Pillow, por isso a tolerância.
 */
@RunWith(AndroidJUnit4::class)
class ContadorVagensAparelhoTest {

    private val instrumentacao = InstrumentationRegistry.getInstrumentation()

    private fun exemplo(): Bitmap =
        instrumentacao.context.assets.open("exemplo_vagens.jpg").use { BitmapFactory.decodeStream(it) }

    private fun confere(foto: Bitmap) {
        val r = contaVagens(instrumentacao.targetContext, foto)
        assertNotNull("o modelo não rodou neste aparelho", r)
        assertEquals(188.0, r!!.vagens.toDouble(), 6.0)
        assertEquals(131.0, r.marcas.size.toDouble(), 13.0)
        assertTrue(r.marcas.all { (x, y) -> x in 0f..1f && y in 0f..1f })
    }

    @Test
    fun conta_a_foto_deitada() = confere(exemplo())

    @Test
    fun conta_a_foto_em_pe_igual() {
        val b = exemplo()
        confere(Bitmap.createBitmap(b, 0, 0, b.width, b.height, Matrix().apply { postRotate(-90f) }, true))
    }
}
