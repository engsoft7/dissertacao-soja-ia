package com.agrointeligencia.app

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import java.time.LocalDateTime
import java.util.Locale
import kotlin.math.roundToInt

// LEITURA EM VOZ ALTA
//
// O botão de alto-falante no Resumo e no Tempo lê o que a tela mostra, com a
// voz do próprio Android (TextToSpeech), no idioma do aparelho: para quem está
// na lavoura com as mãos ocupadas, ou lê com dificuldade. A síntese é a do
// sistema, e nada sai do celular. Os textos falados trocam as abreviações
// ("kg/ha", "°C", "7h") por palavras, que a voz lê melhor.

class Leitor(context: Context) : TextToSpeech.OnInitListener {
    // internal: o teste confere o que foi falado (ShadowTextToSpeech).
    internal val tts = TextToSpeech(context.applicationContext, this)
    var falando by mutableStateOf(false)
        private set
    var indisponivel by mutableStateOf(false)
        private set
    private var pronto = false
    private var pendente: String? = null

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) {
            indisponivel = true
            falando = false
            return
        }
        val idioma = tts.setLanguage(Locale.getDefault())
        if (idioma == TextToSpeech.LANG_MISSING_DATA || idioma == TextToSpeech.LANG_NOT_SUPPORTED) {
            tts.setLanguage(Locale("pt", "BR"))
        }
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) { falando = true }
            override fun onDone(utteranceId: String?) { falando = false }
            @Deprecated("Substituído por onError(String, Int) no Android 5", ReplaceWith(""))
            override fun onError(utteranceId: String?) { falando = false }
        })
        pronto = true
        pendente?.let { pendente = null; fala(it) }
    }

    /** Lê [texto] do começo, interrompendo o que estiver lendo. */
    fun fala(texto: String) {
        if (!pronto) {
            pendente = texto
            falando = true
            return
        }
        falando = tts.speak(texto, TextToSpeech.QUEUE_FLUSH, null, "agrointeligencia") == TextToSpeech.SUCCESS
    }

    fun para() {
        pendente = null
        if (pronto) tts.stop()
        falando = false
    }

    fun encerra() {
        para()
        tts.shutdown()
    }
}

/** Troca as abreviações dos textos da tela por palavras, para a voz. */
fun paraFala(context: Context, texto: String): String = texto
    .replace("kg/ha", context.getString(R.string.fala_kg_ha))
    .replace("±", context.getString(R.string.fala_mais_ou_menos))
    .replace(" · ", ", ")
    .replace("R$ −", context.getString(R.string.fala_menos) + " R$ ")

/** O resumo (Relatorio.kt) em texto corrido para ler em voz alta: título, seções e linhas, sem o rodapé. */
fun falaDoResumo(context: Context, r: Relatorio): String = buildString {
    append(r.titulo.substringAfter(" · ")).append(". ")
    r.secoes.forEach { s ->
        append(s.titulo).append(". ")
        s.linhas.forEach { append(it.trimEnd('.')).append(". ") }
    }
}.let { paraFala(context, it).trim() }

private fun pulverizarAgora(context: Context, n: NivelJanela): String = context.getString(when (n) {
    NivelJanela.BOA -> R.string.fala_pulverizar_boa
    NivelJanela.ATENCAO -> R.string.fala_pulverizar_atencao
    NivelJanela.EVITAR -> R.string.fala_pulverizar_evitar
})

private fun janelaFalada(context: Context, j: Janela, agora: LocalDateTime): String = when (diaDaJanela(j, agora)) {
    QuandoJanela.HOJE -> context.getString(R.string.fala_janela_hoje, j.inicio.hour, j.fim.hour)
    QuandoJanela.AMANHA -> context.getString(R.string.fala_janela_amanha, j.inicio.hour, j.fim.hour)
    QuandoJanela.OUTRO_DIA -> context.getString(R.string.fala_janela_dia, dataCurta(j.inicio.toLocalDate().toString()),
                                                 j.inicio.hour, j.fim.hour)
}

/**
 * O tempo de agora, os avisos do INMET, a pulverização e o dia de hoje, em
 * frases para a voz. Null sem previsão.
 */
fun falaDoTempo(context: Context, p: PrevisaoTempo?, avisos: AvisosResponse?, lugar: String, agora: LocalDateTime): String? {
    val a = p?.current ?: return null
    val partes = mutableListOf<String>()
    val temperatura = a.temperature_2m?.roundToInt()
    val umidade = a.relative_humidity_2m?.roundToInt()
    val vento = a.wind_speed_10m?.let { ventoA2m(it).roundToInt() }
    if (temperatura != null && umidade != null && vento != null) {
        partes += context.getString(R.string.fala_tempo_agora, lugar, temperatura, descricaoTempo(a.weather_code).lowercase(PT_BR),
                                    umidade, vento)
    }
    avisos?.avisos?.takeIf { it.isNotEmpty() }?.let { partes += resumoDosAvisos(it) }
    p.hourly?.let { h ->
        val horas = horasDePulverizacao(h, agora)
        horas.firstOrNull()?.let { partes += pulverizarAgora(context, it.nivel) }
        partes += proximaJanela(horas)?.let { context.getString(R.string.fala_proxima_janela, janelaFalada(context, it, agora)) }
            ?: context.getString(R.string.fala_sem_janela, horas.size)
    }
    p.daily?.let { d -> dias(d).firstOrNull { it.data == agora.toLocalDate() } }?.let { hoje ->
        val max = hoje.maxima?.roundToInt()
        val min = hoje.minima?.roundToInt()
        if (max != null && min != null) {
            partes += context.getString(R.string.fala_hoje, max, min, (hoje.chance ?: 0.0).roundToInt())
        }
    }
    return partes.joinToString(" ") { it.trimEnd('.') + "." }.takeIf { partes.isNotEmpty() }
}

/** O botão de ouvir: alto-falante para ler, quadrado para parar. */
@Composable
fun BotaoOuvir(falando: Boolean, rotulo: String, aoTocar: () -> Unit) {
    OutlinedButton(onClick = aoTocar, modifier = Modifier.heightIn(min = 48.dp)) {
        Icon(if (falando) Icons.Filled.Stop else Icons.AutoMirrored.Filled.VolumeUp, contentDescription = null,
             modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(6.dp))
        Text(if (falando) stringResource(R.string.fala_parar) else rotulo)
    }
}
