package com.agrointeligencia.app

import androidx.compose.ui.res.stringResource
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Fontes dos dados que o aplicativo mostra, com o endereço oficial de cada uma.
 *
 * O Google Play exige, para apps que exibem informação de órgãos públicos sem ser
 * do governo, links claros e funcionando para as fontes originais e o aviso de que
 * o app não representa nenhum órgão (política de declarações enganosas). Os mesmos
 * endereços estão na descrição da loja (aplicativo_mobile/loja/textos_da_loja.txt),
 * conferidos pelo workflow confere-links-loja.yml; FontesOficiaisTest garante que
 * as duas listas não se separem.
 */
/**
 * O que é ([dado], texto de strings.xml) e de quem é ([instituicao]: texto de
 * strings.xml, ou o nome próprio da instituição quando [instituicaoNome] vem
 * preenchido, igual em qualquer idioma).
 */
data class Fonte(val dado: Int, val instituicao: Int, val url: String, val instituicaoNome: String? = null)

private fun fonte(dado: Int, nome: String, url: String) = Fonte(dado, 0, url, nome)

val FONTES_OFICIAIS = listOf(
    Fonte(R.string.fonte_produtividade, R.string.fonte_produtividade_inst, "https://sidra.ibge.gov.br/tabela/1612"),
    fonte(R.string.fonte_avisos, "INMET", "https://portal.inmet.gov.br/"),
    fonte(R.string.fonte_custo, "CONAB",
          "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/custos-de-producao"),
    Fonte(R.string.fonte_calendario, R.string.fonte_calendario_inst,
          "https://www.in.gov.br/web/dou/-/portaria-sda/mapa-n-1.579-de-9-de-abril-de-2026-698696654"),
    Fonte(R.string.fonte_zarc, R.string.fonte_ministerio,
          "https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico"),
    fonte(R.string.fonte_pulverizacao, "Embrapa Soja",
          "https://ainfo.cnptia.embrapa.br/digital/bitstream/item/223209/1/SP-17-2020-online-1.pdf"),
    fonte(R.string.fonte_enso, "NOAA",
          "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php"),
)

val OUTRAS_FONTES = listOf(
    Fonte(R.string.fonte_vegetacao, R.string.fonte_vegetacao_inst,
          "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1"),
    fonte(R.string.fonte_mascara, "MapBiomas", "https://brasil.mapbiomas.org"),
    fonte(R.string.fonte_chuva, "CHIRPS", "https://www.chc.ucsb.edu/data/chirps"),
    fonte(R.string.fonte_clima, "ERA5-Land, Copernicus", "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land"),
    fonte(R.string.fonte_previsao, "Open-Meteo", "https://open-meteo.com"),
    fonte(R.string.fonte_preco_para, "Agrolink", "https://www.agrolink.com.br/cotacoes/historico/pa/soja-em-grao-sc-60kg"),
)

/** Aviso de não afiliação e as fontes com link, na tela Sobre. Tocar numa fonte abre o endereço. */
@Composable
fun FontesDosDados() {
    val abre = LocalUriHandler.current
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.aviso_nao_governo), fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
             color = MaterialTheme.colorScheme.onSurface, lineHeight = 18.sp)
        Spacer(Modifier.height(12.dp))
        for ((titulo, fontes) in listOf(stringResource(R.string.fontes_oficiais_titulo) to FONTES_OFICIAIS,
                                        stringResource(R.string.outras_fontes_titulo) to OUTRAS_FONTES)) {
            Text(titulo, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
            for (f in fontes) {
                Column(
                    // 48 dp de alvo de toque: as fontes de link curto (INMET,
                    // MapBiomas) ficavam com 44 a 46 dp (Accessibility Test
                    // Framework, Teste Premium de 14/11/2026).
                    modifier = Modifier.fillMaxWidth()
                        .heightIn(min = 48.dp)
                        .clickable { runCatching { abre.openUri(f.url) } }
                        .padding(vertical = 6.dp)
                ) {
                    Text(stringResource(f.dado) + ": " + (f.instituicaoNome ?: stringResource(f.instituicao)),
                         fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
                    Text(f.url, fontSize = 12.sp, color = MaterialTheme.colorScheme.primary,
                         textDecoration = TextDecoration.Underline, lineHeight = 16.sp)
                }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}
