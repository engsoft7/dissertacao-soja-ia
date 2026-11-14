package com.agrointeligencia.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.github.takahirom.roborazzi.captureRoboImage
import com.google.gson.Gson
import java.io.File
import java.time.LocalDate
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Captura da Estimativa no campo, com cinco pontos de exemplo. O preço e a
 * previsão do município saem como no app (MainActivity, aba 5) para
 * Paragominas: a cotação da praça do Pará em dia mais perto e a projeção da
 * safra em curso, das respostas reais gravadas por dados_das_capturas.py.
 * Antes eram fixos (preço da CONAB e safra de 2026), e a captura mostrava o
 * que o app deixou de mostrar na 2.7.2. Fica fora de CapturasDeTelaTest, mas
 * com o nome terminado igual, para o filtro "*CapturasDeTelaTest*" do
 * capturas.yml também desenhá-la.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "pt-rBR")
class CampoCapturasDeTelaTest {

    @get:Rule
    val compose = createComposeRule()

    private val exemplo = EstadoCampo(
        pontos = listOf(
            PontoAmostra(13, 1.0, 5, 196),
            PontoAmostra(12, 1.0, 5, 171),
            PontoAmostra(14, 1.0, 5, 205),
            PontoAmostra(11, 1.0, 5, 188),
            PontoAmostra(13, 1.0, 5, 179),
        ),
        areaHa = 48.5,
    )

    private inline fun <reified T> real(nome: String): T? =
        File("build/dados_capturas/$nome.json").takeIf { it.exists() }
            ?.let { Gson().fromJson(it.readText(), T::class.java) }

    // Sem as respostas gravadas, o exemplo de CapturasDeTelaTest: Barcarena, ontem.
    private val praca = pracaParaUsar("Paragominas", real<MercadoResponse>("mercado")?.pracas_para.orEmpty())
        ?: PracaPara("Barcarena", "PA", 148.5, LocalDate.now().minusDays(1).toString())
    private val projecao = real<PrevisaoResponse>("previsao")?.historico?.let { projecaoDaSafra(it) }

    private fun captura(escuro: Boolean) {
        compose.setContent {
            MaterialTheme(colorScheme = esquemaAgro(escuro)) {
                Surface(color = MaterialTheme.colorScheme.background) {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                        EstimativaCampoTela(
                            precoPadrao = praca.valor,
                            fontePreco = "Cotação de ${praca.praca} em ${dataCurta(praca.data)} (Agrolink).",
                            referenciaKgHa = projecao?.rendimento_predito ?: 3297.0,
                            rotuloReferencia = "Paragominas em ${projecao?.ano ?: anoDaSafraEmCurso()}",
                            aoVoltar = {},
                            inicial = exemplo,
                        )
                    }
                }
            }
        }
        compose.onRoot().captureRoboImage("build/capturas/estimativa_campo_${if (escuro) "escuro" else "claro"}.png")
    }

    @Config(qualifiers = "pt-rBR-w411dp-h2300dp-xxhdpi")
    @Test fun estimativa_campo_claro() = captura(false)

    @Config(qualifiers = "pt-rBR-w411dp-h2300dp-night-xxhdpi")
    @Test fun estimativa_campo_escuro() = captura(true)
}
