package com.agrointeligencia.app

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path

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

data class KpiEconomiaResponse(
    val soja_preco_saca: Double,
    val custo_ha: Double,
    val ano_referencia: Int
)

data class SimulacaoRequest(
    val municipio: String,
    val precip_factor: Double,
    val temp_offset: Double
)

data class SimulacaoResponse(
    val municipio: String,
    val baseline_kg_ha: Double,
    val estimativa_kg_ha: Double,
    val delta_kg_ha: Double
)

interface AgroApiService {
    @retrofit2.http.POST("api/simulacao")
    suspend fun simularCenario(@retrofit2.http.Body request: SimulacaoRequest): SimulacaoResponse

    @GET("api/municipios")
    suspend fun getMunicipios(): MunicipioResponse

    @GET("api/previsao/{municipio}")
    suspend fun getPrevisao(@Path("municipio") municipio: String): PrevisaoResponse

    @GET("api/kpis/economia")
    suspend fun getKpisEconomia(): KpiEconomiaResponse
}

object RetrofitClient {
    var currentBaseUrl = "https://agrointeligencia-api.onrender.com/"

    fun getInstance(url: String = currentBaseUrl): AgroApiService {
        val retrofit = Retrofit.Builder()
            .baseUrl(url)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        return retrofit.create(AgroApiService::class.java)
    }
}
