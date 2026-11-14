package com.agrointeligencia.app

import androidx.compose.ui.res.stringResource
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.LocationCity
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.Normalizer
import java.util.Locale
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

// ── o município escolhido ─────────────────────────────────────────────────
//
// O app reabre no último município escolhido. Antes ele abria sempre no
// primeiro da lista (Abel Figueiredo), e quem plantava em Paragominas tinha de
// trocar a cada vez. A escolha também pode vir do GPS: o celular acha a sede
// mais próxima entre os municípios do produto, e a posição não sai do aparelho.

/** Chave do município escolhido em AgroAppCache. */
const val PREF_MUNICIPIO = "municipio_escolhido"

/** Município da lista mais próximo de uma posição, com a distância até a sede. */
data class MunicipioProximo(val nome: String, val distanciaKm: Double)

// Acima disso a posição está longe de qualquer município do produto, e a
// frase diz isso em vez de afirmar que o produtor está naquele município.
const val DISTANCIA_PERTO_KM = 60.0

/** Distância em km entre dois pontos, pela fórmula de haversine. */
fun distanciaKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    val dLat = Math.toRadians(lat2 - lat1)
    val dLon = Math.toRadians(lon2 - lon1)
    val a = sin(dLat / 2).pow(2) +
        cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) * sin(dLon / 2).pow(2)
    return 2 * 6371.0 * asin(sqrt(a.coerceIn(0.0, 1.0)))
}

/**
 * A sede mais próxima entre [municipios]. Só entram os que têm sede conhecida
 * em [sedes]; nulo quando nenhum tem. A conta é feita no celular.
 */
fun municipioMaisProximo(
    lat: Double,
    lon: Double,
    municipios: Collection<String>,
    sedes: Map<String, LugarTempo> = SEDES_MUNICIPAIS,
): MunicipioProximo? =
    municipios.mapNotNull { nome -> sedes[nome]?.let { MunicipioProximo(nome, distanciaKm(lat, lon, it.lat, it.lon)) } }
        .minByOrNull { it.distanciaKm }

/** A frase que o app mostra depois de escolher pelo GPS. */
fun fraseDoMaisProximo(context: android.content.Context, p: MunicipioProximo, total: Int,
                       estado: EstadoDoApp = ESTADOS_DO_APP[0]): String {
    val km = p.distanciaKm.roundToInt()
    return when {
        km < 1 -> context.getString(R.string.mun_escolhido, p.nome)
        p.distanciaKm <= DISTANCIA_PERTO_KM -> context.getString(R.string.mun_escolhido_km, p.nome, km)
        else -> context.getString(R.string.mun_mais_proximo, p.nome, km, total, estado.no, estado.nome)
    }
}

/** Texto para busca: sem acento, sem maiúscula e sem apóstrofo ("Pau D'Arco" → "pau darco"). */
fun semAcento(s: String): String =
    Normalizer.normalize(s, Normalizer.Form.NFD)
        .replace(Regex("\\p{M}+"), "")
        .replace("'", "").replace("’", "")
        .lowercase(Locale.ROOT)
        .trim()

/**
 * Municípios que casam com a busca, sem ligar para acento: "maraba" acha
 * Marabá. Os que começam com o texto vêm antes dos que só o contêm.
 */
fun filtraMunicipios(lista: List<String>, busca: String): List<String> {
    val b = semAcento(busca)
    if (b.isEmpty()) return lista
    val comeca = lista.filter { semAcento(it).startsWith(b) }
    val contem = lista.filter { it !in comeca && semAcento(it).contains(b) }
    return comeca + contem
}

/** O município guardado, se ainda estiver na lista; senão nenhum, e o app pergunta qual é. */
fun municipioGuardadoValido(lista: List<String>, guardado: String?): String? =
    guardado?.takeIf { lista.isEmpty() || it in lista }

// ── telas ─────────────────────────────────────────────────────────────────

/**
 * O município atual e o botão do GPS, no alto de Resumo, Mapa e Histórico.
 * Tocar no nome abre a lista com busca; o botão ao lado escolhe a sede mais
 * próxima. Um campo só de leitura com menu, como antes, obrigava a rolar 38
 * nomes sem busca, e o leitor de tela não dizia o que o campo fazia.
 */
@Composable
fun SeletorMunicipio(
    municipio: String?,
    procurandoPosicao: Boolean,
    aoAbrirLista: () -> Unit,
    aoUsarPosicao: () -> Unit,
    estado: EstadoDoApp = ESTADOS_DO_APP[0],
) {
    val forma = RoundedCornerShape(12.dp)
    val rotuloTrocar = stringResource(R.string.mun_trocar)
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .weight(1f)
                .heightIn(min = 56.dp)
                .clip(forma)
                .border(1.dp, MaterialTheme.colorScheme.outline, forma)
                .clickable(onClickLabel = rotuloTrocar, role = Role.Button) { aoAbrirLista() }
                .padding(horizontal = 14.dp, vertical = 8.dp)
        ) {
            Icon(Icons.Filled.LocationCity, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                // Fora do Pará, o estado junto: o produtor vê de onde é a lista.
                Text(if (estado.uf == "PA") stringResource(R.string.mun_rotulo) else stringResource(R.string.mun_rotulo_estado, estado.nome),
                     fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(municipio ?: stringResource(R.string.mun_escolha_o_seu), fontSize = 17.sp, fontWeight = FontWeight.SemiBold,
                     color = MaterialTheme.colorScheme.onSurface, maxLines = 1)
            }
            Icon(Icons.Filled.ArrowDropDown, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(8.dp))
        FilledTonalIconButton(
            onClick = aoUsarPosicao,
            enabled = !procurandoPosicao,
            modifier = Modifier.size(56.dp)
        ) {
            if (procurandoPosicao) {
                CircularProgressIndicator(modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
            } else {
                Icon(Icons.Filled.MyLocation, contentDescription = stringResource(R.string.mun_gps_descricao))
            }
        }
    }
    if (procurandoPosicao) {
        Text(stringResource(R.string.mun_procurando), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
             modifier = Modifier.padding(top = 4.dp))
    }
}

/**
 * Primeira abertura, ou município que saiu da lista: em vez de abrir num
 * município qualquer, o app pergunta, e diz o que faz com a posição.
 */
@Composable
fun BoasVindasMunicipio(procurandoPosicao: Boolean, aoUsarPosicao: () -> Unit, aoAbrirLista: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.10f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(stringResource(R.string.mun_qual), fontSize = 20.sp, fontWeight = FontWeight.Bold,
                 color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.semantics { heading() })
            Text(stringResource(R.string.mun_boas_vindas),
                 fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface, lineHeight = 20.sp)
            Button(onClick = aoUsarPosicao, enabled = !procurandoPosicao,
                   modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                if (procurandoPosicao) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp,
                                              color = MaterialTheme.colorScheme.onPrimary)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.mun_procurando))
                } else {
                    Icon(Icons.Filled.MyLocation, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.mun_usar_localizacao))
                }
            }
            OutlinedButton(onClick = aoAbrirLista, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                Icon(Icons.Filled.Search, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.mun_escolher_lista))
            }
            Text(stringResource(R.string.mun_privacidade),
                 fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp)
        }
    }
}

/** A lista com busca, dentro da janela de escolha; separada para as capturas de tela. */
@Composable
fun ListaDeMunicipios(
    municipios: List<String>,
    atual: String?,
    busca: String,
    aoBuscar: (String) -> Unit,
    aoEscolher: (String) -> Unit,
    estado: EstadoDoApp = ESTADOS_DO_APP[0],
) {
    val filtrados = filtraMunicipios(municipios, busca)
    OutlinedTextField(
        value = busca,
        onValueChange = aoBuscar,
        singleLine = true,
        placeholder = { Text(stringResource(R.string.mun_buscar)) },
        leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
        trailingIcon = {
            if (busca.isNotEmpty()) {
                IconButton(onClick = { aoBuscar("") }) { Icon(Icons.Filled.Clear, contentDescription = stringResource(R.string.mun_limpar)) }
            }
        },
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
        modifier = Modifier.fillMaxWidth()
    )
    Text(
        if (filtrados.isEmpty()) stringResource(R.string.mun_nenhum, municipios.size, estado.no, estado.nome)
        else stringResource(R.string.mun_contagem, filtrados.size, municipios.size),
        fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 6.dp, bottom = 2.dp)
    )
    LazyColumn(modifier = Modifier.fillMaxWidth().heightIn(max = 360.dp)) {
        items(filtrados) { mun ->
            val escolhido = mun == atual
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 48.dp)
                    .selectable(selected = escolhido, role = Role.RadioButton) { aoEscolher(mun) }
                    .padding(horizontal = 4.dp)
            ) {
                Text(mun, fontSize = 16.sp, modifier = Modifier.weight(1f),
                     fontWeight = if (escolhido) FontWeight.Bold else FontWeight.Normal,
                     color = if (escolhido) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface)
                if (escolhido) Icon(Icons.Filled.Check, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

/** Janela de escolha: o GPS no alto e a lista com busca embaixo. */
@Composable
fun EscolhaMunicipioDialog(
    municipios: List<String>,
    atual: String?,
    procurandoPosicao: Boolean,
    aoUsarPosicao: () -> Unit,
    aoEscolher: (String) -> Unit,
    aoFechar: () -> Unit,
    estado: EstadoDoApp = ESTADOS_DO_APP[0],
    aoEscolherEstado: ((String) -> Unit)? = null,
    avisoDoEstado: String? = null,
) {
    var busca by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = aoFechar,
        icon = { Icon(Icons.Filled.LocationCity, contentDescription = null) },
        title = { Text(stringResource(R.string.mun_escolha_titulo)) },
        text = {
            Column {
                // O estado antes do município: os de ESTADOS_DO_APP (Estados.kt).
                aoEscolherEstado?.let { escolher ->
                    SeletorEstado(estado, escolher)
                    Spacer(Modifier.size(12.dp))
                }
                FilledTonalButton(onClick = aoUsarPosicao, enabled = !procurandoPosicao,
                                  modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    if (procurandoPosicao) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.mun_procurando))
                    } else {
                        Icon(Icons.Filled.MyLocation, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.mun_mais_proximo_botao))
                    }
                }
                Spacer(Modifier.size(12.dp))
                if (municipios.isEmpty()) {
                    Text(avisoDoEstado ?: stringResource(R.string.mun_sem_lista),
                         fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    ListaDeMunicipios(municipios, atual, busca, { busca = it }, aoEscolher, estado)
                }
            }
        },
        confirmButton = { TextButton(onClick = aoFechar) { Text(stringResource(R.string.fechar)) } }
    )
}

/** Os três estados em botões de escolha; o leitor de tela diz qual está marcado. */
@Composable
fun SeletorEstado(estado: EstadoDoApp, aoEscolher: (String) -> Unit) {
    Text(stringResource(R.string.estado_rotulo), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    // Rola de lado se não couber: os cinco não cabem na janela.
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp),
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp).horizontalScroll(rememberScrollState())) {
        ESTADOS_DO_APP.forEach { e ->
            FilterChip(
                selected = e.uf == estado.uf,
                onClick = { aoEscolher(e.uf) },
                label = { Text(e.nome, maxLines = 1) },
                modifier = Modifier.heightIn(min = 48.dp),
            )
        }
    }
}
