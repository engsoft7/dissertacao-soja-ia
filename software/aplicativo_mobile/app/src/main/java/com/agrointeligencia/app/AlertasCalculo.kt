package com.agrointeligencia.app

import java.time.LocalDate
import java.time.LocalDateTime

// AS REGRAS DOS ALERTAS
//
// O celular confere, em segundo plano e a cada 3 horas, o que o produtor ligou
// na tela Alertas (Alertas.kt): os avisos do INMET para o lugar, a próxima
// janela boa de pulverização e o preço da saca numa praça. As decisões ficam
// aqui, sem Android, e são testadas em AlertasCalculoTest:
// - o que já virou notificação não vira de novo;
// - janela de pulverização e preço não tocam de madrugada (o aviso do INMET,
//   sim: o de tempestade não espera amanhecer);
// - uma notificação de pulverização por dia, porque a previsão muda a cada
//   rodada e o produtor não quer três avisos sobre a mesma manhã;
// - o preço avisa quando chega ao alvo e só volta a avisar depois de cair
//   abaixo dele.

/** Horas em que a janela de pulverização e o preço podem notificar: das 6h às 20h59. */
val HORAS_DE_NOTIFICAR = 6..20

/** Horas do dia em que começa uma janela de pulverização que interessa avisar. */
val HORAS_DE_PULVERIZAR = 5..18

/** "2026-10-26 00:00", como o INMET publica, para data e hora; null se não der para ler. */
fun horaDoAviso(t: String?): LocalDateTime? {
    val m = Regex("""(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})""").find(t ?: "") ?: return null
    val (ano, mes, dia, hora, minuto) = m.destructured
    return runCatching { LocalDateTime.of(ano.toInt(), mes.toInt(), dia.toInt(), hora.toInt(), minuto.toInt()) }.getOrNull()
}

/** Os avisos do INMET que ainda não viraram notificação e não terminaram. */
fun avisosParaNotificar(
    avisos: List<AvisoMeteorologico>,
    jaNotificados: Set<String>,
    agora: LocalDateTime,
): List<AvisoMeteorologico> =
    avisos.filter { it.id !in jaNotificados && horaDoAviso(it.fim)?.isBefore(agora) != true }

/** Todas as sequências de pelo menos [minimo] horas boas, na ordem (proximaJanela dá só a primeira). */
fun janelasBoas(horas: List<HoraPulverizacao>, minimo: Int = 2): List<Janela> {
    val saida = mutableListOf<Janela>()
    var i = 0
    while (i < horas.size) {
        if (horas[i].nivel != NivelJanela.BOA) { i++; continue }
        var j = i
        while (j + 1 < horas.size && horas[j + 1].nivel == NivelJanela.BOA) j++
        if (j - i + 1 >= minimo) saida += Janela(horas[i].hora, horas[j].hora.plusHours(1))
        i = j + 1
    }
    return saida
}

/**
 * A janela de pulverização que vale notificar agora: a primeira que começa de
 * dia (HORAS_DE_PULVERIZAR), nas próximas [horizonte] horas, num dia que ainda
 * não teve aviso. Nula de madrugada e quando não há janela assim.
 */
fun janelaParaNotificar(
    horas: List<HoraPulverizacao>,
    agora: LocalDateTime,
    ultimoDiaAvisado: LocalDate?,
    horizonte: Long = 18,
): Janela? {
    if (agora.hour !in HORAS_DE_NOTIFICAR) return null
    return janelasBoas(horas).firstOrNull { j ->
        j.inicio.hour in HORAS_DE_PULVERIZAR &&
            !j.inicio.isAfter(agora.plusHours(horizonte)) &&
            j.fim.isAfter(agora) &&
            j.inicio.toLocalDate() != ultimoDiaAvisado
    }
}

/**
 * Se a cotação do dia na praça chegou ao preço-alvo. Devolve (notificar, novo
 * estado): notifica uma vez ao chegar e só de novo depois que a cotação cair
 * abaixo do alvo. Cotação parada (mais de uma semana, Pracas.kt) não conta, e
 * sem cotação o estado fica como estava.
 */
fun precoParaNotificar(
    praca: PracaPara?,
    alvo: Double?,
    jaAvisado: Boolean,
    agora: LocalDateTime,
): Pair<Boolean, Boolean> {
    if (praca == null || alvo == null || alvo <= 0.0 || !cotacaoEmDia(praca, agora.toLocalDate())) {
        return false to jaAvisado
    }
    val chegou = praca.valor >= alvo
    if (chegou && agora.hour !in HORAS_DE_NOTIFICAR) return false to jaAvisado
    return (chegou && !jaAvisado) to chegou
}

/** "hoje", "amanhã" ou "dd/MM", para o texto da notificação. */
enum class QuandoJanela { HOJE, AMANHA, OUTRO_DIA }

fun diaDaJanela(j: Janela, agora: LocalDateTime): QuandoJanela = when (j.inicio.toLocalDate()) {
    agora.toLocalDate() -> QuandoJanela.HOJE
    agora.toLocalDate().plusDays(1) -> QuandoJanela.AMANHA
    else -> QuandoJanela.OUTRO_DIA
}
