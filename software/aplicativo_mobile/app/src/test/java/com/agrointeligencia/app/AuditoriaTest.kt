package com.agrointeligencia.app

import com.google.gson.Gson
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.time.LocalDate
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.roundToInt

/**
 * Auditoria das telas com o código do próprio aplicativo, nos 38 municípios.
 *
 * auditoria_numeros.py (auditoria-app.yml) grava em build/auditoria/api as
 * respostas da API em produção. Aqui cada município passa pelas mesmas funções
 * que as telas chamam (projecaoDaSafra, pracaParaUsar, sacasDoCampo,
 * resultadoPorHectare, pontoDeEquilibrio), e o teste confere que as telas
 * dizem a mesma coisa umas às outras e que os números são plausíveis. Grava
 * build/auditoria/telas.csv com o que cada tela mostraria.
 *
 * Sem as respostas gravadas (o CI comum), o teste é pulado.
 */
class AuditoriaTest {

    private val pasta = File("build/auditoria/api")
    private val gson = Gson()
    private inline fun <reified T> le(nome: String): T? =
        File(pasta, "$nome.json").takeIf { it.exists() }?.let { gson.fromJson(it.readText(), T::class.java) }

    @Test
    fun telasConferemNosMunicipios() {
        assumeTrue("sem respostas gravadas da API", pasta.isDirectory)
        val hoje = LocalDate.now()
        val mercado: MercadoResponse? = le("mercado")
        val pracas = mercado?.pracas_para.orEmpty()
        val municipios = pasta.listFiles().orEmpty().map { it.name }
            .filter { it.startsWith("previsao_") }.map { it.removePrefix("previsao_").removeSuffix(".json") }.sorted()
        val falhas = mutableListOf<String>()
        val linhas = mutableListOf(
            "municipio;safra;kg_ha;sc_ha_resumo;sc_ha_campo;erro_tipico_kg_ha;ultimo_ibge;kg_ha_ibge;praca;" +
                "data_praca;preco;receita;custo;lucro;retorno_pct;equilibrio_sc;lucro_cartao_historico;anos_sem_dado"
        )

        for (m in municipios) {
            val prev = le<PrevisaoResponse>("previsao_$m")?.valida()
            val fin: FinancaResponse? = le("financas_$m")
            if (prev == null || fin == null) { falhas += "$m: resposta da API ausente ou inválida"; continue }
            val hist = prev.historico

            // Resumo: a safra em curso e a última divulgada.
            val proj = projecaoDaSafra(hist, hoje)
            val obs = ultimoObservado(hist)
            if (proj == null) { falhas += "$m: sem projeção"; continue }
            if (proj.ano != anoDaSafraEmCurso(hoje)) falhas += "$m: Resumo mostra ${proj.ano}, safra em curso é ${anoDaSafraEmCurso(hoje)}"
            if (obs == null) falhas += "$m: sem safra divulgada pelo IBGE"
            if (proj.rendimento_predito !in 1000.0..6000.0) falhas += "$m: projeção implausível (${proj.rendimento_predito} kg/ha)"
            if (proj.margem_erro <= 0) falhas += "$m: projeção sem erro típico"

            // Preço padrão: a praça em dia mais perto; sem ela, a CONAB.
            val praca = pracaParaUsar(m, pracas, hoje)
            if (praca != null && !cotacaoEmDia(praca, hoje)) falhas += "$m: praça ${praca.praca} parada (${praca.data})"
            val preco = praca?.valor ?: fin.soja_preco_saca
            if (preco !in 50.0..300.0) falhas += "$m: preço implausível ($preco)"

            // Viabilidade: o campo de produtividade com uma casa, e a conta.
            val scCampo = sacasDoCampo(proj.rendimento_predito / 60)
            val scResumo = (proj.rendimento_predito / 60).roundToInt()
            if (abs(scCampo - scResumo) > 0.5 + 1e-9) falhas += "$m: Resumo diz ~$scResumo sc e a Viabilidade $scCampo"
            val viab = resultadoPorHectare(scCampo, preco, null, fin)
            val receita = scCampo * preco
            val custo = receita - viab.valor
            if (fin.custo_area_ha != null && fin.custo_transporte_saca != null && fin.taxa_cessr != null) {
                val esperado = fin.custo_area_ha!! + (fin.custo_transporte_saca!! + fin.taxa_cessr!! * preco) * scCampo
                if (abs(custo - esperado) > 0.01) falhas += "$m: custo da linha ${"%.2f".format(custo)} ≠ componentes ${"%.2f".format(esperado)}"
            } else falhas += "$m: API sem os componentes do custo"
            val equilibrio = pontoDeEquilibrio(preco, null, fin)
            if (equilibrio == null) falhas += "$m: sem ponto de equilíbrio"
            else if ((viab.valor >= 0) != (equilibrio <= scCampo + 1e-9))
                falhas += "$m: lucro ${viab.valor} e equilíbrio $equilibrio sc contra $scCampo sc não combinam"

            // Histórico: o cartão da safra em curso diz o mesmo que a Viabilidade.
            val cartao = resultadoPorHectare(sacasDoCampo(proj.rendimento_predito / 60), preco, null, fin)
            if (cartao.valor != viab.valor) falhas += "$m: cartão do Histórico ${cartao.valor} ≠ Viabilidade ${viab.valor}"

            // Safras sem dado do IBGE entre a primeira e a última divulgadas.
            val anosIbge = hist.filter { it.rendimento_real > 0 }.map { it.ano }.toSet()
            val lacunas = if (anosIbge.isEmpty()) emptyList() else (anosIbge.min()..anosIbge.max()).filter { it !in anosIbge }

            linhas += listOf(
                m, proj.ano, "%.0f".format(proj.rendimento_predito), scResumo, scCampo, "%.0f".format(proj.margem_erro),
                obs?.ano ?: "", obs?.rendimento_real?.let { "%.0f".format(it) } ?: "", praca?.praca ?: "CONAB",
                praca?.data ?: "", "%.2f".format(preco), "%.2f".format(receita), "%.2f".format(custo), "%.2f".format(viab.valor),
                "%.1f".format(viab.valor / custo * 100), equilibrio?.let { ceil(it).toInt() } ?: "",
                "%.2f".format(cartao.valor), lacunas.joinToString(" ")
            ).joinToString(";")
        }

        File("build/auditoria").mkdirs()
        File("build/auditoria/telas.csv").writeText(linhas.joinToString("\n") + "\n")
        File("build/auditoria/telas_falhas.txt").writeText(
            if (falhas.isEmpty()) "Nenhuma divergência entre telas em ${municipios.size} municípios.\n"
            else falhas.joinToString("\n") + "\n"
        )
        assertTrue("${municipios.size} municípios lidos", municipios.size >= 38)
        assertTrue(falhas.joinToString("\n"), falhas.isEmpty())
    }
}
