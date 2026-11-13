package com.agrointeligencia.app

// ── O ESTADO ──────────────────────────────────────────────────────────────
//
// O Pará é o recorte da dissertação. Mato Grosso, Maranhão, Tocantins e
// Rondônia entram com a mesma conta, a base de cada estado e o custo da CONAB
// no próprio estado ou, em Rondônia, na praça mais perto
// (software/api_backend/estados.py). Sem escolha, o Pará, como até a 2.7: as
// consultas do Pará vão sem ?uf= e as chaves dele no AgroAppCache são as de
// sempre, e quem atualiza o aplicativo não perde nada do que estava guardado.

data class EstadoDoApp(
    val uf: String,
    val nome: String,
    /** "no Pará", "em Mato Grosso", "no Maranhão". */
    val no: String,
    /** "do Pará", "de Mato Grosso", "do Maranhão". */
    val de: String,
)

val ESTADOS_DO_APP = listOf(
    EstadoDoApp("PA", "Pará", "no Pará", "do Pará"),
    EstadoDoApp("MT", "Mato Grosso", "em Mato Grosso", "de Mato Grosso"),
    EstadoDoApp("MA", "Maranhão", "no Maranhão", "do Maranhão"),
    EstadoDoApp("TO", "Tocantins", "no Tocantins", "do Tocantins"),
    EstadoDoApp("RO", "Rondônia", "em Rondônia", "de Rondônia"),
)

/** Chave do estado escolhido em AgroAppCache. */
const val PREF_ESTADO = "estado_escolhido"

fun estadoDoApp(uf: String?): EstadoDoApp = ESTADOS_DO_APP.firstOrNull { it.uf == uf } ?: ESTADOS_DO_APP[0]

/** O que vai em ?uf=: nada no Pará, para a consulta ser a mesma das versões antigas. */
fun ufParaApi(uf: String): String? = uf.takeIf { it != "PA" }

/** Chave no AgroAppCache: as do Pará ficam como eram; as dos outros estados levam a sigla. */
fun chaveDoEstado(chave: String, uf: String): String = if (uf == "PA") chave else "${chave}_$uf"

/**
 * Se a resposta é do estado pedido. A API anterior a esta versão ignora ?uf= e
 * responde pelo Pará: sem a sigla certa na resposta, ela não vale para outro
 * estado, e o aplicativo diz que o estado ainda não está no servidor em vez
 * de mostrar municípios do Pará com o nome de Mato Grosso.
 */
fun respostaDoEstado(ufPedida: String, ufRespondida: String?): Boolean =
    ufPedida == "PA" || ufRespondida == ufPedida

/** Sedes dos municípios do estado: no Pará, as do aplicativo; nos outros, as que a API manda. */
fun sedesDoEstado(uf: String, sedes: List<SedeMunicipio>?): Map<String, LugarTempo> =
    if (uf == "PA") SEDES_MUNICIPAIS
    else sedes.orEmpty().associate { it.nome to LugarTempo(it.nome, it.latitude, it.longitude, it.cod_ibge7.toString()) }

/** As praças do dia do estado da resposta: no Pará, o campo de sempre. */
fun MercadoResponse.pracasDoEstado(): List<PracaPara> =
    if (uf == null || uf == "PA") pracas_para.orEmpty() else pracas.orEmpty()
