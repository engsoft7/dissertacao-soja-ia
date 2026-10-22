package com.agrointeligencia.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import kotlin.math.sin

/**
 * Desenha as telas com dados de exemplo e grava cada uma em PNG, no tema
 * claro e no escuro, num celular de 411 x 891 dp.
 *
 * Existe porque ninguém além do autor via o aplicativo rodando: o ambiente de
 * desenvolvimento não tem emulador, e problemas de leitura (texto de 8 sp nos
 * gráficos, faixas de El Niño cobrindo o histórico) passavam por revisão de
 * código sem que ninguém os visse. O workflow capturas.yml publica os PNGs
 * na branch capturas-de-tela.
 *
 * Não compara com imagens de referência: só grava. A conferência é visual.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-xxhdpi")
class CapturasDeTelaTest {

    @get:Rule
    val compose = createComposeRule()

    private fun captura(nome: String, escuro: Boolean, conteudo: @Composable () -> Unit) {
        compose.setContent {
            MaterialTheme(colorScheme = esquemaAgro(escuro)) {
                Surface(color = MaterialTheme.colorScheme.background) {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) { conteudo() }
                }
            }
        }
        compose.onRoot().captureRoboImage("build/capturas/${nome}_${if (escuro) "escuro" else "claro"}.png")
    }

    // ── dados de exemplo, na ordem de grandeza da base real ──────────────────

    private val historico = (2001..2027).map { ano ->
        val tendencia = 2400.0 + (ano - 2001) * 35.0
        val observado = ano <= 2024
        PrevisaoHistorico(
            ano = ano,
            rendimento_predito = tendencia,
            rendimento_real = if (observado) tendencia + 260 * sin(ano * 1.7) else 0.0,
            margem_erro = 413.0
        )
    }

    private val previsao = PrevisaoResponse(
        municipio = "Paragominas",
        historico = historico,
        elNinos = listOf(2003, 2005, 2007, 2010, 2015, 2016, 2019, 2020, 2024),
        laNinas = listOf(2001, 2006, 2008, 2009, 2011, 2012, 2018, 2021, 2022, 2023),
        validacao = ValidacaoModelo(0.253, 0.253, 412.8, 13.6, 451, 38)
    )

    private val velas = (0 until 120).map { i ->
        val base = 125.0 + 3 * sin(i / 9.0) + i * 0.02
        val abre = base + 0.4 * sin(i * 1.3)
        val fecha = base + 0.4 * sin(i * 1.3 + 1)
        Vela(t = 1_792_670_400L + i * 300L, o = abre, h = maxOf(abre, fecha) + 0.3,
             l = minOf(abre, fecha) - 0.3, c = fecha)
    }

    private val mercado = MercadoResponse(
        cotacao = CotacaoBolsa(
            fonte = "Yahoo Finance", periodo = "1d", intervalo = "5m", atraso_min = 10,
            atualizado_em = velas.last().t, ultimo_brl_saca = velas.last().c,
            ultimo_usd_bushel = 10.32, cambio = 5.4321,
            variacao_periodo_pct = (velas.last().c / velas.first().o - 1) * 100,
            maxima_periodo = velas.maxOf { it.h }, minima_periodo = velas.minOf { it.l },
            velas = velas
        ),
        fisico = CotacaoFisica(praca = "Paranaguá", uf = "PR", tipo = "porto", valor = 131.5),
        conab_saca = 105.09,
        conab_fonte = "CONAB, Pedro Afonso (TO), março de 2026"
    )

    // ── capturas ──────────────────────────────────────────────────────────────

    @Test fun historico_claro() = captura("historico", false) { HistoricoProdutividadeChart(historico, previsao) }

    @Config(qualifiers = "+night")
    @Test fun historico_escuro() = captura("historico", true) { HistoricoProdutividadeChart(historico, previsao) }

    @Test fun mercado_claro() = captura("mercado", false) { MercadoConteudo(mercado, false, "1d") {} }

    @Config(qualifiers = "+night")
    @Test fun mercado_escuro() = captura("mercado", true) { MercadoConteudo(mercado, false, "1d") {} }

    @Test fun resumo_claro() = captura("resumo", false) {
        ResumoAgronomicoCard(historico.last(), historico.first { it.ano == 2024 })
    }

    @Config(qualifiers = "+night")
    @Test fun resumo_escuro() = captura("resumo", true) {
        ResumoAgronomicoCard(historico.last(), historico.first { it.ano == 2024 })
    }

    @Test fun cartoes_historico_claro() = captura("cartoes_historico", false) {
        PrevisaoCard(historico.first { it.ano == 2024 }, null)
        PrevisaoCard(historico.last(), null)
    }

    @Test fun sobre_claro() = captura("sobre", false) { MetodologiaCard(null, previsao.validacao) }

    @Config(qualifiers = "+night")
    @Test fun sobre_escuro() = captura("sobre", true) { MetodologiaCard(null, previsao.validacao) }
}
