package com.agrointeligencia.app

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import androidx.core.content.FileProvider
import java.io.File
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlin.math.roundToInt

// O RESUMO PARA COMPARTILHAR
//
// Um toque no Resumo gera uma página com o que o app mostra do município (a
// produtividade esperada, o preço da praça e o resultado por hectare, a janela
// de plantio e o caderno da safra) e a entrega ao compartilhamento do Android:
// como imagem, que cabe numa conversa do WhatsApp, ou como PDF, para imprimir
// ou mandar por e-mail. A mesma função desenha as duas; os arquivos ficam no
// cache do app (exportar/) e só saem dele pelo compartilhamento.

data class SecaoRelatorio(val titulo: String, val linhas: List<String>)

data class Relatorio(val titulo: String, val subtitulo: String, val secoes: List<SecaoRelatorio>, val rodape: String)

/** O que entra no resumo; cada parte é opcional e some quando falta. */
data class DadosDoRelatorio(
    val municipio: String,
    val uf: String,
    val hoje: LocalDate,
    val projecao: PrevisaoHistorico? = null,
    val ultimoReal: PrevisaoHistorico? = null,
    val praca: PracaPara? = null,
    val precoUsado: Double? = null,
    val resultadoPorHa: Double? = null,
    val sacasPorHa: Double? = null,
    val plantioCalendario: String? = null,
    val plantioZarc: String? = null,
    val plantioRegiao: String? = null,
    val caderno: ResumoCaderno? = null,
    val safraDoCaderno: Int? = null,
)

private fun numeroBr(v: Double, casas: Int): String = String.format(LOCAL_NUMEROS, "%,.${casas}f", v)

fun montaRelatorio(context: Context, d: DadosDoRelatorio): Relatorio {
    val secoes = mutableListOf<SecaoRelatorio>()
    val f = DateTimeFormatter.ofPattern(context.getString(R.string.plantio_formato_data), context.resources.configuration.locales[0])

    val produtividade = mutableListOf<String>()
    d.projecao?.let { p ->
        val sacas = (p.rendimento_predito / 60).roundToInt().toString()
        produtividade += if (p.margem_erro > 0)
            context.getString(R.string.relatorio_esperada, p.ano, milhar(p.rendimento_predito), sacas, milhar(p.margem_erro))
        else context.getString(R.string.relatorio_esperada_sem_erro, p.ano, milhar(p.rendimento_predito), sacas)
    }
    d.ultimoReal?.takeIf { it.rendimento_real > 0 }?.let {
        produtividade += context.getString(R.string.relatorio_ultimo_ibge, it.ano, milhar(it.rendimento_real))
    }
    if (produtividade.isNotEmpty()) secoes += SecaoRelatorio(context.getString(R.string.relatorio_secao_produtividade), produtividade)

    val preco = mutableListOf<String>()
    d.praca?.let { preco += context.getString(R.string.relatorio_praca, it.praca, reais(it.valor), dataCurta(it.data)) }
        ?: d.precoUsado?.let { preco += context.getString(R.string.relatorio_preco_referencia, reais(it)) }
    if (d.resultadoPorHa != null && d.sacasPorHa != null && d.precoUsado != null) {
        val r = d.resultadoPorHa
        preco += context.getString(R.string.relatorio_resultado, (if (r < 0) "−" else "") + reais(kotlin.math.abs(r)),
                                    numeroBr(d.sacasPorHa, 1), reais(d.precoUsado))
    }
    if (preco.isNotEmpty()) secoes += SecaoRelatorio(context.getString(R.string.relatorio_secao_preco), preco)

    val plantio = listOfNotNull(
        d.plantioCalendario?.let { c -> d.plantioRegiao?.let { context.getString(R.string.relatorio_regiao, c, it) } ?: "$c." },
        d.plantioZarc?.let { "$it." },
    )
    if (plantio.isNotEmpty()) secoes += SecaoRelatorio(context.getString(R.string.relatorio_secao_plantio), plantio)

    d.caderno?.takeIf { it.areaPlantada > 0.0 || it.custoTotal > 0.0 || it.sacasColhidas > 0.0 }?.let { c ->
        val linhas = mutableListOf<String>()
        if (c.areaPlantada > 0.0 || c.custoTotal > 0.0) {
            linhas += context.getString(R.string.relatorio_caderno_area, numeroBr(c.areaPlantada, 1), reais(c.custoTotal))
        }
        c.produtividade?.let { linhas += context.getString(R.string.relatorio_caderno_colhido, numeroBr(it, 1)) }
        c.precoMedio?.let { linhas += context.getString(R.string.relatorio_caderno_vendido, milhar(c.sacasVendidas), reais(it)) }
        secoes += SecaoRelatorio(context.getString(R.string.relatorio_secao_caderno, rotuloDaSafra(d.safraDoCaderno ?: 0)), linhas)
    }

    return Relatorio(
        titulo = context.getString(R.string.relatorio_titulo, d.municipio, d.uf),
        subtitulo = context.getString(R.string.relatorio_subtitulo, d.hoje.format(f)),
        secoes = secoes,
        rodape = context.getString(R.string.relatorio_rodape),
    )
}

private const val VERDE = 0xFF047857.toInt()
private const val TEXTO = 0xFF1E293B.toInt()
private const val CINZA = 0xFF475569.toInt()

/** Escreve [texto] com quebra de linha a partir de [y] e devolve onde ele termina; sem canvas, só mede. */
private fun escreve(canvas: Canvas?, texto: String, x: Float, y: Float, largura: Float, tamanho: Float,
                    negrito: Boolean, cor: Int): Float {
    val pincel = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = tamanho
        color = cor
        typeface = if (negrito) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
    }
    val layout = StaticLayout.Builder.obtain(texto, 0, texto.length, pincel, largura.toInt())
        .setAlignment(Layout.Alignment.ALIGN_NORMAL)
        .setLineSpacing(0f, 1.15f)
        .build()
    if (canvas != null) {
        canvas.save()
        canvas.translate(x, y)
        layout.draw(canvas)
        canvas.restore()
    }
    return y + layout.height
}

/**
 * Desenha o resumo numa página de [largura] x [altura] e devolve a altura de
 * que ele precisa, até o fim do rodapé; sem [canvas], só mede. [escala] 1 é a
 * página A4 do PDF em pontos (595 x 842); a imagem usa a mesma página com a
 * letra maior que couber (escalaDaImagem).
 */
fun desenhaRelatorio(canvas: Canvas?, r: Relatorio, largura: Float, altura: Float, escala: Float): Float {
    canvas?.drawColor(android.graphics.Color.WHITE)
    canvas?.drawRect(0f, 0f, largura, 10f * escala, Paint().apply { color = VERDE })
    val margem = 36f * escala
    val util = largura - 2 * margem
    var y = margem
    y = escreve(canvas, r.titulo, margem, y, util, 20f * escala, true, VERDE)
    y = escreve(canvas, r.subtitulo, margem, y + 2f * escala, util, 11f * escala, false, CINZA)
    for (s in r.secoes) {
        y += 16f * escala
        y = escreve(canvas, s.titulo, margem, y, util, 13.5f * escala, true, TEXTO)
        for (linha in s.linhas) {
            y = escreve(canvas, "•  $linha", margem, y + 4f * escala, util, 11.5f * escala, false, TEXTO)
        }
    }
    // O rodapé fica embaixo, com as fontes e a ressalva de apoio à decisão.
    val pincel = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 8.5f * escala; color = CINZA }
    val rodape = StaticLayout.Builder.obtain(r.rodape, 0, r.rodape.length, pincel, util.toInt())
        .setLineSpacing(0f, 1.1f).build()
    if (canvas != null) {
        canvas.save()
        canvas.translate(margem, maxOf(y + 16f * escala, altura - margem - rodape.height))
        rodape.draw(canvas)
        canvas.restore()
    }
    return y + 16f * escala + rodape.height + margem
}

private fun pastaDeExportar(context: Context): File = File(context.cacheDir, "exportar").apply { mkdirs() }

/** O resumo como PDF de uma página A4. */
fun geraPdf(context: Context, r: Relatorio): File {
    val documento = PdfDocument()
    val pagina = documento.startPage(PdfDocument.PageInfo.Builder(595, 842, 1).create())
    desenhaRelatorio(pagina.canvas, r, 595f, 842f, 1f)
    documento.finishPage(pagina)
    val arquivo = File(pastaDeExportar(context), "resumo_agrointeligencia.pdf")
    arquivo.outputStream().use { documento.writeTo(it) }
    documento.close()
    return arquivo
}

/**
 * A escala da imagem: a maior que ainda cabe na página. Na escala do PDF, a
 * letra do corpo saía com 21 px, uns 8 pontos na tela do celular, e metade da
 * página ficava vazia.
 */
fun escalaDaImagem(r: Relatorio, largura: Float = 1080f, altura: Float = 1350f): Float =
    listOf(2.6f, 2.4f, 2.2f, 2.0f).firstOrNull { desenhaRelatorio(null, r, largura, altura, it) <= altura }
        ?: (largura / 595f)

/** O resumo como imagem de 1080 x 1350, o tamanho que o WhatsApp mostra inteiro. */
fun geraImagem(context: Context, r: Relatorio): File {
    val bitmap = Bitmap.createBitmap(1080, 1350, Bitmap.Config.ARGB_8888)
    desenhaRelatorio(Canvas(bitmap), r, 1080f, 1350f, escalaDaImagem(r))
    val arquivo = File(pastaDeExportar(context), "resumo_agrointeligencia.png")
    arquivo.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    bitmap.recycle()
    return arquivo
}

/** Abre o compartilhamento do Android com o arquivo; false se não houver aplicativo para recebê-lo. */
fun compartilhaArquivo(context: Context, arquivo: File, tipo: String): Boolean {
    val uri = FileProvider.getUriForFile(context, context.packageName + ".fotos", arquivo)
    val envio = Intent(Intent.ACTION_SEND).apply {
        type = tipo
        putExtra(Intent.EXTRA_STREAM, uri)
        putExtra(Intent.EXTRA_SUBJECT, context.getString(R.string.relatorio_assunto))
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    return try {
        context.startActivity(Intent.createChooser(envio, context.getString(R.string.relatorio_compartilhar))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    } catch (_: ActivityNotFoundException) {
        false
    }
}
