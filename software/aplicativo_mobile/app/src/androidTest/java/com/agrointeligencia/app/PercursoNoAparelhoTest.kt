package com.agrointeligencia.app

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.hasScrollToIndexAction
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isRoot
import androidx.compose.ui.test.junit4.accessibility.disableAccessibilityChecks
import androidx.compose.ui.test.junit4.accessibility.enableAccessibilityChecks
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onLast
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.tryPerformAccessibilityChecks
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * O percurso de um produtor pelo app, num Android de verdade (emulador do
 * teste-premium.yml) e com a API desta branch, que o workflow sobe no runner
 * (BuildConfig.API_BASE_URL): escolhe Pau D'Arco na lista,
 * confere a safra em curso e a última do IBGE, passa por Resumo, Viabilidade,
 * Tempo, Estimativa no campo, Mapa, Histórico, Mercado e Sobre, e abre de novo
 * sem internet para ver os dados guardados.
 *
 * Em cada tela grava uma captura e roda as verificações de acessibilidade do
 * Accessibility Test Framework (as mesmas do Scanner de Acessibilidade do
 * Google). Os achados de acessibilidade vão para o relatório e não reprovam o
 * teste; o percurso, sim.
 *
 * Saída em files/percurso do app (o workflow a copia com run-as) e no logcat,
 * com a etiqueta PERCURSO.
 */
@RunWith(AndroidJUnit4::class)
class PercursoNoAparelhoTest {

    @get:Rule
    val regra = createEmptyComposeRule()

    private val instrumentacao = InstrumentationRegistry.getInstrumentation()
    private val ctx: Context = instrumentacao.targetContext
    private val saida = File(ctx.filesDir, "percurso")
    private val passos = mutableListOf<String>()
    private val acessibilidade = mutableListOf<String>()
    private val inicio = System.currentTimeMillis()

    @Before
    fun limpa() {
        ctx.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE).edit().clear().commit()
        // Não apaga a pasta: o segundo teste da classe gravaria por cima do
        // primeiro. O app é desinstalado antes da rodada (teste_premium_emulador.sh).
        saida.mkdirs()
        shell("svc wifi enable")
        shell("svc data enable")
    }

    private fun shell(cmd: String) {
        instrumentacao.uiAutomation.executeShellCommand(cmd).close()
    }

    private fun existe(texto: String) =
        regra.onAllNodesWithText(texto, substring = true).fetchSemanticsNodes().isNotEmpty()

    private fun espera(texto: String, ms: Long = 150_000) = regra.waitUntil(ms) { existe(texto) }

    private fun anota(linha: String) {
        val l = "${(System.currentTimeMillis() - inicio) / 1000}s\t$linha"
        passos += l
        Log.i("PERCURSO", l)
    }

    private fun confere(oQue: String, ok: Boolean) = anota((if (ok) "ok" else "FALHA") + "\t$oQue")

    private fun aba(nome: String) =
        regra.onNode(hasText(nome) and SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Tab))
            .performClick()

    /** Captura e verificações de acessibilidade da tela como está agora. */
    private fun tela(nome: String) {
        regra.waitForIdle()
        val raiz = regra.onAllNodes(isRoot()).onLast()
        try {
            // A tela inteira, pelo UiAutomation: a janela de escolha do município
            // é um Dialog, outra janela, e a captura da raiz trazia só a tela de
            // trás (run 43460955234, 02_lista). Se falhar, a raiz do Compose.
            val bmp = instrumentacao.uiAutomation.takeScreenshot() ?: raiz.captureToImage().asAndroidBitmap()
            File(saida, "$nome.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        } catch (e: Throwable) {
            anota("aviso\t$nome sem captura: ${e.javaClass.simpleName}")
        }
        try {
            regra.enableAccessibilityChecks()
            raiz.tryPerformAccessibilityChecks()
            acessibilidade += "$nome\tsem achados"
        } catch (e: Throwable) {
            val linhas = e.message.orEmpty().lines().map { it.trim() }.filter { it.isNotEmpty() }
            if (linhas.isEmpty()) acessibilidade += "$nome\t${e.javaClass.simpleName}"
            linhas.forEach { acessibilidade += "$nome\t$it" }
        } finally {
            regra.disableAccessibilityChecks()
        }
    }

    /**
     * Desce a lista principal da tela item a item, com captura e verificações
     * em cada um, e volta ao topo. Pelo índice, e não por arrasto: o arrasto
     * podia cair num gráfico e não rolar nada.
     */
    private fun rola(nome: String, vezes: Int) {
        // A lista vertical da tela: pelo cabeçalho ela some da árvore assim que
        // o primeiro item sai da tela, e o passo seguinte não a achava mais.
        val lista = regra.onAllNodes(
            hasScrollToIndexAction() and SemanticsMatcher.keyIsDefined(SemanticsProperties.VerticalScrollAxisRange)
        ).onFirst()
        repeat(vezes) { i ->
            lista.performScrollToIndex(i + 1)
            tela("${nome}_${i + 1}")
        }
        // O que sai da tela numa LazyColumn deixa de existir: sem voltar, o
        // cartão do tempo, no alto, não seria achado.
        lista.performScrollToIndex(0)
        regra.waitForIdle()
    }

    private fun grava(sufixo: String = "") {
        File(saida, "passos$sufixo.tsv").writeText(passos.joinToString("\n") + "\n")
        File(saida, "acessibilidade$sufixo.tsv").writeText(acessibilidade.joinToString("\n") + "\n")
        acessibilidade.forEach { Log.i("PERCURSO", "a11y\t$it") }
    }

    /**
     * Outro estado: Mato Grosso, Sorriso. Com a API desta branch (o workflow a
     * sobe no runner e aponta BuildConfig.API_BASE_URL para ela), percorre
     * Resumo, Histórico, Mercado e Sobre; com um servidor que ainda não tenha
     * o estado (a API publicada antes da v2.5.0), confere que o app avisa em
     * vez de mostrar o Pará com outro nome.
     */
    @Test
    fun percorreOutroEstado() {
        val safra = anoDaSafraEmCurso()
        var cenario: ActivityScenario<MainActivity>? = null
        try {
            anota("api\t${BuildConfig.API_BASE_URL}")
            cenario = ActivityScenario.launch(MainActivity::class.java)
            espera("Qual é o seu município?")
            regra.onNodeWithText("Escolher na lista").performClick()
            regra.waitUntil(150_000) { regra.onAllNodes(hasSetTextAction()).fetchSemanticsNodes().isNotEmpty() }
            regra.onAllNodesWithText("Mato Grosso").onFirst().performClick()
            anota("estado\tMato Grosso escolhido")
            // Ao trocar o estado, a lista do Pará some na hora e a de Mato
            // Grosso chega da API: o campo de busca volta com ela. A lista só
            // desenha os nomes que cabem na janela, e Sorriso fica longe do
            // topo: só aparece pela busca (run 43460955234, 29_falha_mt).
            regra.waitUntil(150_000) {
                regra.onAllNodes(hasSetTextAction()).fetchSemanticsNodes().isNotEmpty() || existe("ainda não está")
            }
            tela("20_estado_mt")
            if (existe("ainda não está")) {
                confere("o servidor ainda não tem Mato Grosso, e o app avisa", true)
                anota("fim\tsem o estado no servidor")
                return
            }
            regra.onNode(hasSetTextAction()).performTextInput("Sor")
            espera("Sorriso")
            confere("a lista de Mato Grosso chegou da API, com Sorriso", true)
            tela("20_busca_mt")
            regra.onAllNodesWithText("Sorriso").onLast().performClick()
            espera("(safra $safra)")
            confere("Resumo de Sorriso com a safra em curso", existe("Sorriso"))
            tela("21_resumo_mt")
            rola("22_resumo_mt", 4)

            aba("Histórico")
            espera("Evolução histórica")
            confere("Histórico de Sorriso com o gráfico e os cartões por safra", existe("Ano "))
            tela("23_historico_mt")

            aba("Mercado")
            espera("Soja em Chicago")
            tela("24_mercado_mt")

            aba("Sobre")
            tela("25_sobre_mt")
            anota("fim\tpercurso em Mato Grosso completo")
        } catch (e: Throwable) {
            anota("FALHA\t${e.javaClass.simpleName}: ${e.message?.lines()?.firstOrNull()}")
            runCatching { tela("29_falha_mt") }
            throw e
        } finally {
            grava("_mt")
            cenario?.close()
        }
    }

    @Test
    fun percorreAsTelasComDadosReais() {
        val safra = anoDaSafraEmCurso()
        var cenario: ActivityScenario<MainActivity>? = null
        try {
            cenario = ActivityScenario.launch(MainActivity::class.java)
            espera("Qual é o seu município?")
            anota("abriu\tboas-vindas")
            tela("01_boas_vindas")

            regra.onNodeWithText("Escolher na lista").performClick()
            // A lista só desenha os nomes que cabem na janela: busca antes.
            regra.waitUntil(150_000) { regra.onAllNodes(hasSetTextAction()).fetchSemanticsNodes().isNotEmpty() }
            tela("02_lista")
            regra.onNode(hasSetTextAction()).performTextInput("Pau")
            espera("Pau D'Arco")
            anota("lista\tchegou da API")
            regra.onAllNodesWithText("Pau D'Arco").onLast().performClick()

            espera("(safra $safra)")
            anota("resumo\tsafra $safra carregada")
            confere("Resumo mostra a última safra do IBGE, 2025", existe("Safra 2025, IBGE"))
            tela("03_resumo")
            rola("04_resumo", 4)

            espera("Tempo em", 60_000)
            regra.onAllNodesWithText("Tempo em", substring = true).onFirst().performClick()
            espera("Agora", 90_000)
            anota("tempo\tprevisão carregada")
            tela("05_tempo")

            aba("Resumo")
            espera("Estimativa no campo")
            regra.onAllNodesWithText("Estimativa no campo").onFirst().performClick()
            espera("Conte plantas e vagens")
            tela("06_estimativa_no_campo")

            aba("Mapa")
            Thread.sleep(8_000) // o mapa é uma página do servidor numa WebView
            tela("07_mapa")

            aba("Histórico")
            // Os cartões vêm do ano mais distante para o mais antigo, e a
            // projeção vai além da safra em curso (2028 com a safra 2027): o
            // cartão da safra em curso não está no alto (run 43460955234).
            espera("Evolução histórica")
            confere("Histórico começa na projeção mais distante ou na safra em curso",
                    existe("Ano ${safra + 1}") || existe("Ano $safra"))
            tela("08_historico")
            rola("09_historico", 3)

            aba("Mercado")
            espera("Soja em Chicago")
            espera("R$", 90_000)
            tela("10_mercado")
            rola("11_mercado", 2)

            aba("Sobre")
            tela("12_sobre")

            // Sem internet: o app abre de novo com o que guardou.
            cenario.close()
            shell("svc wifi disable")
            shell("svc data disable")
            if (android.os.Build.VERSION.SDK_INT >= 30) shell("cmd connectivity airplane-mode enable")
            Thread.sleep(5_000)
            cenario = ActivityScenario.launch(MainActivity::class.java)
            espera("(safra $safra)", 60_000)
            confere("sem internet, o Resumo abre com os dados guardados", true)
            confere("sem internet, o app avisa", existe("Sem conexão"))
            tela("13_sem_internet")
            aba("Mapa")
            confere("sem internet, o Mapa explica", existe("Mapa indisponível sem conexão"))
            tela("14_mapa_sem_internet")
            aba("Mercado")
            Thread.sleep(3_000)
            tela("15_mercado_sem_internet")
            aba("Resumo")
            regra.onAllNodesWithText("Estimativa no campo").onFirst().performClick()
            confere("sem internet, a Estimativa no campo abre", existe("Conte plantas e vagens"))
            anota("fim\tpercurso completo")
        } catch (e: Throwable) {
            anota("FALHA\t${e.javaClass.simpleName}: ${e.message?.lines()?.firstOrNull()}")
            runCatching { tela("99_falha") }
            throw e
        } finally {
            if (android.os.Build.VERSION.SDK_INT >= 30) shell("cmd connectivity airplane-mode disable")
            shell("svc wifi enable")
            shell("svc data enable")
            grava()
            cenario?.close()
        }
    }
}
