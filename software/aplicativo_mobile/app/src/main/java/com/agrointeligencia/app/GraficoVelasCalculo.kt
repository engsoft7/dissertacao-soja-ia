package com.agrointeligencia.app

import kotlin.math.ceil
import kotlin.math.floor

// AS CONTAS DO GRÁFICO DE VELAS (Mercado.kt, GraficoVelas).
//
// O gráfico funciona como o das ferramentas de bolsa: dois dedos aproximam e
// afastam, um dedo arrasta para os lados, dois toques voltam ao período
// inteiro e, ao tocar e segurar, uma cruz mostra a vela e o preço sob o dedo.
// As médias móveis de 9 e de 21 velas, que se ligam e desligam, são médias
// simples dos fechamentos. Cada ponto da média usa as velas daquele ponto para
// trás, dentro do período que a API mandou: a de 21 só começa na 21ª vela.
//
// Ficam fora da tela, sem nada de Android, para os testes de unidade
// alcançarem sem emulador.

/** As médias móveis do gráfico, em velas. */
const val MEDIA_CURTA = 9
const val MEDIA_LONGA = 21

/** Menos velas que isso na largura, o zoom não aproxima mais: cada vela ficaria mais larga que o necessário. */
const val VELAS_MINIMAS_NA_TELA = 8

/** Média móvel simples dos fechamentos em [periodos] velas; nula até haver velas bastantes. */
fun mediaMovel(fechamentos: List<Double>, periodos: Int): List<Double?> {
    if (periodos <= 0) return fechamentos.map { null }
    val saida = ArrayList<Double?>(fechamentos.size)
    var soma = 0.0
    fechamentos.forEachIndexed { i, c ->
        soma += c
        if (i >= periodos) soma -= fechamentos[i - periodos]
        saida += if (i >= periodos - 1) soma / periodos else null
    }
    return saida
}

/**
 * A parte do período que aparece no gráfico: [inicio] é a posição, em velas,
 * da borda esquerda, e [tamanho] é quantas velas cabem na largura. Os dois são
 * fracionários para o zoom e o arrasto andarem suaves, sem pular de vela em
 * vela.
 */
data class JanelaVelas(val inicio: Float, val tamanho: Float) {
    val fim: Float get() = inicio + tamanho

    /** Índices das velas que aparecem, ao menos em parte. */
    fun indices(total: Int): IntRange =
        floor(inicio).toInt().coerceAtLeast(0)..(ceil(fim).toInt() - 1).coerceAtMost(total - 1)

    /** Se mostra o período inteiro. */
    fun inteira(total: Int): Boolean = tamanho >= total - 1e-3f
}

fun janelaInteira(total: Int) = JanelaVelas(0f, total.toFloat())

/** A janela dentro do período: de [VELAS_MINIMAS_NA_TELA] velas (ou todas, se forem menos) ao período inteiro. */
fun JanelaVelas.ajustada(total: Int): JanelaVelas {
    if (total <= 0) return JanelaVelas(0f, 0f)
    val t = tamanho.coerceIn(minOf(VELAS_MINIMAS_NA_TELA, total).toFloat(), total.toFloat())
    return JanelaVelas(inicio.coerceIn(0f, total - t), t)
}

/**
 * Aproxima ([fator] maior que 1) ou afasta (menor que 1) sem tirar do lugar a
 * vela sob os dedos: [ancora] é a posição do centro da pinça na área das
 * velas, de 0 (borda esquerda) a 1 (direita).
 */
fun JanelaVelas.comZoom(fator: Float, ancora: Float, total: Int): JanelaVelas {
    if (fator <= 0f || total <= 0) return ajustada(total)
    val a = ancora.coerceIn(0f, 1f)
    val sobOsDedos = inicio + a * tamanho
    val novo = (tamanho / fator).coerceIn(minOf(VELAS_MINIMAS_NA_TELA, total).toFloat(), total.toFloat())
    return JanelaVelas(sobOsDedos - a * novo, novo).ajustada(total)
}

/** Arrasta [velas] velas: positivo leva a janela para o passado, como o dedo que vai para a direita. */
fun JanelaVelas.arrastada(velas: Float, total: Int): JanelaVelas = JanelaVelas(inicio - velas, tamanho).ajustada(total)

/**
 * A janela depois que chegam velas novas (a tela se atualiza a cada minuto):
 * quem via o período inteiro continua vendo, quem via o fim acompanha a vela
 * nova, e quem tinha ido ao passado fica onde estava.
 */
fun JanelaVelas.comVelasNovas(totalAntes: Int, total: Int): JanelaVelas = when {
    inteira(totalAntes) -> janelaInteira(total)
    fim >= totalAntes - 0.5f -> JanelaVelas(total - tamanho, tamanho).ajustada(total)
    else -> ajustada(total)
}

/** A vela sob a posição [x] da área das velas (0 a 1), ou nula fora do período. */
fun JanelaVelas.velaEm(x: Float, total: Int): Int? = floor(inicio + x.coerceIn(0f, 0.9999f) * tamanho).toInt()
    .takeIf { it in 0 until total }

/**
 * Mínima e máxima do que aparece: as velas da janela, a linha do Pará e as
 * [linhas] desenhadas por cima (as médias), para a escala do eixo acompanhar o
 * zoom, como nas ferramentas de bolsa. Nula sem vela na janela.
 */
fun faixaVisivel(velas: List<Vela>, janela: JanelaVelas, linhas: List<List<Double?>> = emptyList()): Pair<Double, Double>? {
    val indices = janela.indices(velas.size)
    if (indices.isEmpty()) return null
    var minimo = Double.MAX_VALUE
    var maximo = -Double.MAX_VALUE
    for (i in indices) {
        val v = velas[i]
        minimo = minOf(minimo, v.l)
        maximo = maxOf(maximo, v.h)
        v.pa?.let { minimo = minOf(minimo, it); maximo = maxOf(maximo, it) }
        linhas.forEach { linha -> linha.getOrNull(i)?.let { minimo = minOf(minimo, it); maximo = maxOf(maximo, it) } }
    }
    return minimo to maximo
}
