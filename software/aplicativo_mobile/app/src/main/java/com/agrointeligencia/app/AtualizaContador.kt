package com.agrointeligencia.app

import android.content.Context
import com.google.gson.Gson
import okhttp3.OkHttpClient
import okhttp3.Request
import org.tensorflow.lite.Interpreter
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

// MODELO DO CONTADOR SEM VERSÃO NOVA DO APLICATIVO.
//
// O contador de vagens vem dentro do aplicativo (assets). Quando ele for
// retreinado com fotos do Pará (pesquisa/09_contagem_por_imagem/ciclo_retreino.py)
// e passar no portão de qualidade, os .tflite novos vão para a branch
// modelo-contagem-vagens e a API passa a anunciá-los em /api/contador, pelo
// endereço do commit (que não muda depois de publicado). Não se usa Release:
// cada Release publicado gera um depósito novo no Zenodo. Uma vez por dia o
// aplicativo consulta o anúncio e, se houver versão mais nova, baixa os dois
// arquivos e só os adota depois de conferir:
//   - o endereço: só arquivos deste repositório, presos a um commit;
//   - o tamanho e o resumo SHA-256 anunciados (arquivo corrompido ou trocado
//     no caminho fica de fora);
//   - que o modelo abre e tem a entrada e a saída que ContadorVagens.kt espera.
// Qualquer falha deixa tudo como estava: o contador segue com o modelo que
// estiver valendo, e o embutido é sempre a reserva. Nada é enviado: é só uma
// consulta e um download.

/** Versão dos modelos em assets. Sobe junto com eles, num aplicativo novo. */
internal const val VERSAO_EMBUTIDA = 1

/** Os arquivos do repositório: o único lugar de onde o aplicativo aceita modelo. */
internal const val ORIGEM_PERMITIDA = "https://raw.githubusercontent.com/engsoft7/dissertacao-soja-ia/"

/** Depois da origem, o commit inteiro (40 dígitos) e o caminho: um endereço que não muda. */
private val ENDERECO = Regex(Regex.escape(ORIGEM_PERMITIDA) + "[0-9a-f]{40}/[A-Za-z0-9_./-]+")

private const val PASTA = "contador"
private const val INTERVALO_MS = 24L * 60 * 60 * 1000

data class ArquivoModelo(val url: String, val sha256: String, val bytes: Long)

/** O anúncio que a API devolve em /api/contador (software/api_backend/contador_modelo.json). */
data class ManifestoContador(
    val versao: Int,
    val app_minimo: Int? = null,
    val arquivos: Map<String, ArquivoModelo>? = null,
    /** A frase sobre de onde o modelo aprendeu e quanto erra, para a tela. */
    val nota: String? = null,
)

/** O que ficou gravado do último modelo baixado. */
internal data class ModeloBaixado(val versao: Int, val sha256: Map<String, String>, val nota: String?)

private val ARQUIVOS = listOf(MODELO_CONTAGEM.arquivo, MODELO_MARCAS.arquivo)

/**
 * Se vale baixar o modelo anunciado: versão mais nova que a do celular, feita
 * para esta versão do aplicativo, com os dois arquivos, vindos do repositório
 * por um commit fixo e com resumo e tamanho plausíveis.
 */
internal fun precisaBaixar(m: ManifestoContador?, versaoLocal: Int, versaoApp: Int): Boolean {
    if (m == null || m.versao <= versaoLocal) return false
    if ((m.app_minimo ?: 0) > versaoApp) return false
    val arquivos = m.arquivos ?: return false
    return ARQUIVOS.all { nome ->
        val a = arquivos[nome] ?: return@all false
        ENDERECO.matches(a.url) && !a.url.contains("..") &&
            a.sha256.matches(Regex("[0-9a-f]{64}")) && a.bytes in 100_000L..50_000_000L
    }
}

internal fun sha256Hex(bytes: ByteArray): String =
    MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

private fun pasta(context: Context) = File(context.filesDir, PASTA)

internal fun modeloBaixado(context: Context): ModeloBaixado? = try {
    File(pasta(context), "versao.json").takeIf { it.exists() }
        ?.let { Gson().fromJson(it.readText(), ModeloBaixado::class.java) }
} catch (_: Exception) {
    null
}

/** Versão do contador em uso: a baixada, se houver, ou a embutida. */
internal fun versaoContador(context: Context): Int =
    maxOf(VERSAO_EMBUTIDA, modeloBaixado(context)?.versao ?: 0)

/**
 * Bytes do modelo: o baixado, se o resumo ainda conferir com o gravado, ou o
 * embutido. Um arquivo baixado que se corrompeu no armazenamento não é usado.
 */
internal fun bytesDoModelo(context: Context, arquivo: String): ByteArray {
    val baixado = modeloBaixado(context)
    val f = File(pasta(context), arquivo)
    if (baixado != null && baixado.versao > VERSAO_EMBUTIDA && f.exists()) {
        val bytes = f.readBytes()
        if (sha256Hex(bytes) == baixado.sha256[arquivo]) return bytes
    }
    return context.assets.open(arquivo).use { it.readBytes() }
}

/** O modelo abre e tem a entrada (1×3×altura×largura) e a saída que o contador usa. */
private fun confereFormato(bytes: ByteArray, m: ModeloVagens): Boolean = try {
    val buf = ByteBuffer.allocateDirect(bytes.size).order(ByteOrder.nativeOrder()).put(bytes)
    buf.rewind()
    Interpreter(buf).use { modelo ->
        val ent = modelo.getInputTensor(0).shape().toList()
        val sai = modelo.getOutputTensor(0).shape()
        ent == listOf(1, 3, m.altura, m.largura) &&
            sai.fold(1) { a, b -> a * b } == (m.largura / m.passo) * (m.altura / m.passo)
    }
} catch (_: Throwable) {
    false
}

/**
 * Consulta o anúncio e, se houver modelo novo, baixa, confere e adota. Chame
 * fora da thread principal; no máximo uma consulta por dia. Devolve a versão
 * adotada, ou null se nada mudou.
 */
internal suspend fun atualizaContador(context: Context, versaoApp: Int = BuildConfig.VERSION_CODE): Int? {
    val prefs = context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE)
    val agora = System.currentTimeMillis()
    if (agora - prefs.getLong("contador_consultado_em", 0L) < INTERVALO_MS) return null
    return try {
        val manifesto = RetrofitClient.getInstance().getContador()
        prefs.edit().putLong("contador_consultado_em", agora).apply()
        if (!precisaBaixar(manifesto, versaoContador(context), versaoApp)) return null
        val cliente = OkHttpClient.Builder().connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS).build()
        val novos = mutableMapOf<String, ByteArray>()
        for (m in listOf(MODELO_CONTAGEM, MODELO_MARCAS)) {
            val a = manifesto.arquivos!!.getValue(m.arquivo)
            val bytes = cliente.newCall(Request.Builder().url(a.url).build()).execute().use { r ->
                if (!r.isSuccessful) return null
                r.body?.bytes() ?: return null
            }
            if (bytes.size.toLong() != a.bytes || sha256Hex(bytes) != a.sha256) return null
            if (!confereFormato(bytes, m)) return null
            novos[m.arquivo] = bytes
        }
        // Só troca quando os dois chegaram e conferiram: nunca um modelo novo com o outro velho.
        val dir = pasta(context).apply { mkdirs() }
        for ((nome, bytes) in novos) {
            val tmp = File(dir, "$nome.novo")
            tmp.writeBytes(bytes)
            if (!tmp.renameTo(File(dir, nome))) { tmp.delete(); return null }
        }
        val registro = ModeloBaixado(manifesto.versao, novos.mapValues { sha256Hex(it.value) }, manifesto.nota)
        File(dir, "versao.json").writeText(Gson().toJson(registro))
        manifesto.versao
    } catch (_: Exception) {
        null
    }
}
