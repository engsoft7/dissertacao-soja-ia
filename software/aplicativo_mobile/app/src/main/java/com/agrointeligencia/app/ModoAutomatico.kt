package com.agrointeligencia.app

import android.graphics.Bitmap
import kotlin.math.roundToInt

// MODO AUTOMÁTICO DO CONTADOR: DESLIGADO ATÉ HAVER MEDIÇÃO NO PARÁ.
//
// Sem o modo automático, o contador de vagens é uma sugestão: o produtor toca
// em "Contar sozinho (teste)" e confere. Com ele, o contador roda assim que a
// foto das vagens chega e o número entra direto, sem conferência, salvo em
// quatro casos, em que a tela pede para conferir antes de guardar o ponto:
//   - a foto está escura (até as partes mais claras, as vagens, ficam escuras);
//   - a foto está borrada (pouca variação de um pixel para o vizinho);
//   - o número dá vagens por planta fora do que uma soja tem;
//   - é a conferência por amostragem: o primeiro ponto automático do talhão e,
//     depois, um em cada cinco. Ela mede o erro em uso e mantém o material de
//     treino crescendo.
//
// Quem liga o modo é o anúncio da API (contador_modelo.json, "modo_automatico"),
// e só junto com um modelo baixado: o que vem embutido no aplicativo, treinado
// com fotos da China, nunca liga. ciclo_retreino.py publica só escreve o anúncio
// ligado com a medição do erro nas fotos de teste do Pará, e com o erro dentro
// do limite. Os limites abaixo também podem vir no anúncio, para serem
// ajustados com as fotos do Pará sem versão nova do aplicativo.

/** Limites do modo automático. Os padrões saíram de uma foto da YOLO POD reduzida a 512 px. */
data class LimitesAutomatico(
    /** Brilho do pixel no percentil 95, de 0 a 255. A foto de exemplo dá 169; escurecida a 30%, 50. */
    val brilhoMin: Double? = null,
    /** Variância do laplaciano a 512 px. A de exemplo dá 1.246; desfocada em 1 px, 86; em 2 px, 10. */
    val nitidezMin: Double? = null,
    val vagensPorPlantaMin: Double? = null,
    val vagensPorPlantaMax: Double? = null,
    /** Um ponto automático em cada tantos é conferido pelo produtor. */
    val conferirACada: Int? = null,
) {
    // O Gson não passa pelo construtor: campo ausente no anúncio vira null, e o padrão vale.
    val brilho: Double get() = brilhoMin ?: 60.0
    val nitidez: Double get() = nitidezMin ?: 30.0
    val minimo: Double get() = vagensPorPlantaMin ?: 5.0
    val maximo: Double get() = vagensPorPlantaMax ?: 150.0
    val aCada: Int get() = (conferirACada ?: 5).coerceAtLeast(1)
}

/** Ligado só com um modelo baixado cujo anúncio disse que pode. */
internal fun modoAutomaticoLigado(baixado: ModeloBaixado?): Boolean =
    baixado != null && baixado.versao > VERSAO_EMBUTIDA && baixado.modo_automatico == true

internal fun limitesDe(baixado: ModeloBaixado?): LimitesAutomatico = baixado?.limites ?: LimitesAutomatico()

data class QualidadeFoto(val brilhoP95: Double, val nitidez: Double)

/** Lado maior em que a qualidade é medida: a nitidez muda com a escala da foto. */
internal const val LADO_QUALIDADE = 512

/**
 * Brilho (percentil 95 da luminância) e nitidez (variância do laplaciano de 4
 * vizinhos) de uma imagem ARGB de [largura] × [altura], já reduzida a
 * [LADO_QUALIDADE] no lado maior.
 */
internal fun qualidadeDaFoto(pixels: IntArray, largura: Int, altura: Int): QualidadeFoto {
    val y = DoubleArray(largura * altura) { i ->
        val p = pixels[i]
        0.299 * ((p shr 16) and 0xFF) + 0.587 * ((p shr 8) and 0xFF) + 0.114 * (p and 0xFF)
    }
    val histograma = IntArray(256)
    y.forEach { histograma[it.roundToInt().coerceIn(0, 255)]++ }
    var acumulado = 0
    var p95 = 255
    for (v in 0..255) {
        acumulado += histograma[v]
        if (acumulado >= 0.95 * y.size) { p95 = v; break }
    }
    var n = 0
    var soma = 0.0
    var soma2 = 0.0
    for (r in 1 until altura - 1) {
        for (c in 1 until largura - 1) {
            val i = r * largura + c
            val l = y[i - largura] + y[i + largura] + y[i - 1] + y[i + 1] - 4 * y[i]
            soma += l
            soma2 += l * l
            n++
        }
    }
    val variancia = if (n == 0) 0.0 else soma2 / n - (soma / n) * (soma / n)
    return QualidadeFoto(p95.toDouble(), variancia)
}

/** A mesma medida, na foto como a tela mostra. */
internal fun qualidadeDaFoto(foto: Bitmap): QualidadeFoto {
    val esc = LADO_QUALIDADE.toDouble() / maxOf(foto.width, foto.height)
    val b = if (esc < 1) Bitmap.createScaledBitmap(foto, maxOf(3, (foto.width * esc).roundToInt()),
                                                   maxOf(3, (foto.height * esc).roundToInt()), true)
            else foto
    val px = IntArray(b.width * b.height)
    b.getPixels(px, 0, b.width, 0, 0, b.width, b.height)
    return qualidadeDaFoto(px, b.width, b.height)
}

/**
 * Por que este ponto precisa da conferência do produtor, ou null se o número
 * do contador pode entrar sozinho. [automaticosAntes] é quantos pontos deste
 * talhão já entraram com o número do contador.
 */
internal fun motivoParaConferir(
    qualidade: QualidadeFoto?,
    vagens: Int,
    arrancadas: Int,
    automaticosAntes: Int,
    lim: LimitesAutomatico,
): String? {
    if (qualidade != null && qualidade.brilhoP95 < lim.brilho)
        return "a foto está escura; com pouca luz o contador erra mais"
    if (qualidade != null && qualidade.nitidez < lim.nitidez)
        return "a foto está borrada; segure firme ou chegue um pouco mais longe"
    if (arrancadas > 0) {
        val porPlanta = vagens.toDouble() / arrancadas
        if (porPlanta < lim.minimo || porPlanta > lim.maximo)
            return "o número dá ${porPlanta.roundToInt()} vagens por planta, fora do comum"
    }
    if (automaticosAntes % lim.aCada == 0)
        return if (automaticosAntes == 0) "o primeiro ponto de cada talhão é conferido por você"
               else "um ponto em cada ${lim.aCada} é conferido por você, para medir o erro do contador"
    return null
}
