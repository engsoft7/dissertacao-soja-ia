package com.agrointeligencia.app

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import com.google.gson.GsonBuilder
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

// FOTOS MARCADAS: O MATERIAL PARA TREINAR A CONTAGEM AUTOMÁTICA.
//
// Cada toque do produtor numa vagem ou planta é exatamente a marcação que um
// modelo de contagem por pontos precisa para aprender. Em vez de jogar isso
// fora, o app guarda a foto (já de pé e reduzida, a mesma que foi tocada) e
// um JSON com os pontos em pixels. Fica só no celular, em armazenamento
// privado do app; sai dele apenas quando o produtor exporta o .zip e escolhe
// para onde mandar. Nada é enviado sozinho.
//
// Só entra foto com ao menos uma marca: foto sem marcação não ensina nada.

private const val PASTA = "amostras_treino"

/** Uma foto marcada, como vai no JSON ao lado da imagem. */
data class AnotacaoFoto(
    val imagem: String,
    val largura: Int,
    val altura: Int,
    /** "planta" (foto da linha) ou "vagem" (plantas arrancadas). */
    val classe: String,
    /** Centro de cada marca, em pixels da imagem: [x, y]. */
    val pontos: List<List<Int>>,
    /** O número que ficou no campo da tela; se difere dos pontos, o produtor corrigiu à mão. */
    val contagem_informada: Int?,
    val contexto: Map<String, Double>,
    val data: String,
    val versao_app: String,
)

/** Marcas em coordenadas da foto (0 a 1) para pixels. */
internal fun pontosEmPixels(marcas: List<Pair<Float, Float>>, largura: Int, altura: Int): List<List<Int>> =
    marcas.map { (x, y) ->
        listOf(
            (x * largura).toInt().coerceIn(0, largura - 1),
            (y * altura).toInt().coerceIn(0, altura - 1),
        )
    }

private fun pasta(context: Context) = File(context.filesDir, PASTA)

/**
 * Guarda a foto e as marcas. Lê a foto de novo pelo mesmo caminho da tela
 * (carregaFoto), para a imagem guardada ser pixel a pixel a que foi tocada.
 * Roda fora da thread principal; devolve false se a foto não pôde ser lida.
 */
internal fun guardaAmostra(
    context: Context,
    foto: Uri,
    classe: String,
    marcas: List<Pair<Float, Float>>,
    contagemInformada: Int?,
    contexto: Map<String, Double>,
): Boolean {
    if (marcas.isEmpty()) return false
    val bmp = carregaFoto(context, foto) ?: return false
    val dir = pasta(context).apply { mkdirs() }
    val agora = Date()
    val nome = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(agora) + "_" + classe
    File(dir, "$nome.jpg").outputStream().use { bmp.compress(Bitmap.CompressFormat.JPEG, 92, it) }
    val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).apply { timeZone = TimeZone.getDefault() }
    val anotacao = AnotacaoFoto(
        imagem = "$nome.jpg",
        largura = bmp.width,
        altura = bmp.height,
        classe = classe,
        pontos = pontosEmPixels(marcas, bmp.width, bmp.height),
        contagem_informada = contagemInformada,
        contexto = contexto,
        data = iso.format(agora),
        versao_app = BuildConfig.VERSION_NAME,
    )
    File(dir, "$nome.json").writeText(GsonBuilder().setPrettyPrinting().create().toJson(anotacao))
    return true
}

/** Quantas fotos marcadas estão guardadas. */
internal fun contaAmostras(context: Context): Int =
    pasta(context).listFiles { f -> f.name.endsWith(".json") }?.size ?: 0

/** Tamanho das fotos guardadas, em MB, para o produtor saber quanto ocupam. */
internal fun tamanhoAmostrasMb(context: Context): Double =
    (pasta(context).listFiles()?.sumOf { it.length() } ?: 0L) / 1_048_576.0

private const val LEIAME = """Fotos marcadas no AgroInteligência (Estimativa no campo)

Cada foto (.jpg) tem ao lado um .json com o mesmo nome:
  classe              "planta" (foto de 1 m de linha) ou "vagem" (plantas arrancadas)
  largura, altura     tamanho da imagem em pixels
  pontos              centro de cada marca feita pelo produtor, [x, y] em pixels,
                      origem no canto superior esquerdo
  contagem_informada  número que ficou na tela; se difere da quantidade de pontos,
                      o produtor corrigiu a contagem à mão e a foto pode ter
                      objetos sem marca
  contexto            metros de linha, plantas arrancadas, espaçamento etc.
  data, versao_app

As imagens já estão de pé (orientação EXIF aplicada) e reduzidas a no máximo
2048 px no lado maior: são exatamente as que foram tocadas.
"""

/** Junta tudo num .zip no cache, pronto para compartilhar; null se não houver fotos. */
internal fun empacotaAmostras(context: Context): File? {
    val arquivos = pasta(context).listFiles()?.sortedBy { it.name } ?: return null
    if (arquivos.none { it.name.endsWith(".json") }) return null
    val saida = File(context.cacheDir, "exportar").apply { mkdirs() }
    saida.listFiles()?.forEach { it.delete() }
    val dia = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
    val zip = File(saida, "fotos_marcadas_$dia.zip")
    ZipOutputStream(zip.outputStream().buffered()).use { z ->
        z.putNextEntry(ZipEntry("LEIAME.txt"))
        z.write(LEIAME.toByteArray())
        z.closeEntry()
        for (f in arquivos) {
            z.putNextEntry(ZipEntry(f.name))
            f.inputStream().use { it.copyTo(z) }
            z.closeEntry()
        }
    }
    return zip
}

internal fun apagaAmostras(context: Context) {
    pasta(context).listFiles()?.forEach { it.delete() }
}
