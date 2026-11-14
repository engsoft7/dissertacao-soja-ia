package com.agrointeligencia.app

import android.widget.ImageView
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.github.takahirom.roborazzi.captureRoboImage
import com.google.gson.Gson
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
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
 * Os dados vêm de build/dados_capturas/, gravados pelo script
 * automacao_github/dados_das_capturas.py com as respostas reais da API. Sem
 * esses arquivos (rodando o teste sozinho, ou com o Yahoo fora do ar no caso
 * do mercado), cada tela volta à série de exemplo abaixo.
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

    private val historicoExemplo = (2001..2027).map { ano ->
        val tendencia = 2400.0 + (ano - 2001) * 35.0
        val observado = ano <= 2024
        PrevisaoHistorico(
            ano = ano,
            rendimento_predito = tendencia,
            rendimento_real = if (observado) tendencia + 260 * sin(ano * 1.7) else 0.0,
            margem_erro = 413.0
        )
    }

    private val previsaoExemplo = PrevisaoResponse(
        municipio = "Paragominas",
        historico = historicoExemplo,
        elNinos = listOf(2003, 2005, 2007, 2010, 2015, 2016, 2019, 2020, 2024),
        laNinas = listOf(2001, 2006, 2008, 2009, 2011, 2012, 2018, 2021, 2022, 2023),
        validacao = ValidacaoModelo(0.253, 0.253, 412.8, 13.6, 451, 38)
    )

    private val velas = (0 until 120).map { i ->
        val base = 125.0 + 3 * sin(i / 9.0) + i * 0.02
        val abre = base + 0.4 * sin(i * 1.3)
        val fecha = base + 0.4 * sin(i * 1.3 + 1)
        Vela(t = 1_792_670_400L + i * 300L, o = abre, h = maxOf(abre, fecha) + 0.3,
             l = minOf(abre, fecha) - 0.3, c = fecha, pa = fecha - 1.2)
    }

    private val mesesExemplo = (0 until 12).map { k ->
        val chicago = 128.0 + 6 * sin(k / 2.0)
        val base = -6.0 + 5 * sin(k / 3.0)
        MesPara(mes = String.format("%04d-%02d", 2025 + (k + 10) / 12, (k + 10) % 12 + 1),
                para = chicago + base, chicago = chicago, base = base)
    }

    private val mercadoExemplo = MercadoResponse(
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
        conab_fonte = "CONAB, Pedro Afonso (TO), março de 2026",
        para = EstimativaPara(
            fonte = "Agrolink, média mensal do Pará (praça publicada: Barcarena)",
            mes_base = mesesExemplo.last().mes, base_brl_saca = -1.2,
            meses = mesesExemplo, estimado_brl_saca = velas.last().c - 1.2
        )
    )

    // ── dados reais, quando o script os gravou ────────────────────────────────

    private inline fun <reified T> real(nome: String): T? =
        File("build/dados_capturas/$nome.json").takeIf { it.exists() }
            ?.let { Gson().fromJson(it.readText(), T::class.java) }

    private val previsao: PrevisaoResponse = real("previsao") ?: previsaoExemplo
    private val financas: FinancaResponse? = real("financas")
    private val mercadoReal: MercadoResponse? = real("mercado")
    // Praças do Pará: as da API quando ela já as manda; senão um exemplo com a
    // data de ontem (e uma praça parada), para a captura mostrar o bloco.
    private val pracasExemplo = java.time.LocalDate.now().minusDays(1).toString().let { ontem ->
        listOf(PracaPara("Redenção", "PA", 148.5, ontem), PracaPara("Barcarena", "PA", 148.5, ontem),
               PracaPara("Paragominas", "PA", 133.12, java.time.LocalDate.now().minusDays(32).toString()))
    }
    private val mercado: MercadoResponse = (mercadoReal ?: mercadoExemplo).let {
        if (it.pracas_para.isNullOrEmpty()) it.copy(pracas_para = pracasExemplo) else it
    }
    private val periodoMercado = if (mercadoReal != null) "1mo" else "1d"

    // Tempo: a resposta do Open-Meteo gravada pelo script, ou a de Paragominas
    // lida em 25/10/2026 (src/test/resources). O "agora" é o da própria
    // resposta, para a janela de pulverização começar na hora certa.
    private val tempo: PrevisaoTempo = real("tempo") ?: Gson().fromJson(
        javaClass.classLoader!!.getResource("openmeteo_paragominas_2026-10-25.json")!!.readText(),
        PrevisaoTempo::class.java
    )
    private val agoraTempo = java.time.LocalDateTime.parse(tempo.current!!.time!!)
    private val avisos: AvisosResponse = real("avisos") ?: AvisosResponse(disponivel = true, avisos = emptyList())

    // Um aviso real do INMET (tempestade de 26/10/2026 no sul do Pará), só
    // para desenhar o cartão: Paragominas não tinha aviso naquele dia.
    private val avisoExemplo = AvisosResponse(
        fonte = "INMET", disponivel = true, avisos = listOf(
            AvisoMeteorologico(
                id = "56174", evento = "Tempestade", severidade = "Perigo Potencial", nivel = 1, cor = "#FFFE00",
                inicio = "2026-10-26 00:00", fim = "2026-10-26 23:59",
                riscos = listOf("Chuva entre 20 e 30 mm/h ou até 50 mm/dia, ventos intensos (40-60 km/h), e queda de " +
                    "granizo. Baixo risco de corte de energia elétrica, estragos em plantações, queda de galhos de " +
                    "árvores e de alagamentos."),
                instrucoes = listOf("Evite usar aparelhos eletrônicos ligados à tomada.",
                    "Obtenha mais informações junto à Defesa Civil (telefone 199) e ao Corpo de Bombeiros (telefone 193).")
            )
        )
    )

    // A mesma escolha do AgroDashboard (Safra.kt): a projeção é a da safra em
    // curso, e a comparação é com a última safra que tem produtividade divulgada.
    private val historico = previsao.historico.sortedByDescending { it.ano }
    private val projecao = projecaoDaSafra(previsao.historico) ?: historico.first()
    private val ultimoReal = ultimoObservado(previsao.historico)

    // ── capturas ──────────────────────────────────────────────────────────────

    @Test fun historico_claro() = captura("historico", false) { HistoricoProdutividadeChart(historico, previsao) }

    @Config(qualifiers = "+night")
    @Test fun historico_escuro() = captura("historico", true) { HistoricoProdutividadeChart(historico, previsao) }

    // A tela Mercado passa da altura do celular: no aplicativo ela rola, mas a
    // captura só pega o que cabe na tela, e o fim saía espremido. Estas duas
    // são desenhadas num celular mais alto.
    @Config(qualifiers = "w411dp-h1400dp-xxhdpi")
    @Test fun mercado_claro() = captura("mercado", false) { MercadoConteudo(mercado, false, periodoMercado) {} }

    @Config(qualifiers = "w411dp-h1400dp-night-xxhdpi")
    @Test fun mercado_escuro() = captura("mercado", true) { MercadoConteudo(mercado, false, periodoMercado) {} }

    @Test fun resumo_claro() = captura("resumo", false) { ResumoAgronomicoCard(projecao, ultimoReal) }

    @Config(qualifiers = "+night")
    @Test fun resumo_escuro() = captura("resumo", true) { ResumoAgronomicoCard(projecao, ultimoReal) }

    @Test fun viabilidade_claro() = captura("viabilidade", false) {
        financas?.let { ResumoFinanceiroCard(projecao, it, mercado.para, mercado.pracas_para.orEmpty(), "Paragominas") }
    }

    @Test fun cartoes_historico_claro() = captura("cartoes_historico", false) {
        // O mesmo preço padrão do app: a praça em dia mais perto de Paragominas.
        val preco = pracaParaUsar("Paragominas", mercado.pracas_para.orEmpty())?.valor
        PrevisaoCard(projecao, financas, preco)
        ultimoReal?.let { PrevisaoCard(it, financas, preco) }
    }

    @Test fun sobre_claro() = captura("sobre", false) { MetodologiaCard(financas, previsao.validacao) }

    @Config(qualifiers = "+night")
    @Test fun sobre_escuro() = captura("sobre", true) { MetodologiaCard(financas, previsao.validacao) }

    // A tela Tempo é longa: desenhada num celular alto, como a do Mercado.
    @Config(qualifiers = "w411dp-h2100dp-xxhdpi")
    @Test fun tempo_claro() = captura("tempo", false) {
        TempoConteudo(tempo, avisos, SEDES_MUNICIPAIS["Paragominas"], agoraTempo, null, false, false)
    }

    @Config(qualifiers = "w411dp-h2100dp-night-xxhdpi")
    @Test fun tempo_escuro() = captura("tempo", true) {
        TempoConteudo(tempo, avisos, SEDES_MUNICIPAIS["Paragominas"], agoraTempo, null, false, false)
    }

    @Test fun aviso_inmet_claro() = captura("aviso_inmet", false) { CartaoAvisos(avisoExemplo) }

    // Janela de plantio: a resposta de /api/plantio/Paragominas gravada pelo
    // script, ou um exemplo com as datas da Região II do Pará na portaria. O
    // "hoje" fica fixo para a frase do cartão não mudar de um dia para o outro.
    private val plantio: PlantioResponse = real("plantio") ?: PlantioResponse(
        safra = "2026/2027", uf = "PA", municipio = "Paragominas",
        calendario = CalendarioPlantio(
            regiao = "II", vazio = listOf("2026-08-01", "2026-10-31"), semeadura = listOf("2026-11-01", "2027-02-28"),
            fonte = "Portaria SDA/MAPA nº 1.579, de 9 de abril de 2026", url = "https://www.in.gov.br/"),
        zarc = ZarcPlantio(
            portaria = "Portaria nº 203, de 03/07/2026", url = "https://dados.agricultura.gov.br/",
            ciclos = listOf(OpcaoZarc(20, "Grupo I"), OpcaoZarc(21, "Grupo II"), OpcaoZarc(22, "Grupo III")),
            solos = (11..16).map { OpcaoZarc(it, "AD${it - 10}") },
            riscos = mapOf("21-13" to buildString {
                for (i in 1..36) append(when (i) { in 1..3, in 33..36 -> '2'; 4, 32 -> '3'; 5 -> '4'; else -> '0' })
            })),
        lido_em = "2026-11-14")
    private val hojePlantio = java.time.LocalDate.of(2026, 11, 14)

    private fun estadoPlantio(): EstadoPlantio {
        val prefs = org.robolectric.RuntimeEnvironment.getApplication()
            .getSharedPreferences("capturas_plantio", android.content.Context.MODE_PRIVATE)
        prefs.edit().clear().commit()
        return EstadoPlantio(prefs).also { it.dados = plantio }
    }

    @Composable
    private fun telaPlantio(estado: EstadoPlantio) {
        PlantioResumoCard(estado, hojePlantio) {}
        Spacer(Modifier.height(16.dp))
        PlantioTela(estado, plantio.municipio, aoAtualizar = {}, aoVoltar = {}, hoje = hojePlantio)
    }

    @Config(qualifiers = "w411dp-h1700dp-xxhdpi")
    @Test fun plantio_claro() {
        val estado = estadoPlantio()
        captura("plantio", false) { telaPlantio(estado) }
    }

    // Alertas: INMET e preço ligados, com a praça de Paragominas e o alvo de R$ 140.
    private fun prefsDosAlertas() = org.robolectric.RuntimeEnvironment.getApplication()
        .getSharedPreferences("capturas_alertas", android.content.Context.MODE_PRIVATE).also {
            it.edit().clear().putBoolean(PREF_ALERTA_INMET, true).putBoolean(PREF_ALERTA_PRECO, true)
                .putString(PREF_ALERTA_PRECO_PRACA, "Paragominas").putFloat(PREF_ALERTA_PRECO_ALVO, 140f).commit()
        }

    @Config(qualifiers = "w411dp-h1500dp-xxhdpi")
    @Test fun alertas_claro() {
        val prefs = prefsDosAlertas()
        captura("alertas", false) {
            AlertasTela(prefs, SEDES_MUNICIPAIS["Paragominas"], mercado.pracas_para.orEmpty(),
                        mercado.pracas_para?.firstOrNull()) {}
        }
    }

    @Config(qualifiers = "w411dp-h1700dp-night-xxhdpi")
    @Test fun plantio_escuro() {
        val estado = estadoPlantio()
        captura("plantio", true) { telaPlantio(estado) }
    }

    // Escolha do município (2.7.0): o cartão da primeira abertura, o seletor
    // com o botão do GPS e a lista com busca, filtrada por "pa".
    @Composable
    private fun telaMunicipio() {
        val lista = SEDES_MUNICIPAIS.keys.sortedWith(java.text.Collator.getInstance(java.util.Locale("pt", "BR")))
        BoasVindasMunicipio(procurandoPosicao = false, aoUsarPosicao = {}, aoAbrirLista = {})
        Spacer(Modifier.height(16.dp))
        SeletorMunicipio("Paragominas", procurandoPosicao = false, aoAbrirLista = {}, aoUsarPosicao = {})
        Spacer(Modifier.height(16.dp))
        ListaDeMunicipios(lista, atual = "Paragominas", busca = "pa", aoBuscar = {}, aoEscolher = {})
    }

    @Config(qualifiers = "w411dp-h1100dp-xxhdpi")
    @Test fun municipio_claro() = captura("municipio", false) { telaMunicipio() }

    @Config(qualifiers = "w411dp-h1100dp-night-xxhdpi")
    @Test fun municipio_escuro() = captura("municipio", true) { telaMunicipio() }

    // ── outros estados (Estados.kt) ───────────────────────────────────────────
    // As mesmas telas com as respostas de um município de cada estado, gravadas
    // por dados_das_capturas.py: o resumo, a viabilidade (em Tocantins com o
    // custo aberto por item; nos outros, pelos dois rateios) e o cartão do
    // modelo, que mostra o R² dele ao lado do da referência naquele estado.
    @Composable
    private fun telasDoEstado(uf: String, municipio: String) {
        val p: PrevisaoResponse? = real("previsao_$uf")
        val f: FinancaResponse? = real("financas_$uf")
        val m: MunicipioResponse? = real("municipios_$uf")
        if (p == null || f == null) {
            Text("Sem as respostas de $uf: rode dados_das_capturas.py antes.")
            return
        }
        val projecaoUf = projecaoDaSafra(p.historico) ?: p.historico.maxByOrNull { it.ano }!!
        Text("$municipio (${estadoDoApp(uf).nome})", style = MaterialTheme.typography.titleMedium)
        ResumoAgronomicoCard(projecaoUf, ultimoObservado(p.historico))
        ResumoFinanceiroCard(projecaoUf, f, null, emptyList(), municipio, sedesDoEstado(uf, m?.sedes))
        MetodologiaCard(f, p.validacao)
    }

    @Config(qualifiers = "w411dp-h2600dp-xxhdpi")
    @Test fun estado_mt_claro() = captura("estado_mt", false) { telasDoEstado("MT", "Sorriso") }

    @Config(qualifiers = "w411dp-h2600dp-xxhdpi")
    @Test fun estado_ma_claro() = captura("estado_ma", false) { telasDoEstado("MA", "Balsas") }

    @Config(qualifiers = "w411dp-h2600dp-xxhdpi")
    @Test fun estado_to_claro() = captura("estado_to", false) { telasDoEstado("TO", "Porto Nacional") }

    @Config(qualifiers = "w411dp-h2600dp-xxhdpi")
    @Test fun estado_ro_claro() = captura("estado_ro", false) { telasDoEstado("RO", "Vilhena") }

    // A escolha do estado na janela do município: os cinco estados e a lista do escolhido.
    @Composable
    private fun telaEstados() {
        val m: MunicipioResponse? = real("municipios_MT")
        val estado = estadoDoApp("MT")
        SeletorEstado(estado) {}
        Spacer(Modifier.height(12.dp))
        ListaDeMunicipios(m?.municipios ?: listOf("Sinop", "Sorriso"), atual = "Sorriso", busca = "so",
                          aoBuscar = {}, aoEscolher = {}, estado = estado)
    }

    @Config(qualifiers = "w411dp-h900dp-xxhdpi")
    @Test fun municipio_estados_claro() = captura("municipio_estados", false) { telaEstados() }

    @Config(qualifiers = "w411dp-h900dp-night-xxhdpi")
    @Test fun municipio_estados_escuro() = captura("municipio_estados", true) { telaEstados() }

    // O ícone do launcher, montado pelo próprio Android a partir do
    // adaptive-icon: confere que as três camadas compilam e se encaixam.
    @Test fun icone() = captura("icone", false) {
        AndroidView(
            factory = { ImageView(it).apply { setImageResource(R.mipmap.ic_launcher) } },
            modifier = Modifier.size(192.dp)
        )
    }
}
