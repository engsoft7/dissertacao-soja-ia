package com.agrointeligencia.app

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos

// AS CONTAS DA ESTIMATIVA NO CAMPO.
//
// É a estimativa de produtividade que o agrônomo faz na lavoura antes da
// colheita, por componentes de rendimento:
//
//     kg/ha = plantas/m² × vagens/planta × grãos/vagem × peso de mil grãos (g) ÷ 100
//
// (plantas/m² × vagens × grãos dá grãos por m²; vezes o peso de um grão em
// gramas, PMG/1000, dá g/m²; vezes 10.000 m²/ha e dividido por 1.000 g/kg,
// kg/ha. Sobra o ÷ 100.)
//
// Plantas e vagens o produtor conta, na foto ou no campo. Grãos por vagem e
// peso de mil grãos dependem da cultivar e do ano: entram com um valor típico
// que ele ajusta. A conta não desconta perdas de colheita: o número é o que a
// lavoura tem no pé.
//
// Ficam fora da tela, sem nada de Android, para os testes de unidade
// alcançarem sem emulador.

/** Um ponto de amostragem: plantas numa linha medida e vagens de plantas arrancadas. */
data class PontoAmostra(
    val plantas: Int,
    val metrosDeLinha: Double,
    val arrancadas: Int,
    val vagens: Int,
)

data class ParametrosCampo(
    /** Espaçamento entre linhas, em metros. */
    val espacamento: Double = 0.45,
    val graosPorVagem: Double = 2.2,
    /** Peso de mil grãos, em gramas. */
    val pesoMilGraos: Double = 150.0,
)

data class Estimativa(
    val pontos: Int,
    val plantasPorM2: Double,
    val vagensPorPlanta: Double,
    val kgHa: Double,
    /** Menor e maior estimativa entre os pontos; iguais com um ponto só. */
    val kgHaMin: Double,
    val kgHaMax: Double,
) {
    val scHa: Double get() = kgHa / 60.0
}

internal fun PontoAmostra.valido(): Boolean =
    plantas > 0 && metrosDeLinha > 0 && arrancadas > 0 && vagens > 0

internal fun plantasPorM2(p: PontoAmostra, espacamento: Double): Double =
    p.plantas / (p.metrosDeLinha * espacamento)

internal fun vagensPorPlanta(p: PontoAmostra): Double = p.vagens.toDouble() / p.arrancadas

internal fun kgPorHectare(plantasM2: Double, vagensPlanta: Double, graosVagem: Double, pesoMil: Double): Double =
    plantasM2 * vagensPlanta * graosVagem * pesoMil / 100.0

/**
 * Estimativa da lavoura: a média das estimativas de cada ponto válido.
 *
 * Média por ponto, e não soma de todas as plantas e vagens, porque cada ponto
 * representa um pedaço igual do talhão; somar daria mais peso ao ponto em que
 * se arrancaram mais plantas. A faixa entre o menor e o maior ponto vai junto:
 * ela diz ao produtor se a lavoura é uniforme ou se faltam pontos.
 */
internal fun estimaLavoura(pontos: List<PontoAmostra>, par: ParametrosCampo): Estimativa? {
    if (par.espacamento <= 0 || par.graosPorVagem <= 0 || par.pesoMilGraos <= 0) return null
    val validos = pontos.filter { it.valido() }
    if (validos.isEmpty()) return null
    val porPonto = validos.map {
        kgPorHectare(plantasPorM2(it, par.espacamento), vagensPorPlanta(it), par.graosPorVagem, par.pesoMilGraos)
    }
    return Estimativa(
        pontos = validos.size,
        plantasPorM2 = validos.map { plantasPorM2(it, par.espacamento) }.average(),
        vagensPorPlanta = validos.map { vagensPorPlanta(it) }.average(),
        kgHa = porPonto.average(),
        kgHaMin = porPonto.min(),
        kgHaMax = porPonto.max(),
    )
}

private const val RAIO_TERRA_M = 6_371_008.8

/**
 * Área, em hectares, do polígono dado pelos vértices (latitude, longitude) em
 * graus, na ordem em que foram marcados.
 *
 * Projeta os vértices num plano em torno da latitude média (equiretangular) e
 * aplica a fórmula do laço (shoelace). Para um talhão, de algumas centenas de
 * metros a poucos quilômetros, o erro da projeção é muito menor que o do GPS
 * do celular, de 3 a 10 m por ponto.
 */
internal fun areaHectares(vertices: List<Pair<Double, Double>>): Double {
    if (vertices.size < 3) return 0.0
    val lat0 = vertices.map { it.first }.average() * PI / 180
    val xy = vertices.map { (lat, lon) ->
        Pair(RAIO_TERRA_M * lon * PI / 180 * cos(lat0), RAIO_TERRA_M * lat * PI / 180)
    }
    var dobro = 0.0
    for (i in xy.indices) {
        val (x1, y1) = xy[i]
        val (x2, y2) = xy[(i + 1) % xy.size]
        dobro += x1 * y2 - x2 * y1
    }
    return abs(dobro) / 2 / 10_000
}
