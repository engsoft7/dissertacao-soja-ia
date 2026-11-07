package com.agrointeligencia.app

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

data class MunicipioResponse(
    val municipios: List<String>,
    // Só com ?uf= (Estados.kt): a sigla confirma que o servidor atendeu o estado,
    // e as sedes servem ao GPS, ao Tempo e à praça mais perto.
    val uf: String? = null,
    val sedes: List<SedeMunicipio>? = null,
)

/** A sede de um município de outro estado, como a API manda em /api/municipios?com_sedes=true. */
data class SedeMunicipio(val nome: String, val cod_ibge7: Long, val latitude: Double, val longitude: Double)

data class PrevisaoHistorico(
    val ano: Int,
    val rendimento_predito: Double,
    val rendimento_real: Double,
    val margem_erro: Double
)

/**
 * Métricas da validação do modelo, enviadas pela API a partir de
 * pesquisa/dados/metricas_validacao.json. Acompanham a base a cada safra nova,
 * sem recompilar o aplicativo.
 */
data class ValidacaoModelo(
    val r2: Double,
    val r2_referencia: Double,
    val rmse_kg_ha: Double,
    val rrmse_pct: Double,
    val registros: Int,
    val municipios: Int
)

data class PrevisaoResponse(
    val municipio: String,
    val historico: List<PrevisaoHistorico>,
    val elNinos: List<Int>? = null,
    val laNinas: List<Int>? = null,
    // Nulo quando a API é mais antiga que o aplicativo, ou na previsão guardada
    // em cache por uma versão anterior: a tela diz que as métricas estão
    // indisponíveis em vez de exibir números de outra base.
    val validacao: ValidacaoModelo? = null,
    // Com ?uf=, a sigla do estado da resposta (Estados.kt).
    val uf: String? = null
)


/**
 * Cotação física do dia numa praça. Porto e terminal não são preço de
 * porteira: entre eles e a fazenda ainda há frete e base. A praça e o tipo
 * viajam junto com o valor para a tela poder dizer de onde o número veio.
 */
data class CotacaoFisica(
    val praca: String,
    val uf: String,
    val tipo: String,
    val valor: Double
)

data class FinancaResponse(
    val soja_preco_saca: Double,
    val custo_ha: Double,
    // Nulo quando a Receita Federal não publica VTN para o município.
    val vtn_ha: Double? = null,
    // Rótulo da praça e da data do levantamento da CONAB, e a frase que situa
    // o preço padrão na série histórica. Vêm do servidor, e não escritos aqui,
    // para o aplicativo acompanhar um levantamento novo sem recompilar: são a
    // única parte da tela que envelhece quando a CONAB publica. Nulos quando a
    // API é mais antiga que o aplicativo — a tela omite a legenda em vez de
    // exibir uma data errada.
    val fonte_preco: String? = null,
    val nota_preco: String? = null,
    val levantamento: String? = null,
    // Idade do levantamento, calculada no servidor a cada requisição. Sem isto,
    // este aplicativo aberto daqui a dois anos exibiria o preço de 2026 como se
    // fosse o de hoje: o levantamento é um arquivo estático e a atualização
    // depende de alguém manter o repositório. O aviso vem pronto do servidor,
    // para o alerta acompanhar o tempo sem depender de um APK novo.
    val defasagem_meses: Int? = null,
    val aviso_preco: String? = null,
    // A mesma idade, dita do lado do custo: quando o produtor informa o próprio
    // preço, o aviso do preço perde sentido, mas o custo continua saindo do
    // levantamento velho e entrando na margem do mesmo jeito.
    val aviso_custo: String? = null,
    // Físico em Paranaguá, relido de hora em hora. É a única cotação DIÁRIA do
    // produto: o padrão vem de levantamento bimestral e sempre chega com
    // semanas de atraso. Não substitui o preço de porteira — é porto, no
    // Paraná, acima do que se recebe no Pará.
    val soja_preco_paranagua_saca: Double? = null,
    // Cotação de bolsa, só para comparação. Nunca entra em receita nem em
    // margem: é preço de Chicago, acima do que se recebe na porteira no Pará.
    // Antes o campo nem existia aqui, e o painel mostrava a comparação
    // enquanto o aplicativo não mostrava nada.
    val soja_preco_cbot_saca: Double? = null,
    // Componentes do custo por saca, para o caso de o levantamento não trazer
    // o custo aberto por item: aí o resultado vai pelos dois rateios extremos.
    val custo_variavel_saca: Double? = null,
    val custo_fixo_ha: Double? = null,
    val produtividade_referencia_sc: Double? = null,
    // Custo aberto por item (planilha da série histórica da CONAB): a parte por
    // hectare, o transporte por saca e a CESSR como fração da receita. Nulos com
    // a API antiga ou levantamento sem itens: o app volta aos dois rateios.
    val custo_area_ha: Double? = null,
    val custo_transporte_saca: Double? = null,
    val taxa_cessr: Double? = null,
    // Cotação diária da praça mais próxima do usuário. O corredor do Pará vem
    // antes dos portos do Sul na busca; nulo quando a fonte não responde, e
    // nunca um valor de reserva.
    val preco_fisico: CotacaoFisica? = null,
    val ano_referencia: Int,
    // Com ?uf=, a sigla do estado da resposta (Estados.kt).
    val uf: String? = null
)

data class KpiEconomiaResponse(
    val soja_preco_saca: Double,
    val custo_ha: Double,
    val fonte_preco: String? = null,
    val nota_preco: String? = null,
    val levantamento: String? = null,
    val defasagem_meses: Int? = null,
    val aviso_preco: String? = null,
    val aviso_custo: String? = null,
    val soja_preco_paranagua_saca: Double? = null,
    val soja_preco_cbot_saca: Double? = null,
    val custo_variavel_saca: Double? = null,
    val custo_fixo_ha: Double? = null,
    val produtividade_referencia_sc: Double? = null,
    // Custo aberto por item (planilha da série histórica da CONAB): a parte por
    // hectare, o transporte por saca e a CESSR como fração da receita. Nulos com
    // a API antiga ou levantamento sem itens: o app volta aos dois rateios.
    val custo_area_ha: Double? = null,
    val custo_transporte_saca: Double? = null,
    val taxa_cessr: Double? = null,
    // Cotação diária da praça mais próxima do usuário. O corredor do Pará vem
    // antes dos portos do Sul na busca; nulo quando a fonte não responde, e
    // nunca um valor de reserva.
    val preco_fisico: CotacaoFisica? = null,
    val ano_referencia: Int
)

data class SimulacaoRequest(
    val municipio: String,
    val precip_factor: Double,
    val temp_offset: Double,
    // A safra do cenário: a mesma do Resumo (a API aceita as três projetadas).
    val ano: Int? = null,
    // Sem estado, o Pará (Estados.kt).
    val uf: String? = null
)

data class Sensibilidade(
    val variavel: String,
    val r: Double,
    val p: Double,
    val n: Int,
    val amplitude_kg_ha: Double
)

data class SimulacaoResponse(
    val municipio: String,
    val baseline_kg_ha: Double,
    val estimativa_kg_ha: Double,
    val delta_kg_ha: Double,
    // Opcionais para a versão antiga da API continuar sendo lida.
    val fora_da_faixa: List<String>? = null,
    val margem_kg_ha: Double? = null,
    val sensibilidade: Sensibilidade? = null
)

data class PingResponse(val status: String, val model_loaded: Boolean)

/** Uma vela da cotação de Chicago, já em R$/saca; t em segundos (Unix). */
/**
 * Uma vela de Chicago em R$/saca. "pa" é o preço estimado no Pará no mesmo
 * instante: o fechamento somado à base do Pará no mês (ver EstimativaPara).
 * Nulo quando a API não tem a base.
 */
data class Vela(val t: Long, val o: Double, val h: Double, val l: Double, val c: Double, val pa: Double? = null)

/** Médias de um mês, em R$/saca: Pará (Agrolink), Chicago, e a base entre elas. */
data class MesPara(val mes: String, val para: Double, val nacional: Double? = null, val chicago: Double, val base: Double)

/**
 * Preço estimado da soja no Pará. Ninguém publica o físico paraense ao longo
 * do dia; a estimativa soma à cotação de Chicago a base do Pará, isto é, a
 * diferença entre a média mensal do Pará publicada pela Agrolink e a média de
 * Chicago em reais no mesmo mês. É estimativa, não cotação de praça.
 */
data class EstimativaPara(
    val fonte: String,
    val url: String? = null,
    val mes_base: String,
    val base_brl_saca: Double,
    val meses: List<MesPara>? = null,
    val estimado_brl_saca: Double? = null
)

/**
 * Soja na CBOT convertida para R$/saca pelo dólar de cada instante. Chega com
 * atraso de 10 a 15 minutos: é a cotação gratuita, não a de tempo real, que
 * exige licença paga da bolsa. A tela declara o atraso.
 */
data class CotacaoBolsa(
    val fonte: String,
    val periodo: String,
    val intervalo: String,
    val atraso_min: Int,
    val atualizado_em: Long,
    val ultimo_brl_saca: Double,
    val ultimo_usd_bushel: Double? = null,
    val cambio: Double? = null,
    val variacao_periodo_pct: Double,
    val maxima_periodo: Double,
    val minima_periodo: Double,
    val velas: List<Vela>
)

/**
 * Cotação diária de uma praça do Pará na Agrolink. "data" é a da última
 * atualização (AAAA-MM-DD): uma praça parada continua listada com o valor velho.
 */
data class PracaPara(val praca: String, val uf: String? = "PA", val valor: Double, val data: String)

data class MercadoResponse(
    // Nulo quando a fonte não respondeu: a tela diz que a cotação está
    // indisponível em vez de exibir um número inventado.
    val cotacao: CotacaoBolsa? = null,
    val fisico: CotacaoFisica? = null,
    val conab_saca: Double? = null,
    val conab_fonte: String? = null,
    // Nulo quando a API é mais antiga ou a fonte da base não respondeu: a tela
    // omite a estimativa do Pará em vez de inventar uma base.
    val para: EstimativaPara? = null,
    // Nulo ou vazio com a API antiga ou a fonte fora do ar: a tela fica com a estimativa.
    val pracas_para: List<PracaPara>? = null,
    val pracas_fonte: String? = null,
    // Com ?uf= de outro estado: a sigla e as praças dele (pracasDoEstado, em Estados.kt).
    val uf: String? = null,
    val pracas: List<PracaPara>? = null
)

/**
 * Aviso meteorológico do INMET para o lugar (ver avisos_inmet.py na API).
 * "nivel" vai de 1 (perigo potencial) a 3 (grande perigo); "cor" é a do INMET.
 */
data class AvisoMeteorologico(
    val id: String,
    val evento: String? = null,
    val severidade: String? = null,
    val nivel: Int? = null,
    val cor: String? = null,
    val inicio: String? = null,
    val fim: String? = null,
    val riscos: List<String>? = null,
    val instrucoes: List<String>? = null
)

/** "disponivel" falso quando o INMET não respondeu: a tela não diz "nenhum aviso" sem saber. */
data class AvisosResponse(
    val fonte: String? = null,
    val disponivel: Boolean = false,
    val lido_em: Long? = null,
    val avisos: List<AvisoMeteorologico>? = null
)

interface AgroApiService {
    @retrofit2.http.POST("api/simulacao")
    suspend fun simularCenario(@retrofit2.http.Body request: SimulacaoRequest): SimulacaoResponse

    // ?uf= nulo fica fora da consulta: o Pará pede exatamente o que as versões antigas pediam.
    @GET("api/municipios")
    suspend fun getMunicipios(
        @retrofit2.http.Query("uf") uf: String? = null,
        @retrofit2.http.Query("com_sedes") comSedes: Boolean? = null
    ): MunicipioResponse

    @GET("api/previsao/{municipio}")
    suspend fun getPrevisao(
        @Path("municipio") municipio: String,
        @retrofit2.http.Query("uf") uf: String? = null
    ): PrevisaoResponse

    @GET("api/financas/{municipio}")
    suspend fun getFinancas(
        @Path("municipio") municipio: String,
        @retrofit2.http.Query("uf") uf: String? = null
    ): FinancaResponse

    @GET("api/ping")
    suspend fun ping(): PingResponse

    @GET("api/mercado")
    suspend fun getMercado(
        @retrofit2.http.Query("periodo") periodo: String,
        @retrofit2.http.Query("uf") uf: String? = null
    ): MercadoResponse

    // Parâmetros nulos ficam fora da consulta: o GPS da fazenda vai sem
    // geocódigo, e a API decide pelo polígono do aviso.
    // Anúncio do modelo do contador de vagens (AtualizaContador.kt).
    @GET("api/contador")
    suspend fun getContador(): ManifestoContador

    @GET("api/avisos")
    suspend fun getAvisos(
        @retrofit2.http.Query("lat") lat: Double?,
        @retrofit2.http.Query("lon") lon: Double?,
        @retrofit2.http.Query("geocode") geocode: String?
    ): AvisosResponse
}

object RetrofitClient {
    private const val BASE_URL = "https://agrointeligencia-api.onrender.com/"

    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(60, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()
    }

    private val api: AgroApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(AgroApiService::class.java)
    }

    fun getInstance(): AgroApiService = api
}
