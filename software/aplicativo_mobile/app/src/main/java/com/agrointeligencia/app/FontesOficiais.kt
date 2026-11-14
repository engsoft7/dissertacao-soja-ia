package com.agrointeligencia.app

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
data class Fonte(val dado: String, val instituicao: String, val url: String)

val FONTES_OFICIAIS = listOf(
    Fonte("Produtividade municipal", "IBGE, Produção Agrícola Municipal", "https://sidra.ibge.gov.br/tabela/1612"),
    Fonte("Avisos meteorológicos", "INMET", "https://portal.inmet.gov.br/"),
    Fonte("Custo de produção e preço de referência", "CONAB",
          "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/custos-de-producao"),
    Fonte("Calendário de semeadura e vazio sanitário", "Ministério da Agricultura, Portaria SDA/MAPA nº 1.579/2026",
          "https://www.in.gov.br/web/dou/-/portaria-sda/mapa-n-1.579-de-9-de-abril-de-2026-698696654"),
    Fonte("Risco climático do plantio (ZARC)", "Ministério da Agricultura",
          "https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico"),
    Fonte("Critérios da janela de pulverização", "Embrapa Soja",
          "https://ainfo.cnptia.embrapa.br/digital/bitstream/item/223209/1/SP-17-2020-online-1.pdf"),
    Fonte("El Niño e La Niña (índice ONI)", "NOAA",
          "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php"),
)

val OUTRAS_FONTES = listOf(
    Fonte("Vegetação por satélite", "MODIS (NASA), pelo Google Earth Engine",
          "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1"),
    Fonte("Máscara de soja", "MapBiomas", "https://brasil.mapbiomas.org"),
    Fonte("Chuva", "CHIRPS", "https://www.chc.ucsb.edu/data/chirps"),
    Fonte("Clima", "ERA5-Land, Copernicus", "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land"),
    Fonte("Previsão do tempo", "Open-Meteo", "https://open-meteo.com"),
    Fonte("Preço do Pará", "Agrolink", "https://www.agrolink.com.br/cotacoes/historico/pa/soja-em-grao-sc-60kg"),
)

const val AVISO_NAO_GOVERNO =
    "O AgroInteligência não é um aplicativo do governo e não representa nenhum órgão público. " +
    "Não tem vínculo com o IBGE, o INMET, a CONAB, a Embrapa, o Ministério da Agricultura, a NOAA ou a " +
    "NASA: apenas usa dados " +
    "abertos publicados por essas instituições, nos endereços abaixo."

/** Aviso de não afiliação e as fontes com link, na tela Sobre. Tocar numa fonte abre o endereço. */
@Composable
fun FontesDosDados() {
    val abre = LocalUriHandler.current
    val secundaria = MaterialTheme.colorScheme.onSurfaceVariant
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(AVISO_NAO_GOVERNO, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
             color = MaterialTheme.colorScheme.onSurface, lineHeight = 18.sp)
        Spacer(Modifier.height(12.dp))
        for ((titulo, fontes) in listOf("Fontes oficiais (órgãos públicos)" to FONTES_OFICIAIS,
                                        "Outras fontes" to OUTRAS_FONTES)) {
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
                    Text("${f.dado}: ${f.instituicao}", fontSize = 12.sp, color = secundaria, lineHeight = 16.sp)
                    Text(f.url, fontSize = 12.sp, color = MaterialTheme.colorScheme.primary,
                         textDecoration = TextDecoration.Underline, lineHeight = 16.sp)
                }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}
