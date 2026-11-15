package com.agrointeligencia.app

import android.content.Context
import android.content.SharedPreferences
import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.gson.Gson
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Query
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt

// A TELA TEMPO: AGORA, JANELA DE PULVERIZAÇÃO, AVISOS, 7 DIAS E CHUVA.
//
// A previsão vem direto do Open-Meteo (https://open-meteo.com, dados sob CC BY
// 4.0, gratuito para uso não comercial), sem passar pela API do produto. Assim
// a tela abre em segundos mesmo com a API dormindo no plano gratuito do
// Render, e o limite diário da fonte conta por celular, e não para o servidor
// inteiro. Só os avisos do INMET passam pela API, que reduz a lista do país
// inteiro (mais de 300 kB) aos avisos do lugar.
//
// O lugar é a sede do município escolhido ou, se o produtor pedir, a posição
// do GPS: num município do tamanho de São Félix do Xingu a fazenda pode estar
// a centenas de quilômetros da sede. A posição vai arredondada a cerca de 1 km.
//
// As contas (janela de pulverização, balanço de chuva) estão em TempoCalculo.kt.

// ── resposta do Open-Meteo ────────────────────────────────────────────────

data class TempoAtual(
    val time: String? = null,
    val temperature_2m: Double? = null,
    val relative_humidity_2m: Double? = null,
    val apparent_temperature: Double? = null,
    val precipitation: Double? = null,
    val weather_code: Int? = null,
    val wind_speed_10m: Double? = null,
    val wind_gusts_10m: Double? = null,
    val wind_direction_10m: Double? = null,
    val is_day: Int? = null
)

data class TempoHorario(
    val time: List<String> = emptyList(),
    val temperature_2m: List<Double?> = emptyList(),
    val relative_humidity_2m: List<Double?> = emptyList(),
    val precipitation_probability: List<Double?>? = null,
    val precipitation: List<Double?> = emptyList(),
    val wind_speed_10m: List<Double?> = emptyList(),
    val wind_gusts_10m: List<Double?>? = null,
    val weather_code: List<Int?>? = null
)

data class TempoDiario(
    val time: List<String> = emptyList(),
    val weather_code: List<Int?>? = null,
    val temperature_2m_max: List<Double?>? = null,
    val temperature_2m_min: List<Double?>? = null,
    val precipitation_sum: List<Double?>? = null,
    val precipitation_probability_max: List<Double?>? = null,
    val wind_speed_10m_max: List<Double?>? = null,
    val wind_gusts_10m_max: List<Double?>? = null,
    val et0_fao_evapotranspiration: List<Double?>? = null,
    val uv_index_max: List<Double?>? = null,
    val sunrise: List<String?>? = null,
    val sunset: List<String?>? = null
)

data class PrevisaoTempo(
    val latitude: Double? = null,
    val longitude: Double? = null,
    val elevation: Double? = null,
    val timezone: String? = null,
    val current: TempoAtual? = null,
    val hourly: TempoHorario? = null,
    val daily: TempoDiario? = null
)

interface OpenMeteoService {
    @GET("v1/forecast")
    suspend fun previsao(
        @Query("latitude") latitude: Double,
        @Query("longitude") longitude: Double,
        @Query("current") atual: String,
        @Query("hourly") horario: String,
        @Query("daily") diario: String,
        @Query("past_days") diasPassados: Int,
        @Query("forecast_days") diasAdiante: Int,
        @Query("timezone") fuso: String
    ): PrevisaoTempo
}

object OpenMeteo {
    private const val BASE_URL = "https://api.open-meteo.com/"
    private const val ATUAL = "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation," +
        "weather_code,wind_speed_10m,wind_gusts_10m,wind_direction_10m,is_day"
    private const val HORARIO = "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation," +
        "wind_speed_10m,wind_gusts_10m,weather_code"
    private const val DIARIO = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum," +
        "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,et0_fao_evapotranspiration," +
        "uv_index_max,sunrise,sunset"

    private val api: OpenMeteoService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(20, TimeUnit.SECONDS).build())
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(OpenMeteoService::class.java)
    }

    /** Sete dias para trás (chuva e evapotranspiração) e sete para a frente, no fuso do lugar. */
    suspend fun previsao(lat: Double, lon: Double): PrevisaoTempo =
        api.previsao(arredonda(lat), arredonda(lon), ATUAL, HORARIO, DIARIO, 7, 7, "auto")
}

// ── o lugar ───────────────────────────────────────────────────────────────

/** Ponto da previsão; o geocódigo IBGE vai junto quando é sede de município, para os avisos. */
data class LugarTempo(val nome: String, val lat: Double, val lon: Double, val geocode: String?)

/**
 * Sedes dos 38 municípios do produto, de pesquisa/dados/municipios_para.csv,
 * com as chaves nos nomes que a API devolve em /api/municipios.
 */
val SEDES_MUNICIPAIS: Map<String, LugarTempo> = mapOf(
    "Abel Figueiredo" to LugarTempo("Abel Figueiredo", -4.95333, -48.3933, "1500131"),
    "Água Azul do Norte" to LugarTempo("Água Azul do Norte", -6.79053, -50.4791, "1500347"),
    "Altamira" to LugarTempo("Altamira", -3.20407, -52.21, "1500602"),
    "Belterra" to LugarTempo("Belterra", -2.63609, -54.9374, "1501451"),
    "Brejo Grande do Araguaia" to LugarTempo("Brejo Grande do Araguaia", -5.69822, -48.4103, "1501758"),
    "Breu Branco" to LugarTempo("Breu Branco", -3.77191, -49.5735, "1501782"),
    "Conceição do Araguaia" to LugarTempo("Conceição do Araguaia", -8.26136, -49.2689, "1502707"),
    "Cumaru do Norte" to LugarTempo("Cumaru do Norte", -7.81097, -50.7698, "1502764"),
    "Curionópolis" to LugarTempo("Curionópolis", -6.09965, -49.6068, "1502772"),
    "Dom Eliseu" to LugarTempo("Dom Eliseu", -4.285, -47.505, "1502939"),
    "Floresta do Araguaia" to LugarTempo("Floresta do Araguaia", -7.55335, -49.7125, "1503044"),
    "Goianésia do Pará" to LugarTempo("Goianésia do Pará", -3.84338, -49.0974, "1503093"),
    "Ipixuna do Pará" to LugarTempo("Ipixuna do Pará", -2.55992, -47.5059, "1503457"),
    "Jacareacanga" to LugarTempo("Jacareacanga", -6.21469, -57.7544, "1503754"),
    "Jacundá" to LugarTempo("Jacundá", -4.44617, -49.1153, "1503804"),
    "Marabá" to LugarTempo("Marabá", -5.38075, -49.1327, "1504208"),
    "Monte Alegre" to LugarTempo("Monte Alegre", -1.99768, -54.0724, "1504802"),
    "Novo Progresso" to LugarTempo("Novo Progresso", -7.14347, -55.3786, "1505031"),
    "Paragominas" to LugarTempo("Paragominas", -3.00212, -47.3527, "1505502"),
    "Pau D'Arco" to LugarTempo("Pau D'Arco", -7.83874, -50.04423, "1505551"),
    "Piçarra" to LugarTempo("Piçarra", -6.43778, -48.8716, "1505635"),
    "Placas" to LugarTempo("Placas", -3.86813, -54.2124, "1505650"),
    "Redenção" to LugarTempo("Redenção", -8.02529, -50.0317, "1506138"),
    "Rio Maria" to LugarTempo("Rio Maria", -7.31236, -50.0379, "1506161"),
    "Rondon do Pará" to LugarTempo("Rondon do Pará", -4.77793, -48.067, "1506187"),
    "Rurópolis" to LugarTempo("Rurópolis", -4.10028, -54.9092, "1506195"),
    "Santa Maria das Barreiras" to LugarTempo("Santa Maria das Barreiras", -8.85784, -49.7215, "1506583"),
    "Santana do Araguaia" to LugarTempo("Santana do Araguaia", -9.3281, -50.35, "1506708"),
    "Santarém" to LugarTempo("Santarém", -2.43849, -54.6996, "1506807"),
    "São Félix do Xingu" to LugarTempo("São Félix do Xingu", -6.64254, -51.9904, "1507300"),
    "São João do Araguaia" to LugarTempo("São João do Araguaia", -5.36334, -48.7926, "1507508"),
    "Sapucaia" to LugarTempo("Sapucaia", -6.94018, -49.6834, "1507755"),
    "Tailândia" to LugarTempo("Tailândia", -2.94584, -48.9489, "1507953"),
    "Tomé-Açu" to LugarTempo("Tomé-Açu", -2.41302, -48.1415, "1508001"),
    "Tucumã" to LugarTempo("Tucumã", -6.74687, -51.1626, "1508084"),
    "Ulianópolis" to LugarTempo("Ulianópolis", -3.75007, -47.4892, "1508126"),
    "Uruará" to LugarTempo("Uruará", -3.71519, -53.7396, "1508159"),
    "Xinguara" to LugarTempo("Xinguara", -7.0983, -49.9437, "1508407"),
)

private const val PREF_TEMPO_GPS = "tempo_usar_gps"
private const val PREF_TEMPO_GPS_LAT = "tempo_gps_lat"
private const val PREF_TEMPO_GPS_LON = "tempo_gps_lon"
// Previsão guardada há menos que isso não é baixada de novo ao abrir a tela.
private const val VALIDADE_PREVISAO_MS = 30 * 60 * 1000L

/**
 * Estado da previsão, compartilhado entre o cartão do Resumo e a tela Tempo.
 * A última previsão de cada lugar fica guardada no aparelho: sem rede, a
 * tela mostra a última, com a hora em que foi obtida.
 */
class EstadoTempo(private val prefs: SharedPreferences, private val nomeDoGps: String = "Sua localização") {
    private val gson = Gson()
    var lugar by mutableStateOf<LugarTempo?>(null)
        private set
    var previsao by mutableStateOf<PrevisaoTempo?>(null)
        private set
    var obtidaEm by mutableStateOf(0L)
        private set
    var avisos by mutableStateOf<AvisosResponse?>(null)
        private set
    var carregando by mutableStateOf(false)
        private set
    var falhou by mutableStateOf(false)
        private set
    var usarGps by mutableStateOf(prefs.getBoolean(PREF_TEMPO_GPS, false))
        private set
    var gps by mutableStateOf(lerGps())
        private set

    private fun lerGps(): LugarTempo? {
        val lat = prefs.getFloat(PREF_TEMPO_GPS_LAT, Float.NaN)
        val lon = prefs.getFloat(PREF_TEMPO_GPS_LON, Float.NaN)
        return if (lat.isNaN() || lon.isNaN()) null else LugarTempo(nomeDoGps, lat.toDouble(), lon.toDouble(), null)
    }

    /** O lugar da previsão: o GPS, quando o produtor escolheu e já há posição; senão a sede do município. */
    /** As sedes do estado escolhido (Estados.kt); no Pará, as do aplicativo. */
    var sedes by mutableStateOf(SEDES_MUNICIPAIS)

    fun lugarPara(municipio: String?): LugarTempo? =
        gps.takeIf { usarGps } ?: municipio?.let { sedes[it] }

    fun usarMunicipio() {
        usarGps = false
        prefs.edit().putBoolean(PREF_TEMPO_GPS, false).apply()
    }

    fun usarPosicao(lat: Double, lon: Double) {
        val l = LugarTempo(nomeDoGps, arredonda(lat), arredonda(lon), null)
        gps = l
        usarGps = true
        prefs.edit().putBoolean(PREF_TEMPO_GPS, true)
            .putFloat(PREF_TEMPO_GPS_LAT, l.lat.toFloat()).putFloat(PREF_TEMPO_GPS_LON, l.lon.toFloat()).apply()
    }

    private fun chave(l: LugarTempo) = "tempo_${arredonda(l.lat)}_${arredonda(l.lon)}"

    /** Mostra o que está guardado do lugar e baixa de novo se estiver velho (ou se [forcar]). */
    suspend fun carrega(l: LugarTempo, forcar: Boolean = false) {
        val k = chave(l)
        if (lugar != l) {
            lugar = l
            falhou = false
            previsao = prefs.getString(k, null)?.let { runCatching { gson.fromJson(it, PrevisaoTempo::class.java) }.getOrNull() }
            obtidaEm = if (previsao != null) prefs.getLong(k + "_em", 0L) else 0L
            avisos = prefs.getString("avisos_$k", null)?.let { runCatching { gson.fromJson(it, AvisosResponse::class.java) }.getOrNull() }
        }
        if (!forcar && previsao != null && System.currentTimeMillis() - obtidaEm < VALIDADE_PREVISAO_MS) return
        carregando = true
        try {
            val p = OpenMeteo.previsao(l.lat, l.lon)
            if (lugar != l) return
            previsao = p
            obtidaEm = System.currentTimeMillis()
            falhou = false
            prefs.edit().putString(k, gson.toJson(p)).putLong(k + "_em", obtidaEm).apply()
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (_: Exception) {
            if (lugar == l) falhou = true
        } finally {
            if (lugar == l) carregando = false
        }
        // Os avisos dependem da API, que pode levar um minuto para acordar; a
        // previsão já está na tela enquanto isso.
        try {
            val a = RetrofitClient.getInstance().getAvisos(l.lat, l.lon, l.geocode)
            if (lugar != l) return
            avisos = a
            if (a.disponivel) prefs.edit().putString("avisos_$k", gson.toJson(a)).apply()
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (_: Exception) {
            // mantém os guardados, se houver; sem nenhum, a tela diz que não conseguiu consultar
            if (lugar == l && avisos == null) avisos = AvisosResponse(disponivel = false)
        }
    }
}

// ── formatação ────────────────────────────────────────────────────────────

// Os eventos e níveis do INMET que o app conhece, para o inglês; os outros
// ficam como o INMET publica. Os riscos e as orientações vêm só em português.
private val EVENTOS_INMET = mapOf(
    "tempestade" to R.string.inmet_tempestade,
    "chuvas intensas" to R.string.inmet_chuvas_intensas,
    "acumulado de chuva" to R.string.inmet_acumulado_chuva,
    "vendaval" to R.string.inmet_vendaval,
    "baixa umidade" to R.string.inmet_baixa_umidade,
    "onda de calor" to R.string.inmet_onda_calor,
    "onda de frio" to R.string.inmet_onda_frio,
    "declínio de temperatura" to R.string.inmet_declinio_temperatura,
    "geada" to R.string.inmet_geada,
    "granizo" to R.string.inmet_granizo,
    "perigo potencial" to R.string.inmet_sev_perigo_potencial,
    "perigo" to R.string.inmet_sev_perigo,
    "grande perigo" to R.string.inmet_sev_grande_perigo,
)

/** O nome de um evento ou nível do INMET no idioma do app, ou como veio, se o app não o conhece. */
fun nomeDoInmet(context: Context, nome: String): String =
    EVENTOS_INMET[nome.trim().lowercase(java.util.Locale.ROOT)]?.let { context.getString(it) } ?: nome

private fun localDe(context: Context) = context.resources.configuration.locales[0]

/**
 * "2 avisos do INMET: tempestade". Dois avisos do mesmo evento, com outro nível
 * ou outro horário, apareciam como "tempestade, tempestade" no cartão do Resumo
 * (Teste Premium de 14/11/2026): o nome entra uma vez, e a contagem é a da lista.
 */
fun resumoDosAvisos(context: Context, avisos: List<AvisoMeteorologico>): String {
    val nomes = avisos.map { a -> a.evento?.let { nomeDoInmet(context, it) } ?: context.getString(R.string.tempo_aviso) }
        .map { it.lowercase(localDe(context)) }.distinct()
    return context.resources.getQuantityString(R.plurals.tempo_resumo_avisos, avisos.size, avisos.size,
                                               nomes.joinToString(", "))
}

private fun graus(v: Double?) = v?.let { "${it.roundToInt()} °C" } ?: "–"
private fun mm(v: Double) = if (v < 10) String.format(LOCAL_NUMEROS, "%.1f mm", v) else "${v.roundToInt()} mm"

/** A hora cheia: "7h" em português, "7:00" em inglês. */
fun horaCurta(context: Context, t: LocalDateTime): String = context.getString(R.string.formato_hora, t.hour)

private fun diaDaSemana(context: Context, d: LocalDate): String =
    d.format(DateTimeFormatter.ofPattern(context.getString(R.string.tempo_formato_dia_semana), localDe(context)))
        .replaceFirstChar { it.uppercase() }.replace(".", "")

private fun nomeDoDia(context: Context, d: LocalDate, hoje: LocalDate): String = when (d) {
    hoje -> context.getString(R.string.tempo_hoje)
    hoje.plusDays(1) -> context.getString(R.string.tempo_amanha)
    else -> diaDaSemana(context, d)
}

private fun quandoJanela(context: Context, j: Janela, agora: LocalDateTime): String {
    val ini = horaCurta(context, j.inicio)
    val fim = horaCurta(context, j.fim)
    return when (diaDaJanela(j, agora)) {
        QuandoJanela.HOJE -> context.getString(R.string.tempo_janela_hoje, ini, fim)
        QuandoJanela.AMANHA -> context.getString(R.string.tempo_janela_amanha, ini, fim)
        QuandoJanela.OUTRO_DIA -> context.getString(R.string.tempo_janela_dia, diaDaSemana(context, j.inicio.toLocalDate()), ini, fim)
    }
}

/** O motivo de uma hora não ser boa, com os limites da conta (TempoCalculo.kt). */
fun textoDoMotivo(context: Context, m: MotivoHora): String = context.getString(m.texto, *m.limites.toTypedArray())

fun iconeTempo(codigo: Int?, dia: Boolean = true): ImageVector = when (codigo) {
    0, 1 -> if (dia) Icons.Filled.WbSunny else Icons.Filled.NightsStay
    2 -> Icons.Filled.WbCloudy
    3, 45, 48 -> Icons.Filled.Cloud
    in 51..67, in 80..86 -> Icons.Filled.Umbrella
    95, 96, 97, 99 -> Icons.Filled.FlashOn
    else -> Icons.Filled.Cloud
}

@Composable
private fun corDoNivel(n: NivelJanela): Color {
    val escuro = isSystemInDarkTheme()
    return when (n) {
        NivelJanela.BOA -> if (escuro) Color(0xFF3fb950) else Color(0xFF15803d)
        NivelJanela.ATENCAO -> if (escuro) Color(0xFFd29922) else Color(0xFFb45309)
        NivelJanela.EVITAR -> if (escuro) Color(0xFFf85149) else Color(0xFFb91c1c)
    }
}

private fun nomeDoNivel(context: Context, n: NivelJanela) = context.getString(when (n) {
    NivelJanela.BOA -> R.string.nivel_boa
    NivelJanela.ATENCAO -> R.string.nivel_atencao
    NivelJanela.EVITAR -> R.string.nivel_evitar
})

/** Instante "agora" no fuso do lugar da previsão. */
fun agoraNoLugar(p: PrevisaoTempo?): LocalDateTime =
    LocalDateTime.now(runCatching { ZoneId.of(p?.timezone ?: "America/Belem") }.getOrDefault(ZoneId.of("America/Belem")))

// ── cartão do Resumo ──────────────────────────────────────────────────────

/** Tempo de agora e a pulverização desta hora, no alto do Resumo; o toque abre a tela Tempo. */
@Composable
fun TempoResumoCard(estado: EstadoTempo, aoAbrir: () -> Unit) {
    val p = estado.previsao
    val agora = agoraNoLugar(p)
    val atual = p?.current
    val horaAgora = p?.hourly?.let { horasDePulverizacao(it, agora, 1).firstOrNull() }
    val avisos = estado.avisos?.avisos.orEmpty()
    val context = LocalContext.current
    Card(
        onClick = aoAbrir,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(16.dp)) {
            Icon(iconeTempo(atual?.weather_code, atual?.is_day != 0), contentDescription = null,
                 tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(32.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.tempo_em, estado.lugar?.nome ?: "…"), fontSize = 12.sp,
                     color = MaterialTheme.colorScheme.onSurfaceVariant)
                when {
                    atual != null -> Text("${graus(atual.temperature_2m)} · ${stringResource(descricaoTempo(atual.weather_code))}",
                                          fontWeight = FontWeight.SemiBold, fontSize = 16.sp,
                                          color = MaterialTheme.colorScheme.onSurface)
                    estado.carregando -> Text(stringResource(R.string.tempo_carregando), fontSize = 14.sp,
                                              color = MaterialTheme.colorScheme.onSurface)
                    else -> Text(stringResource(R.string.tempo_indisponivel_toque), fontSize = 14.sp,
                                 color = MaterialTheme.colorScheme.onSurface)
                }
                horaAgora?.let {
                    Text(stringResource(R.string.tempo_pulverizar_agora, nomeDoNivel(context, it.nivel)) +
                         (it.motivos.firstOrNull()?.let { m -> " (${textoDoMotivo(context, m).substringBefore(':')})" } ?: ""),
                         fontSize = 13.sp, color = corDoNivel(it.nivel), fontWeight = FontWeight.SemiBold)
                }
                if (avisos.isNotEmpty()) {
                    Text(resumoDosAvisos(context, avisos),
                         fontSize = 13.sp, color = corDoNivel(NivelJanela.ATENCAO), fontWeight = FontWeight.SemiBold)
                }
            }
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = stringResource(R.string.tempo_abrir),
                 tint = MaterialTheme.colorScheme.primary)
        }
    }
}

// ── a tela Tempo ──────────────────────────────────────────────────────────

/** A tela com rede e GPS; o desenho em si é [TempoConteudo]. */
@Composable
fun TempoTela(estado: EstadoTempo, municipio: String?, ouvir: @Composable () -> Unit = {}, aoVoltar: () -> Unit) {
    val lugar = estado.lugarPara(municipio)
    // A carga ao mudar de lugar é feita no AgroDashboard, que serve também o
    // cartão do Resumo; aqui só o botão de atualizar.
    var atualizar by remember { mutableStateOf(0) }
    LaunchedEffect(atualizar) { if (atualizar > 0) lugar?.let { estado.carrega(it, forcar = true) } }
    TempoConteudo(
        previsao = estado.previsao,
        avisos = estado.avisos,
        lugar = lugar,
        agora = agoraNoLugar(estado.previsao),
        obtidaEm = estado.obtidaEm.takeIf { it > 0 },
        carregando = estado.carregando,
        falhou = estado.falhou,
        aoVoltar = aoVoltar
    ) {
        EscolhaDoLugar(estado, municipio) { atualizar++ }
        // Ler em voz alta (Fala.kt), quando o AgroDashboard o oferece.
        ouvir()
    }
}

/** Sede do município ou posição do GPS, e o botão de atualizar. */
@Composable
private fun EscolhaDoLugar(estado: EstadoTempo, municipio: String?, aoAtualizar: () -> Unit) {
    var mensagem by remember { mutableStateOf<String?>(null) }
    // A leitura da posição é a mesma da escolha do município (Localizacao.kt).
    val leitor = rememberLeitorDePosicao(
        semPermissao = stringResource(R.string.tempo_sem_permissao),
        aoFalhar = { mensagem = it }
    ) { lat, lon ->
        mensagem = null
        estado.usarPosicao(lat, lon)
    }

    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(selected = !estado.usarGps, onClick = { estado.usarMunicipio() },
                   label = { Text(municipio ?: stringResource(R.string.mun_rotulo), maxLines = 1) },
                   leadingIcon = { Icon(Icons.Filled.LocationCity, contentDescription = null, modifier = Modifier.size(18.dp)) },
                   modifier = Modifier.weight(1f, fill = false))
        FilterChip(selected = estado.usarGps, onClick = { mensagem = null; leitor.ler() },
                   label = { Text(stringResource(R.string.tempo_minha_localizacao), maxLines = 1) },
                   leadingIcon = { Icon(Icons.Filled.MyLocation, contentDescription = null, modifier = Modifier.size(18.dp)) })
        IconButton(onClick = aoAtualizar) { Icon(Icons.Filled.Refresh, contentDescription = stringResource(R.string.tempo_atualizar)) }
    }
    if (leitor.procurando) {
        LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp))
        Text(stringResource(R.string.mun_procurando), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    mensagem?.let { Text(it, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
}

/**
 * A tela Tempo sem rede: recebe os dados prontos. Separada de [TempoTela]
 * para poder ser desenhada nas capturas de tela automáticas.
 */
@Composable
fun TempoConteudo(
    previsao: PrevisaoTempo?,
    avisos: AvisosResponse?,
    lugar: LugarTempo?,
    agora: LocalDateTime,
    obtidaEm: Long?,
    carregando: Boolean,
    falhou: Boolean,
    aoVoltar: () -> Unit = {},
    controles: @Composable () -> Unit = {}
) {
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = aoVoltar) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.voltar_ao_resumo))
            }
            Text(stringResource(R.string.tempo_titulo), fontWeight = FontWeight.Bold, fontSize = 20.sp,
                 color = MaterialTheme.colorScheme.onBackground)
        }
        controles()
        lugar?.let {
            Text(stringResource(if (it.geocode != null) R.string.tempo_na_sede else R.string.tempo_arredondada, it.nome),
                 fontSize = 12.sp, color = secundaria)
        }

        when {
            previsao == null && carregando ->
                CircularProgressIndicator(modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally))
            previsao == null ->
                Text(stringResource(if (falhou) R.string.tempo_falhou else R.string.tempo_escolha_municipio),
                     fontSize = 14.sp, color = secundaria)
            else -> {
                if (falhou) {
                    Text(stringResource(R.string.tempo_sem_conexao), fontSize = 12.sp,
                         color = corDoNivel(NivelJanela.ATENCAO), fontWeight = FontWeight.SemiBold)
                }
                val listaDias = previsao.daily?.let { dias(it) }.orEmpty()
                val hoje = listaDias.firstOrNull { it.data == agora.toLocalDate() }
                previsao.current?.let { CartaoAgora(it, hoje) }
                CartaoAvisos(avisos)
                previsao.hourly?.let { CartaoPulverizacao(horasDePulverizacao(it, agora), agora) }
                if (listaDias.isNotEmpty()) {
                    CartaoSeteDias(listaDias.filter { !it.data.isBefore(agora.toLocalDate()) }, agora.toLocalDate())
                    CartaoChuva(listaDias, agora.toLocalDate())
                }
            }
        }

        val formatoQuando = stringResource(R.string.formato_data_hora)
        val quando = obtidaEm?.let {
            java.time.Instant.ofEpochMilli(it).atZone(ZoneId.systemDefault())
                .format(DateTimeFormatter.ofPattern(formatoQuando, localDe(LocalContext.current)))
        }
        Text(quando?.let { stringResource(R.string.tempo_fonte_obtida, it) } ?: stringResource(R.string.tempo_fonte),
             fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
        Text(stringResource(R.string.tempo_nao_entra),
             fontSize = 12.sp, color = secundaria, lineHeight = 16.sp, fontStyle = FontStyle.Italic)
    }
}

@Composable
private fun Cartao(titulo: String, icone: ImageVector, conteudo: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 8.dp)) {
                Icon(icone, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text(titulo, fontWeight = FontWeight.Bold, fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface)
            }
            conteudo()
        }
    }
}

@Composable
private fun Medida(rotulo: String, valor: String, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(rotulo, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(valor, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
    }
}

@Composable
private fun CartaoAgora(a: TempoAtual, hoje: DiaTempo?) {
    Cartao(stringResource(R.string.tempo_agora), Icons.Filled.Thermostat) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(iconeTempo(a.weather_code, a.is_day != 0), contentDescription = null,
                 tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(44.dp))
            Spacer(Modifier.width(12.dp))
            Column {
                Text(graus(a.temperature_2m), fontSize = 32.sp, fontWeight = FontWeight.Bold,
                     color = MaterialTheme.colorScheme.onSurface)
                Text(stringResource(descricaoTempo(a.weather_code)) +
                     (a.apparent_temperature?.let { " · " + stringResource(R.string.tempo_sensacao, graus(it)) } ?: ""),
                     fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth()) {
            val direcao = direcaoVento(a.wind_direction_10m)?.let { stringResource(it) } ?: ""
            Medida(stringResource(R.string.tempo_umidade), a.relative_humidity_2m?.let { "${it.roundToInt()}%" } ?: "–",
                   Modifier.weight(1f))
            Medida(stringResource(R.string.tempo_vento), a.wind_speed_10m?.let { "${it.roundToInt()} km/h $direcao".trim() } ?: "–",
                   Modifier.weight(1f))
            Medida(stringResource(R.string.tempo_rajadas), a.wind_gusts_10m?.let { "${it.roundToInt()} km/h" } ?: "–",
                   Modifier.weight(1f))
        }
        hoje?.let { d ->
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth()) {
                Medida(stringResource(R.string.tempo_hoje), stringResource(R.string.tempo_faixa, graus(d.minima), graus(d.maxima)),
                       Modifier.weight(1f))
                val uv = d.uv?.let { u -> "${u.roundToInt()} (${categoriaUv(u)?.let { stringResource(it) } ?: ""})" } ?: "–"
                Medida(stringResource(R.string.tempo_uv_maximo), uv, Modifier.weight(1f))
                Medida(stringResource(R.string.tempo_sol), if (d.nascer != null && d.por != null) "${d.nascer} – ${d.por}" else "–",
                       Modifier.weight(1f))
            }
        }
        // Só o que muda a leitura: a altura do vento e, quando é o caso, o UV.
        Text(stringResource(R.string.tempo_vento_10m) +
             (if ((hoje?.uv ?: 0.0) >= 8.0) " " + stringResource(R.string.tempo_uv_alerta) else ""),
             fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp,
             modifier = Modifier.padding(top = 8.dp))
    }
}

/**
 * "2026-10-26 00:00", como o INMET publica, para "26/10 às 00:00" (em inglês,
 * "Oct 26 at 00:00"), no formato que Formatos guardou do idioma.
 */
internal fun dataDoAviso(t: String?): String {
    val m = Regex("""(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})""").find(t ?: "") ?: return t ?: "?"
    val (ano, mes, dia, hm) = m.destructured
    return runCatching {
        LocalDateTime.parse("$ano-$mes-${dia}T$hm").format(DateTimeFormatter.ofPattern(Formatos.dataHora, Formatos.locale))
    }.getOrDefault(t ?: "?")
}

private fun corDoAviso(cor: String?, padrao: Color): Color =
    runCatching { Color(android.graphics.Color.parseColor(cor)) }.getOrDefault(padrao)

@Composable
internal fun CartaoAvisos(avisos: AvisosResponse?) {
    val lista = avisos?.avisos.orEmpty()
    if (lista.isEmpty()) {
        val texto = when {
            avisos == null -> stringResource(R.string.tempo_avisos_consultando)
            !avisos.disponivel -> stringResource(R.string.tempo_avisos_falhou)
            else -> stringResource(R.string.tempo_avisos_nenhum)
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(if (avisos?.disponivel == true) Icons.Filled.CheckCircle else Icons.Filled.Warning, contentDescription = null,
                 tint = MaterialTheme.colorScheme.onSurfaceVariant,
                 modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text(texto, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }
    val padrao = corDoNivel(NivelJanela.ATENCAO)
    val context = LocalContext.current
    Cartao(stringResource(R.string.tempo_avisos_titulo), Icons.Filled.Warning) {
        lista.forEachIndexed { i, a ->
            var aberto by remember(a.id) { mutableStateOf(false) }
            val cor = corDoAviso(a.cor, padrao)
            Row(Modifier.fillMaxWidth().padding(top = if (i > 0) 10.dp else 0.dp).height(IntrinsicSize.Min)) {
                Box(Modifier.width(5.dp).fillMaxHeight().background(cor, RoundedCornerShape(3.dp)))
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    val evento = a.evento?.let { nomeDoInmet(context, it) } ?: stringResource(R.string.tempo_aviso)
                        .replaceFirstChar { it.uppercase() }
                    Text("$evento · ${a.severidade?.let { nomeDoInmet(context, it) } ?: ""}".trimEnd(' ', '·'),
                         fontWeight = FontWeight.SemiBold,
                         fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
                    Text(stringResource(R.string.tempo_aviso_periodo, dataDoAviso(a.inicio), dataDoAviso(a.fim)), fontSize = 12.sp,
                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                    a.riscos?.firstOrNull()?.let {
                        Text(it, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface, lineHeight = 16.sp)
                    }
                    if (!a.instrucoes.isNullOrEmpty()) {
                        TextButton(onClick = { aberto = !aberto }, contentPadding = PaddingValues(0.dp)) {
                            Text(stringResource(if (aberto) R.string.tempo_ocultar_orientacoes else R.string.tempo_ver_orientacoes),
                                 fontSize = 12.sp)
                        }
                        if (aberto) a.instrucoes.forEach {
                            Text("• $it", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CartaoPulverizacao(horas: List<HoraPulverizacao>, agora: LocalDateTime) {
    if (horas.isEmpty()) return
    var tocada by remember(horas) { mutableStateOf(0) }
    val sel = horas[tocada.coerceIn(0, horas.size - 1)]
    val janela = proximaJanela(horas)
    val corTexto = MaterialTheme.colorScheme.onSurfaceVariant
    val cores = NivelJanela.entries.associateWith { corDoNivel(it) }
    val context = LocalContext.current
    Cartao(stringResource(R.string.tempo_janela_titulo), Icons.Filled.Agriculture) {
        val primeira = horas.first()
        Text(stringResource(R.string.tempo_agora_nivel, nomeDoNivel(context, primeira.nivel)), fontSize = 18.sp,
             fontWeight = FontWeight.Bold, color = cores.getValue(primeira.nivel))
        if (primeira.motivos.isNotEmpty()) {
            Text(primeira.motivos.joinToString("; ") { textoDoMotivo(context, it) }, fontSize = 13.sp,
                 color = MaterialTheme.colorScheme.onSurface, lineHeight = 17.sp)
        }
        Text(janela?.let { stringResource(R.string.tempo_proxima_janela, quandoJanela(context, it, agora)) }
                 ?: stringResource(R.string.tempo_sem_janela, horas.size),
             fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface,
             modifier = Modifier.padding(top = 6.dp))

        Canvas(
            modifier = Modifier.fillMaxWidth().height(48.dp).padding(top = 10.dp)
                .semantics {
                    contentDescription = context.getString(R.string.tempo_janela_descricao, horas.size,
                        horas.count { it.nivel == NivelJanela.BOA }, horas.count { it.nivel == NivelJanela.ATENCAO },
                        horas.count { it.nivel == NivelJanela.EVITAR })
                }
                .pointerInput(horas) {
                    detectTapGestures { pos ->
                        tocada = (pos.x / (size.width.toFloat() / horas.size)).toInt().coerceIn(0, horas.size - 1)
                    }
                }
        ) {
            val passo = size.width / horas.size
            val altura = 20.dp.toPx()
            val paint = Paint().apply { color = corTexto.toArgb(); textSize = 11.sp.toPx(); isAntiAlias = true }
            horas.forEachIndexed { i, h ->
                drawRect(color = cores.getValue(h.nivel).copy(alpha = if (i == tocada) 1f else 0.75f),
                         topLeft = Offset(i * passo + 1, 0f), size = Size(passo - 2, altura))
                if (i % 3 == 0) {
                    val r = horaCurta(context, h.hora)
                    drawContext.canvas.nativeCanvas.drawText(r, (i * passo).coerceAtMost(size.width - paint.measureText(r)),
                                                             altura + 14.dp.toPx(), paint)
                }
            }
            drawRect(color = corTexto, topLeft = Offset(tocada * passo, 0f), size = Size(passo, altura),
                     style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2.dp.toPx()))
        }
        Text(stringResource(R.string.tempo_hora_selecionada, nomeDoDia(context, sel.hora.toLocalDate(), agora.toLocalDate()),
                            horaCurta(context, sel.hora), nomeDoNivel(context, sel.nivel), graus(sel.temperatura),
                            sel.umidade?.let { "${it.roundToInt()}%" } ?: "–", sel.vento2m?.let { "${it.roundToInt()} km/h" } ?: "–") +
             (sel.chanceChuva?.let { ", " + stringResource(R.string.tempo_chuva_pct, it.roundToInt()) } ?: ""),
             fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface, lineHeight = 16.sp)
        if (sel !== primeira && sel.motivos.isNotEmpty()) {
            Text(sel.motivos.joinToString("; ") { textoDoMotivo(context, it) }, fontSize = 12.sp, color = corTexto,
                 lineHeight = 16.sp)
        }
        Row(modifier = Modifier.padding(top = 4.dp)) {
            NivelJanela.entries.forEach { n ->
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(end = 14.dp)) {
                    Box(Modifier.size(12.dp).background(cores.getValue(n), RoundedCornerShape(2.dp)))
                    Spacer(Modifier.width(4.dp))
                    Text(nomeDoNivel(context, n).replaceFirstChar { it.uppercase() }, fontSize = 12.sp, color = corTexto)
                }
            }
        }
        // A fonte completa (Adegas e Gazziero, 2020; FAO-56) está no Sobre.
        // Quanto a janela erra, medido contra 12 estações do INMET de nov/2025 a
        // abr/2026 (pesquisa/10_trabalhos_futuros/04_valida_tempo_inmet.py):
        // das horas previstas boas, 26% eram boas, 63% de atenção e 10,6% a evitar.
        Text(stringResource(R.string.tempo_embrapa, TEMPERATURA_MAXIMA.toInt(), UMIDADE_MINIMA.toInt(), VENTO_MINIMO.toInt(),
                            VENTO_IDEAL_MAXIMO.toInt(), HORAS_SEM_CHUVA),
             fontSize = 12.sp, color = corTexto, lineHeight = 16.sp, modifier = Modifier.padding(top = 8.dp))
    }
}

@Composable
private fun CartaoSeteDias(lista: List<DiaTempo>, hoje: LocalDate) {
    val context = LocalContext.current
    Cartao(stringResource(R.string.tempo_proximos_dias), Icons.Filled.DateRange) {
        lista.forEachIndexed { i, d ->
            if (i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                Text(nomeDoDia(context, d.data, hoje), fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                     color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.width(78.dp))
                val descricao = stringResource(descricaoTempo(d.codigo))
                Icon(iconeTempo(d.codigo), contentDescription = descricao,
                     tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.tempo_faixa, graus(d.minima), graus(d.maxima)), fontSize = 13.sp,
                         color = MaterialTheme.colorScheme.onSurface)
                    Text(descricao + (d.ventoMaximo?.let { " · " + stringResource(R.string.tempo_vento_ate, it.roundToInt()) } ?: ""),
                         fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(d.chuva?.let { mm(it) } ?: "–", fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                         color = MaterialTheme.colorScheme.onSurface)
                    Text(d.chance?.let { stringResource(R.string.tempo_chance, it.roundToInt()) } ?: "", fontSize = 11.sp,
                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun CartaoChuva(lista: List<DiaTempo>, hoje: LocalDate) {
    val b = balancoChuva(lista, hoje)
    val escuro = isSystemInDarkTheme()
    val corChuva = if (escuro) Color(0xFF58A6FF) else Color(0xFF1D4ED8)
    val corTexto = MaterialTheme.colorScheme.onSurfaceVariant
    val corGrade = MaterialTheme.colorScheme.outlineVariant
    val context = LocalContext.current
    val formatoRotulo = DateTimeFormatter.ofPattern(stringResource(R.string.tempo_formato_rotulo_dia), localDe(context))
    val rotuloHoje = stringResource(R.string.tempo_rotulo_hoje)
    Cartao(stringResource(R.string.tempo_chuva_titulo), Icons.Filled.WaterDrop) {
        if (b.diasPassados > 0) {
            val sinal = if (b.saldo >= 0) "+" else "−"
            Text(stringResource(R.string.tempo_chuva_passada, b.diasPassados, mm(b.chuvaPassada), mm(b.et0Passada),
                                sinal + mm(kotlin.math.abs(b.saldo))),
                 fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface, lineHeight = 17.sp)
        }
        Text(stringResource(R.string.tempo_chuva_prevista, b.diasPrevistos, mm(b.chuvaPrevista)), fontSize = 13.sp,
             color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.padding(top = 2.dp))
        val maximo = (lista.maxOfOrNull { it.chuva ?: 0.0 } ?: 0.0).coerceAtLeast(5.0)
        Canvas(
            modifier = Modifier.fillMaxWidth().height(110.dp).padding(top = 10.dp)
                .semantics {
                    contentDescription = context.getString(R.string.tempo_chuva_descricao, b.diasPassados, b.diasPrevistos,
                                                           mm(lista.maxOfOrNull { it.chuva ?: 0.0 } ?: 0.0))
                }
        ) {
            val padY = 18.dp.toPx()
            val h = size.height - padY
            val passo = size.width / lista.size.coerceAtLeast(1)
            val paint = Paint().apply { color = corTexto.toArgb(); textSize = 10.sp.toPx(); isAntiAlias = true }
            drawLine(color = corGrade, start = Offset(0f, h), end = Offset(size.width, h), strokeWidth = 1.dp.toPx())
            lista.forEachIndexed { i, d ->
                val v = d.chuva ?: 0.0
                val alt = (v / maximo * (h - 12.dp.toPx())).toFloat()
                val passado = d.data.isBefore(hoje)
                drawRect(color = corChuva.copy(alpha = if (passado) 0.45f else 1f),
                         topLeft = Offset(i * passo + passo * 0.2f, h - alt), size = Size(passo * 0.6f, alt))
                if (v >= 0.5) {
                    val r = if (v < 10) String.format(LOCAL_NUMEROS, "%.1f", v) else "${v.roundToInt()}"
                    drawContext.canvas.nativeCanvas.drawText(r, i * passo + (passo - paint.measureText(r)) / 2,
                                                             h - alt - 3.dp.toPx(), paint)
                }
                if (d.data == hoje || i == 0 || i == lista.size - 1) {
                    val r = if (d.data == hoje) rotuloHoje else d.data.format(formatoRotulo)
                    drawContext.canvas.nativeCanvas.drawText(
                        r, (i * passo + (passo - paint.measureText(r)) / 2).coerceIn(0f, size.width - paint.measureText(r)),
                        h + 14.dp.toPx(), paint)
                }
                if (d.data == hoje) {
                    drawLine(color = corTexto, start = Offset(i * passo, 0f), end = Offset(i * passo, h),
                             strokeWidth = 1.dp.toPx(),
                             pathEffect = androidx.compose.ui.graphics.PathEffect.dashPathEffect(floatArrayOf(6f, 6f), 0f))
                }
            }
        }
        Text(stringResource(R.string.tempo_chuva_legenda),
             fontSize = 12.sp, color = corTexto, lineHeight = 16.sp, modifier = Modifier.padding(top = 6.dp))
    }
}
