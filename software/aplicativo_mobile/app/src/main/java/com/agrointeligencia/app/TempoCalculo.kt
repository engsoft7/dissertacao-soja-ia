package com.agrointeligencia.app

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.temporal.ChronoUnit
import kotlin.math.ln
import kotlin.math.roundToInt

// AS CONTAS DA TELA TEMPO.
//
// A previsão do tempo serve às operações do dia (pulverizar, colher, plantar)
// e não entra na estimativa de produtividade, que usa o clima observado das
// safras. A tela diz isso.
//
// A janela de pulverização segue a Embrapa Soja (Adegas e Gazziero, 2020,
// Tecnologias de produção de soja, cap. 12, p. 285-289):
//   - temperatura até 30 °C; abaixo de 10 °C a absorção também cai;
//   - umidade relativa acima de 60%;
//   - vento de 3 a 8 km/h; acima de 8 km/h só com ponta antideriva, e nunca
//     acima de 10 km/h; abaixo de 3 km/h as gotas finas ficam suspensas
//     (inversão térmica);
//   - sem chuva logo depois: o intervalo de cada produto está na bula.
// O vento da previsão é a 10 m de altura; o da recomendação é o que se sente
// na lavoura. A conversão para 2 m é a do perfil logarítmico da FAO-56 (Allen
// et al., 1998, eq. 47), que reduz o vento a 75% do de 10 m.
//
// Chuva na hora: 0,1 mm ou mais previsto, ou chance de 50% ou mais. Os dois
// limites são do aplicativo, e não da Embrapa: o menor valor que o modelo
// publica e a chance em que chover passa a ser o mais provável.
//
// Ficam fora da tela, sem nada de Android, para os testes de unidade
// alcançarem sem emulador.

const val TEMPERATURA_MAXIMA = 30.0
const val TEMPERATURA_MINIMA = 10.0
const val UMIDADE_MINIMA = 60.0
const val VENTO_MINIMO = 3.0
const val VENTO_IDEAL_MAXIMO = 8.0
const val VENTO_MAXIMO_ANTIDERIVA = 10.0
const val CHUVA_MINIMA_MM = 0.1
const val CHANCE_DE_CHUVA = 50.0
/** Horas depois da aplicação conferidas para chuva. */
const val HORAS_SEM_CHUVA = 2

/** Vento a 2 m a partir do vento a 10 m (FAO-56, eq. 47: u2 = uz · 4,87 / ln(67,8 z − 5,42)). */
fun ventoA2m(vento10m: Double): Double = vento10m * 4.87 / ln(67.8 * 10 - 5.42)

enum class NivelJanela { BOA, ATENCAO, EVITAR }

data class HoraPulverizacao(
    val hora: LocalDateTime,
    val nivel: NivelJanela,
    val motivos: List<String>,
    val temperatura: Double?,
    val umidade: Double?,
    val vento2m: Double?,
    val chanceChuva: Double?,
)

/** Nível de uma hora e os motivos, do mais grave ao mais leve. */
fun avaliaHora(
    temperatura: Double?,
    umidade: Double?,
    vento10m: Double?,
    chuvaNaHora: Boolean,
    chuvaLogo: Boolean,
): Pair<NivelJanela, List<String>> {
    val evitar = mutableListOf<String>()
    val atencao = mutableListOf<String>()
    val vento = vento10m?.let { ventoA2m(it) }
    if (chuvaNaHora) evitar += "chuva prevista nesta hora"
    if (temperatura != null && temperatura > TEMPERATURA_MAXIMA) evitar += "temperatura acima de 30 °C"
    if (umidade != null && umidade < UMIDADE_MINIMA) evitar += "umidade abaixo de 60%"
    if (vento != null && vento > VENTO_MAXIMO_ANTIDERIVA) evitar += "vento acima de 10 km/h"
    if (vento != null && vento > VENTO_IDEAL_MAXIMO && vento <= VENTO_MAXIMO_ANTIDERIVA)
        atencao += "vento entre 8 e 10 km/h: só com ponta antideriva"
    if (vento != null && vento < VENTO_MINIMO) atencao += "vento abaixo de 3 km/h: gotas finas ficam no ar"
    if (temperatura != null && temperatura < TEMPERATURA_MINIMA) atencao += "temperatura abaixo de 10 °C"
    if (!chuvaNaHora && chuvaLogo) atencao += "chuva prevista nas $HORAS_SEM_CHUVA horas seguintes"
    if (temperatura == null || umidade == null || vento == null) atencao += "previsão incompleta para esta hora"
    val nivel = when {
        evitar.isNotEmpty() -> NivelJanela.EVITAR
        atencao.isNotEmpty() -> NivelJanela.ATENCAO
        else -> NivelJanela.BOA
    }
    return nivel to (evitar + atencao)
}

/** Índice da hora em curso na série horária (ou da primeira depois dela). */
fun indiceDaHora(horas: List<LocalDateTime>, agora: LocalDateTime): Int {
    val inicio = agora.truncatedTo(ChronoUnit.HOURS)
    return horas.indexOfFirst { !it.isBefore(inicio) }
}

/** Avaliação de cada hora a partir da hora em curso. */
fun horasDePulverizacao(h: TempoHorario, agora: LocalDateTime, quantas: Int = 24): List<HoraPulverizacao> {
    val horas = h.time.map { LocalDateTime.parse(it) }
    val inicio = indiceDaHora(horas, agora)
    if (inicio < 0) return emptyList()
    fun chove(i: Int): Boolean {
        if (i >= horas.size) return false
        val mm = h.precipitation.getOrNull(i) ?: 0.0
        val chance = h.precipitation_probability?.getOrNull(i) ?: 0.0
        return mm >= CHUVA_MINIMA_MM || chance >= CHANCE_DE_CHUVA
    }
    return (inicio until minOf(horas.size, inicio + quantas)).map { i ->
        val temp = h.temperature_2m.getOrNull(i)
        val ur = h.relative_humidity_2m.getOrNull(i)
        val v10 = h.wind_speed_10m.getOrNull(i)
        val (nivel, motivos) = avaliaHora(temp, ur, v10, chove(i), (1..HORAS_SEM_CHUVA).any { chove(i + it) })
        HoraPulverizacao(horas[i], nivel, motivos, temp, ur, v10?.let { ventoA2m(it) },
                         h.precipitation_probability?.getOrNull(i))
    }
}

data class Janela(val inicio: LocalDateTime, val fim: LocalDateTime)

/** Primeira sequência de pelo menos [minimo] horas boas; o fim é a hora seguinte à última boa. */
fun proximaJanela(horas: List<HoraPulverizacao>, minimo: Int = 2): Janela? {
    var i = 0
    while (i < horas.size) {
        if (horas[i].nivel != NivelJanela.BOA) { i++; continue }
        var j = i
        while (j + 1 < horas.size && horas[j + 1].nivel == NivelJanela.BOA) j++
        if (j - i + 1 >= minimo) return Janela(horas[i].hora, horas[j].hora.plusHours(1))
        i = j + 1
    }
    return null
}

data class DiaTempo(
    val data: LocalDate,
    val codigo: Int?,
    val maxima: Double?,
    val minima: Double?,
    val chuva: Double?,
    val chance: Double?,
    val ventoMaximo: Double?,
    val rajadaMaxima: Double?,
    val et0: Double?,
    val uv: Double?,
    val nascer: String?,
    val por: String?,
)

fun dias(d: TempoDiario): List<DiaTempo> = d.time.mapIndexed { i, t ->
    DiaTempo(
        data = LocalDate.parse(t),
        codigo = d.weather_code?.getOrNull(i),
        maxima = d.temperature_2m_max?.getOrNull(i),
        minima = d.temperature_2m_min?.getOrNull(i),
        chuva = d.precipitation_sum?.getOrNull(i),
        chance = d.precipitation_probability_max?.getOrNull(i),
        ventoMaximo = d.wind_speed_10m_max?.getOrNull(i),
        rajadaMaxima = d.wind_gusts_10m_max?.getOrNull(i),
        et0 = d.et0_fao_evapotranspiration?.getOrNull(i),
        uv = d.uv_index_max?.getOrNull(i),
        nascer = d.sunrise?.getOrNull(i)?.substringAfter('T'),
        por = d.sunset?.getOrNull(i)?.substringAfter('T'),
    )
}

/** Chuva e evapotranspiração de referência dos dias passados, e a chuva prevista de hoje em diante. */
data class BalancoChuva(
    val chuvaPassada: Double,
    val et0Passada: Double,
    val diasPassados: Int,
    val chuvaPrevista: Double,
    val diasPrevistos: Int,
) {
    val saldo: Double get() = chuvaPassada - et0Passada
}

fun balancoChuva(lista: List<DiaTempo>, hoje: LocalDate): BalancoChuva {
    val passados = lista.filter { it.data.isBefore(hoje) }
    val adiante = lista.filter { !it.data.isBefore(hoje) }
    return BalancoChuva(
        chuvaPassada = passados.sumOf { it.chuva ?: 0.0 },
        et0Passada = passados.sumOf { it.et0 ?: 0.0 },
        diasPassados = passados.size,
        chuvaPrevista = adiante.sumOf { it.chuva ?: 0.0 },
        diasPrevistos = adiante.size,
    )
}

/** Descrição do código de tempo da OMM, como a documentação do Open-Meteo o define. */
fun descricaoTempo(codigo: Int?): String = when (codigo) {
    0 -> "Céu limpo"
    1 -> "Predomínio de sol"
    2 -> "Parcialmente nublado"
    3 -> "Nublado"
    45, 48 -> "Nevoeiro"
    51 -> "Garoa fraca"
    53 -> "Garoa"
    55 -> "Garoa forte"
    56, 57 -> "Garoa congelante"
    61 -> "Chuva fraca"
    63 -> "Chuva moderada"
    65 -> "Chuva forte"
    66, 67 -> "Chuva congelante"
    71, 73, 75, 77 -> "Neve"
    80 -> "Pancadas de chuva fracas"
    81 -> "Pancadas de chuva"
    82 -> "Pancadas de chuva fortes"
    85, 86 -> "Pancadas de neve"
    95 -> "Trovoada"
    96, 99 -> "Trovoada com granizo"
    97 -> "Trovoada forte"
    else -> "Sem descrição"
}

/** De onde o vento vem, em oito direções. */
fun direcaoVento(graus: Double?): String {
    if (graus == null) return ""
    val nomes = listOf("N", "NE", "L", "SE", "S", "SO", "O", "NO")
    return nomes[(((graus % 360) + 360) % 360 / 45.0).roundToInt() % 8]
}

/** Categoria do índice ultravioleta pela escala da OMS. */
fun categoriaUv(uv: Double?): String? = uv?.roundToInt()?.let {
    when {
        it <= 2 -> "baixo"
        it <= 5 -> "moderado"
        it <= 7 -> "alto"
        it <= 10 -> "muito alto"
        else -> "extremo"
    }
}

/** Coordenada arredondada a 0,01° (cerca de 1 km): basta à previsão e não expõe a sede da fazenda. */
fun arredonda(c: Double): Double = Math.round(c * 100) / 100.0
