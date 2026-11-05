package com.agrointeligencia.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay

/**
 * Leitura única da posição do celular, com o pedido de permissão quando falta.
 * Serve a tela Tempo ("Minha localização") e a escolha do município mais
 * próximo. Antes o código vivia dentro da tela Tempo; com dois usos, ficou aqui.
 */
class LeitorDePosicao internal constructor() {
    /** true enquanto espera o GPS ou a rede responder. */
    var procurando by mutableStateOf(false)
        internal set
    internal var iniciar: () -> Unit = {}

    /** Lê a posição; pede a permissão antes, se ainda não houver. */
    fun ler() = iniciar()
}

// Sem resposta nesse tempo (dentro de casa, sem sinal), o app desiste e avisa,
// em vez de deixar a barra de progresso girando para sempre.
private const val ESPERA_POSICAO_MS = 30_000L
// A última posição conhecida basta se for desta última hora: a previsão do
// tempo e a escolha do município têm resolução de quilômetros.
private const val IDADE_MAXIMA_POSICAO_MS = 60 * 60 * 1000L

/**
 * [aoObter] recebe a posição; [aoFalhar], a frase a mostrar quando não há
 * permissão ([semPermissao]), a localização está desligada ou o tempo esgota.
 */
@SuppressLint("MissingPermission") // a permissão é conferida antes de pedir posições
@Composable
fun rememberLeitorDePosicao(
    semPermissao: String,
    aoFalhar: (String) -> Unit,
    aoObter: (lat: Double, lon: Double) -> Unit,
): LeitorDePosicao {
    val context = LocalContext.current
    val obter by rememberUpdatedState(aoObter)
    val falhar by rememberUpdatedState(aoFalhar)
    val leitor = remember { LeitorDePosicao() }
    val gerente = remember { context.getSystemService(Context.LOCATION_SERVICE) as LocationManager }
    val ouvinte = remember {
        object : LocationListener {
            override fun onLocationChanged(location: Location) {
                gerente.removeUpdates(this)
                leitor.procurando = false
                obter(location.latitude, location.longitude)
            }
            // Todos os métodos, como em EstimativaCampo: até o Android 10 a
            // interface não tinha implementação padrão para os demais.
            override fun onProviderDisabled(provider: String) {}
            override fun onProviderEnabled(provider: String) {}
            @Deprecated("Exigido até o Android 10")
            override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}
        }
    }
    DisposableEffect(Unit) { onDispose { gerente.removeUpdates(ouvinte) } }
    LaunchedEffect(leitor.procurando) {
        if (leitor.procurando) {
            delay(ESPERA_POSICAO_MS)
            gerente.removeUpdates(ouvinte)
            leitor.procurando = false
            falhar("Não foi possível achar sua posição. Tente ao ar livre ou perto de uma janela.")
        }
    }

    fun localizar() {
        val recente = listOf(LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER, LocationManager.PASSIVE_PROVIDER)
            .mapNotNull { runCatching { gerente.getLastKnownLocation(it) }.getOrNull() }
            .maxByOrNull { it.time }
            ?.takeIf { System.currentTimeMillis() - it.time < IDADE_MAXIMA_POSICAO_MS }
        if (recente != null) {
            obter(recente.latitude, recente.longitude)
            return
        }
        val provedor = listOf(LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER)
            .firstOrNull { runCatching { gerente.isProviderEnabled(it) }.getOrDefault(false) }
        if (provedor == null) {
            falhar("A localização do celular está desligada. Ligue-a e toque de novo.")
            return
        }
        leitor.procurando = true
        try {
            gerente.requestLocationUpdates(provedor, 0L, 0f, ouvinte, Looper.getMainLooper())
        } catch (_: Exception) {
            leitor.procurando = false
            falhar("Não foi possível ler a posição do celular.")
        }
    }

    fun temPermissao() = listOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        .any { ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED }
    val pedir = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        if (temPermissao()) localizar() else falhar(semPermissao)
    }
    SideEffect {
        leitor.iniciar = {
            // Um segundo toque enquanto procura não abre outra leitura.
            if (!leitor.procurando) {
                if (temPermissao()) localizar()
                else pedir.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
            }
        }
    }
    return leitor
}
