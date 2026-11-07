package com.agrointeligencia.app

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import com.google.gson.Gson
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
/** Os talhões, com os pontos e a colheita, num arquivo só ao lado das fotos. */
internal const val TALHOES = "talhoes.json"

/** De onde vieram as marcas de uma foto. */
internal object MarcasDe {
    /** Todas tocadas pelo produtor. */
    const val PRODUTOR = "produtor"
    /** Sugeridas pelo contador automático e depois conferidas pelo produtor. */
    const val CONTADOR_CONFERIDO = "contador_conferido"
}

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
    /** "produtor" ou "contador_conferido" (ver MarcasDe). */
    val origem_das_marcas: String = MarcasDe.PRODUTOR,
    /** Quando o contador automático foi usado: o número que ele deu e quantas marcas sugeriu. */
    val contagem_automatica: Int? = null,
    val marcas_sugeridas: Int? = null,
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
    origem: String = MarcasDe.PRODUTOR,
    automatica: ContagemAutomatica? = null,
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
        origem_das_marcas = origem,
        contagem_automatica = automatica?.vagens,
        marcas_sugeridas = automatica?.marcas?.size,
    )
    File(dir, "$nome.json").writeText(GsonBuilder().setPrettyPrinting().create().toJson(anotacao))
    return true
}

/** Quantas fotos marcadas estão guardadas. */
internal fun contaAmostras(context: Context): Int =
    pasta(context).listFiles { f -> f.name.endsWith(".json") && f.name != TALHOES }?.size ?: 0

// O TALHÃO E A COLHEITA.
//
// A estimativa no campo e o contador só se conferem de verdade com a balança:
// quantas sacas saíram do talhão. A colheita vem semanas depois das contagens,
// e o produtor a informa na mesma tela. O talhão vai no .zip com os pontos
// (cada um com o número do contador, quando foi usado) e a colheita, e
// ciclo_retreino.py colheita compara a estimativa por toque e a do contador
// com o que foi pesado.

/** Um talhão como vai no .zip. */
data class RegistroTalhao(
    val talhao: String,
    val atualizado_em: String,
    val versao_app: String,
    val versao_contador: Int,
    val modo_automatico: Boolean,
    val area_ha: Double?,
    val espacamento_m: Double,
    val graos_por_vagem: Double,
    val peso_mil_graos_g: Double,
    val pontos: List<PontoAmostra>,
    /** A estimativa da tela (CampoCalculo.kt), no pé, antes das perdas na colheita. */
    val estimativa_kg_ha: Double?,
    /** Sacas de 60 kg do romaneio, já descontadas umidade e impureza. */
    val colhido_sacas: Double?,
    val colheita_kg_ha: Double?,
)

/** Produtividade colhida, em kg/ha: as sacas de 60 kg sobre a área. */
internal fun colheitaKgHa(sacas: Double?, areaHa: Double?): Double? =
    if (sacas == null || areaHa == null || sacas <= 0 || areaHa <= 0) null else sacas * 60.0 / areaHa

internal fun registroDoTalhao(
    estado: EstadoCampo,
    agora: String,
    versaoApp: String,
    versaoContador: Int,
    modoAutomatico: Boolean,
): RegistroTalhao? {
    val id = estado.talhao ?: return null
    if (estado.pontos.isEmpty() && estado.colhidoSacas == null) return null
    val p = estado.parametros
    return RegistroTalhao(
        talhao = id, atualizado_em = agora, versao_app = versaoApp, versao_contador = versaoContador,
        modo_automatico = modoAutomatico, area_ha = estado.areaHa, espacamento_m = p.espacamento,
        graos_por_vagem = p.graosPorVagem, peso_mil_graos_g = p.pesoMilGraos, pontos = estado.pontos,
        estimativa_kg_ha = estimaLavoura(estado.pontos, p)?.kgHa,
        colhido_sacas = estado.colhidoSacas, colheita_kg_ha = colheitaKgHa(estado.colhidoSacas, estado.areaHa),
    )
}

/** O arquivo inteiro: uma classe, e não um Map genérico, para o Gson não depender de TypeToken. */
private data class ArquivoTalhoes(val talhoes: List<RegistroTalhao>?)

private val TRAVA_TALHOES = Any()

private fun leTalhoes(context: Context): List<RegistroTalhao> = try {
    File(pasta(context), TALHOES).takeIf { it.exists() }
        ?.let { Gson().fromJson(it.readText(), ArquivoTalhoes::class.java)?.talhoes?.filterNotNull() } ?: emptyList()
} catch (_: Exception) {
    emptyList()
}

/** Junta o registro aos que já estavam: o do mesmo talhão é trocado, os outros ficam. */
internal fun comTalhao(todos: List<RegistroTalhao>, registro: RegistroTalhao): List<RegistroTalhao> =
    todos.filter { it.talhao != registro.talhao } + registro

/** Grava (ou atualiza) o talhão. Roda fora da thread principal. */
internal fun gravaTalhao(context: Context, registro: RegistroTalhao) = synchronized(TRAVA_TALHOES) {
    val dir = pasta(context).apply { mkdirs() }
    val tmp = File(dir, "$TALHOES.novo")
    tmp.writeText(GsonBuilder().setPrettyPrinting().create().toJson(ArquivoTalhoes(comTalhao(leTalhoes(context), registro))))
    if (!tmp.renameTo(File(dir, TALHOES))) tmp.delete()
}

/** Quantos talhões têm a colheita informada. */
internal fun talhoesComColheita(context: Context): Int = leTalhoes(context).count { it.colheita_kg_ha != null }

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
  origem_das_marcas   "produtor" (todas tocadas por ele) ou "contador_conferido"
                      (sugeridas pelo contador automático e conferidas pelo
                      produtor); fotos com marcas só do contador não entram
  contagem_automatica, marcas_sugeridas
                      o número que o contador deu e quantas marcas ele sugeriu,
                      quando foi usado

As imagens já estão de pé (orientação EXIF aplicada) e reduzidas a no máximo
2048 px no lado maior: são exatamente as que foram tocadas.

talhoes.json tem, na lista "talhoes", cada talhão em que se contou:
  talhao              identificação do talhão, sorteada pelo app
  pontos              plantas, metrosDeLinha, arrancadas e vagens de cada ponto;
                      vagensDoContador é o número do contador automático,
                      quando foi usado, e conferido diz se o produtor
                      conferiu as marcas
  espacamento_m, graos_por_vagem, peso_mil_graos_g, area_ha
  estimativa_kg_ha    a estimativa da tela, no pé, antes das perdas na colheita
  colhido_sacas       sacas de 60 kg do romaneio, se o produtor informou
  colheita_kg_ha      o colhido sobre a área
  versao_contador, modo_automatico
"""

/** Junta tudo num .zip no cache, pronto para compartilhar; null se não houver fotos. */
internal fun empacotaAmostras(context: Context): File? {
    val arquivos = pasta(context).listFiles()?.filter { !it.name.endsWith(".novo") }?.sortedBy { it.name }
        ?: return null
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
