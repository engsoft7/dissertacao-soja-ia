package com.agrointeligencia.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import org.tensorflow.lite.Interpreter
import java.nio.ByteBuffer
import java.nio.ByteOrder

// CONTAGEM AUTOMÁTICA DE VAGENS: UMA SUGESTÃO PARA O PRODUTOR CONFERIR.
//
// Dois modelos treinados com a base YOLO POD (Xiang et al., 2023, Plant
// Methods 19:8, licença CC BY 4.0), de plantas arrancadas e deitadas sobre
// pano escuro, na China (pesquisa/09_contagem_por_imagem):
//   v1 dá o número de vagens: erro médio de 5,6% por foto no teste da base;
//   v2 dá as marcas: acha cerca de 6 em cada 10 vagens, e 84% das marcas caem
//   numa vagem.
// Nas fotos de lavouras do Pará o erro ainda não foi medido. Por isso a
// contagem automática não substitui a do produtor: ela preenche o número e as
// marcas, e ele confere tocando na foto.
//
// O caminho da foto aqui é o mesmo que converte_para_celular.py repete nas
// fotos de teste da base para medir o erro depois da conversão; mudar um sem
// o outro invalida aquela conferência.

/** Um dos modelos: arquivo em assets, lado maior da imagem no treino, passo do mapa e limiar das marcas. */
internal class ModeloVagens(val arquivo: String, val lado: Int, val passo: Int, val limiar: Float) {
    /** A entrada é um quadro deitado de tamanho fixo, na proporção 4:3. */
    val largura: Int get() = lado
    val altura: Int get() = lado * 3 / 4
}

internal val MODELO_CONTAGEM = ModeloVagens("contador_vagens_v1.tflite", lado = 768, passo = 8, limiar = 0.05f)
internal val MODELO_MARCAS = ModeloVagens("contador_vagens_v2.tflite", lado = 1024, passo = 4, limiar = 0.02f)

private val MEDIA = floatArrayOf(0.485f, 0.456f, 0.406f)
private val DESVIO = floatArrayOf(0.229f, 0.224f, 0.225f)
private const val FATOR = 100f

/** O que o contador devolve: o número de vagens e as marcas, em fração da foto em pé (0 a 1). */
data class ContagemAutomatica(val vagens: Int, val marcas: List<Pair<Float, Float>>)

/**
 * Tamanho da foto dentro do quadro do modelo. Foto em pé é girada antes, para
 * ficar deitada como as da base; [Triple.third] diz se girou.
 */
internal fun tamanhoNoQuadro(largura: Int, altura: Int, m: ModeloVagens): Triple<Int, Int, Boolean> {
    val girou = altura > largura
    val w = if (girou) altura else largura
    val h = if (girou) largura else altura
    val esc = minOf(m.largura.toDouble() / w, m.altura.toDouble() / h)
    val nw = minOf(m.largura, maxOf(m.passo, Math.round(w * esc).toInt()))
    val nh = minOf(m.altura, maxOf(m.passo, Math.round(h * esc).toInt()))
    return Triple(nw, nh, girou)
}

/**
 * Pixels (ARGB, nw × nh) para a entrada do modelo, 1×3×altura×largura,
 * normalizada como no treino. O que sobra do quadro fica zero, o cinza médio.
 */
internal fun normaliza(pixels: IntArray, nw: Int, nh: Int, m: ModeloVagens): FloatArray {
    val plano = m.largura * m.altura
    val x = FloatArray(3 * plano)
    for (y in 0 until nh) {
        for (xx in 0 until nw) {
            val p = pixels[y * nw + xx]
            val i = y * m.largura + xx
            x[i] = (((p shr 16) and 0xFF) / 255f - MEDIA[0]) / DESVIO[0]
            x[plano + i] = (((p shr 8) and 0xFF) / 255f - MEDIA[1]) / DESVIO[1]
            x[2 * plano + i] = ((p and 0xFF) / 255f - MEDIA[2]) / DESVIO[2]
        }
    }
    return x
}

/**
 * O mapa de densidade que sai do modelo para a contagem (a soma) e as marcas
 * (os máximos locais acima do limiar), só na parte do quadro ocupada pela
 * foto. Marcas em fração da imagem enquadrada.
 */
internal fun interpreta(saida: FloatArray, nw: Int, nh: Int, m: ModeloVagens): Pair<Double, List<Pair<Float, Float>>> {
    val larguraMapa = m.largura / m.passo
    val w = nw / m.passo
    val h = nh / m.passo
    fun d(x: Int, y: Int) = maxOf(0f, saida[y * larguraMapa + x]) / FATOR
    var soma = 0.0
    val marcas = mutableListOf<Pair<Float, Float>>()
    for (y in 0 until h) {
        for (x in 0 until w) {
            val v = d(x, y)
            soma += v
            if (v <= m.limiar) continue
            var maximo = true
            for (dy in -1..1) for (dx in -1..1) {
                val xx = x + dx
                val yy = y + dy
                if (xx in 0 until w && yy in 0 until h && d(xx, yy) > v) maximo = false
            }
            if (maximo) marcas.add(((x + 0.5f) * m.passo / nw) to ((y + 0.5f) * m.passo / nh))
        }
    }
    return soma to marcas
}

/** Das frações da foto girada (90° no sentido horário) para as da foto em pé. */
internal fun desgira(marcas: List<Pair<Float, Float>>, girou: Boolean): List<Pair<Float, Float>> =
    if (!girou) marcas else marcas.map { (u, v) -> v to (1f - u) }

/** Gira, reduz por metades sucessivas e por fim bilinear, como na conferência. */
private fun enquadra(foto: Bitmap, m: ModeloVagens): Triple<IntArray, Pair<Int, Int>, Boolean> {
    val (nw, nh, girou) = tamanhoNoQuadro(foto.width, foto.height, m)
    var b = if (girou) Bitmap.createBitmap(foto, 0, 0, foto.width, foto.height, Matrix().apply { postRotate(90f) }, true)
            else foto
    while (b.width / 2 >= nw && b.height / 2 >= nh) b = Bitmap.createScaledBitmap(b, b.width / 2, b.height / 2, true)
    if (b.width != nw || b.height != nh) b = Bitmap.createScaledBitmap(b, nw, nh, true)
    val pixels = IntArray(nw * nh)
    b.getPixels(pixels, 0, nw, 0, 0, nw, nh)
    return Triple(pixels, nw to nh, girou)
}

private fun roda(context: Context, foto: Bitmap, m: ModeloVagens): Pair<Double, List<Pair<Float, Float>>> {
    val (pixels, tamanho, girou) = enquadra(foto, m)
    val (nw, nh) = tamanho
    val entrada = ByteBuffer.allocateDirect(3 * m.largura * m.altura * 4).order(ByteOrder.nativeOrder())
    entrada.asFloatBuffer().put(normaliza(pixels, nw, nh, m))
    val saida = ByteBuffer.allocateDirect((m.largura / m.passo) * (m.altura / m.passo) * 4).order(ByteOrder.nativeOrder())
    // Lido inteiro para a memória, e não mapeado do pacote: assim funciona
    // mesmo se o empacotamento comprimir o arquivo.
    val bytes = context.assets.open(m.arquivo).use { it.readBytes() }
    val modelo = ByteBuffer.allocateDirect(bytes.size).order(ByteOrder.nativeOrder()).put(bytes)
    modelo.rewind()
    Interpreter(modelo, Interpreter.Options().setNumThreads(4)).use { it.run(entrada, saida) }
    saida.rewind()
    val mapa = FloatArray(saida.capacity() / 4)
    saida.asFloatBuffer().get(mapa)
    val (soma, marcas) = interpreta(mapa, nw, nh, m)
    return soma to desgira(marcas, girou)
}

/**
 * Conta as vagens da foto (já de pé, como sai de carregaFoto). Demora alguns
 * segundos: chame fora da thread principal. Devolve null se o celular não
 * conseguir rodar o modelo, e a tela volta à contagem por toque.
 */
internal fun contaVagens(context: Context, foto: Bitmap): ContagemAutomatica? = try {
    val (vagens, _) = roda(context, foto, MODELO_CONTAGEM)
    val (_, marcas) = roda(context, foto, MODELO_MARCAS)
    ContagemAutomatica(Math.round(vagens).toInt(), marcas)
} catch (_: Exception) {
    null
} catch (_: LinkageError) {
    null
} catch (_: OutOfMemoryError) {
    null
}
