package com.agrointeligencia.app

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

data class MunicipioResponse(val municipios: List<String>)

data class PrevisaoHistorico(
    val ano: Int,
    val rendimento_predito: Double,
    val rendimento_real: Double,
    val margem_erro: Double
)

data class PrevisaoResponse(
    val municipio: String,
    val historico: List<PrevisaoHistorico>,
    val elNinos: List<Int>? = null,
    val laNinas: List<Int>? = null
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
    // Componentes do custo. A CONAB publica só os totais por saca, sem abrir
    // por item: não se sabe que parcela do custo variável acompanha a área
    // (semente, adubo, pulverização) e que parcela acompanha a produção
    // (colheita, secagem, frete). Acima da produtividade de referência os dois
    // rateios possíveis chegam a inverter o sinal do resultado, e daí a tela
    // precisa dizer isso em vez de pintar de verde.
    val custo_variavel_saca: Double? = null,
    val custo_fixo_ha: Double? = null,
    val produtividade_referencia_sc: Double? = null,
    // Cotação diária da praça mais próxima do usuário. O corredor do Pará vem
    // antes dos portos do Sul na busca; nulo quando a fonte não responde, e
    // nunca um valor de reserva.
    val preco_fisico: CotacaoFisica? = null,
    val ano_referencia: Int
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
    // Cotação diária da praça mais próxima do usuário. O corredor do Pará vem
    // antes dos portos do Sul na busca; nulo quando a fonte não responde, e
    // nunca um valor de reserva.
    val preco_fisico: CotacaoFisica? = null,
    val ano_referencia: Int
)

data class SimulacaoRequest(
    val municipio: String,
    val precip_factor: Double,
    val temp_offset: Double
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

interface AgroApiService {
    @retrofit2.http.POST("api/simulacao")
    suspend fun simularCenario(@retrofit2.http.Body request: SimulacaoRequest): SimulacaoResponse

    @GET("api/municipios")
    suspend fun getMunicipios(): MunicipioResponse

    @GET("api/previsao/{municipio}")
    suspend fun getPrevisao(@Path("municipio") municipio: String): PrevisaoResponse

    @GET("api/financas/{municipio}")
    suspend fun getFinancas(@Path("municipio") municipio: String): FinancaResponse

    @GET("api/ping")
    suspend fun ping(): PingResponse
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
