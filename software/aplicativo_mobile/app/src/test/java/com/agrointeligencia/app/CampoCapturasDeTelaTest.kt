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
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Captura da Estimativa no campo, com cinco pontos de exemplo. O preço e a
 * previsão do município são os que o app mostra para Paragominas: o preço
 * recebido do levantamento da CONAB e a projeção do Resumo. Fica fora de
 * CapturasDeTelaTest, mas com o nome terminado igual, para o filtro
 * "*CapturasDeTelaTest*" do capturas.yml também desenhá-la.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35])
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

    private fun captura(escuro: Boolean) {
        compose.setContent {
            MaterialTheme(colorScheme = esquemaAgro(escuro)) {
                Surface(color = MaterialTheme.colorScheme.background) {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                        EstimativaCampoTela(
                            precoPadrao = 105.09,
                            fontePreco = "Preço de referência: CONAB, Pedro Afonso (TO), março de 2026.",
                            referenciaKgHa = 3318.0,
                            rotuloReferencia = "Paragominas em 2026",
                            aoVoltar = {},
                            inicial = exemplo,
                        )
                    }
                }
            }
        }
        compose.onRoot().captureRoboImage("build/capturas/estimativa_campo_${if (escuro) "escuro" else "claro"}.png")
    }

    @Config(qualifiers = "w411dp-h2300dp-xxhdpi")
    @Test fun estimativa_campo_claro() = captura(false)

    @Config(qualifiers = "w411dp-h2300dp-night-xxhdpi")
    @Test fun estimativa_campo_escuro() = captura(true)
}
