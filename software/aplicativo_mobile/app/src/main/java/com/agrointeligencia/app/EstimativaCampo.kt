package com.agrointeligencia.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.media.ExifInterface
import android.net.Uri
import android.os.Bundle
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.isSpecified
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChanged
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

// ESTIMATIVA NO CAMPO: A LAVOURA DO PRODUTOR, E NÃO A MÉDIA DO MUNICÍPIO.
//
// O modelo do app prevê a produtividade média do município a partir de
// satélite e clima. O talhão de cada produtor pode estar bem acima ou bem
// abaixo dessa média, e quem está na lavoura consegue medir: conta plantas
// numa linha, arranca algumas, conta as vagens. Esta tela organiza essa
// contagem, faz a conta (CampoCalculo.kt) e leva o resultado a sacas e reais.
//
// A contagem é do produtor: ele toca em cada planta ou vagem na foto, e o app
// só soma. Nas vagens, o contador automático (ContadorVagens.kt) pode
// preencher o número e sugerir as marcas, mas foi treinado com fotos da China
// e ainda não foi conferido em lavouras do Pará: a tela diz isso, e o
// produtor confere tocando na foto. Foto com marcas só do contador, sem
// conferência, não vai para o material de treino. O modo automático
// (ModoAutomatico.kt), em que o número entra sem conferência, fica desligado
// até um modelo medido no Pará ser anunciado pela API.
//
// Depois da colheita, o produtor informa quantas sacas saíram do talhão, e o
// app compara com a estimativa. O talhão, com os pontos e a colheita, vai no
// .zip das fotos (AmostrasTreino.kt) para conferir a estimativa e o contador.

private const val PREF_CAMPO = "estimativa_campo"
// Precisão mínima para aceitar um canto do talhão. Com 20 m de erro em cada
// canto, um talhão de 10 ha já erra a área em mais de 10%.
private const val PRECISAO_MAX_M = 20f

/** O que a tela guarda entre uma abertura e outra do aplicativo. */
data class EstadoCampo(
    val pontos: List<PontoAmostra> = emptyList(),
    val parametros: ParametrosCampo = ParametrosCampo(),
    val areaHa: Double? = null,
    /** Identificação do talhão em que se está contando; null nos estados guardados antes dela. */
    val talhao: String? = null,
    /** Sacas de 60 kg que saíram do talhão, quando o produtor informa. */
    val colhidoSacas: Double? = null,
)

private fun novoTalhao(): String = UUID.randomUUID().toString().replace("-", "").take(12)

/** O número de um campo, no separador decimal do idioma (numeroDigitado, CadernoCalculo.kt). */
private fun String.numero(): Double? = numeroDigitado(this)

private fun decimal(v: Double, casas: Int = 1): String = String.format(LOCAL_NUMEROS, "%,.${casas}f", v)

/** Para pôr de volta num campo: sem separador de milhar, que um número sem decimais deixaria ambíguo. */
private fun paraCampo(v: Double, casas: Int): String = String.format(LOCAL_NUMEROS, "%.${casas}f", v)

@Suppress("SENSELESS_COMPARISON")
private fun lerEstado(context: Context): EstadoCampo {
    val json = context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE).getString(PREF_CAMPO, null)
        ?: return EstadoCampo()
    // O Gson não passa pelo construtor: um campo ausente vira null mesmo em
    // tipo não nulo. Qualquer coisa estranha volta ao estado vazio.
    return try {
        val e: EstadoCampo? = Gson().fromJson(json, EstadoCampo::class.java)
        if (e == null || e.pontos == null || e.parametros == null) EstadoCampo() else e
    } catch (_: Exception) {
        EstadoCampo()
    }
}

private fun gravarEstado(context: Context, estado: EstadoCampo) {
    context.getSharedPreferences("AgroAppCache", Context.MODE_PRIVATE)
        .edit().putString(PREF_CAMPO, Gson().toJson(estado)).apply()
}

/**
 * A tela inteira. [precoPadrao] é o preço do produtor, se ele já informou na
 * Viabilidade, ou o de referência; [referenciaKgHa] é a previsão do modelo
 * para o município selecionado, mostrada ao lado para comparação.
 * [inicial] serve às capturas de tela; no aplicativo, a tela abre com o que
 * ficou guardado.
 */
@Composable
fun EstimativaCampoTela(
    precoPadrao: Double?,
    fontePreco: String?,
    referenciaKgHa: Double?,
    rotuloReferencia: String?,
    aoVoltar: () -> Unit,
    inicial: EstadoCampo? = null,
) {
    val context = LocalContext.current
    val guardado = remember { inicial ?: lerEstado(context) }

    val pontos = remember { mutableStateListOf<PontoAmostra>().apply { addAll(guardado.pontos) } }
    var espacamento by rememberSaveable { mutableStateOf(decimal(guardado.parametros.espacamento, 2)) }
    var graos by rememberSaveable { mutableStateOf(decimal(guardado.parametros.graosPorVagem, 1)) }
    var pesoMil by rememberSaveable { mutableStateOf(decimal(guardado.parametros.pesoMilGraos, 0)) }
    var area by rememberSaveable { mutableStateOf(guardado.areaHa?.let { decimal(it, 2) } ?: "") }
    var preco by rememberSaveable { mutableStateOf(precoPadrao?.let { decimal(it, 2) } ?: "") }
    var talhao by rememberSaveable { mutableStateOf(guardado.talhao ?: novoTalhao()) }
    var colhido by rememberSaveable {
        mutableStateOf(guardado.colhidoSacas?.let { paraCampo(it, if (it % 1.0 == 0.0) 0 else 1) } ?: "")
    }

    val parametros = ParametrosCampo(espacamento.numero() ?: 0.0, graos.numero() ?: 0.0, pesoMil.numero() ?: 0.0)
    val areaHa = area.numero()?.takeIf { it > 0 }
    val colhidoSacas = colhido.numero()?.takeIf { it > 0 }

    // O modo automático só vale com um modelo baixado que o anúncio liberou.
    val baixado = remember { if (inicial == null) modeloBaixado(context) else null }
    val automatico = modoAutomaticoLigado(baixado)
    val limites = limitesDe(baixado)

    // Guarda a cada mudança: contar trinta vagens e perder ao fechar o app é defeito.
    LaunchedEffect(pontos.toList(), parametros, areaHa, talhao, colhidoSacas) {
        if (inicial != null) return@LaunchedEffect
        val estado = EstadoCampo(pontos.toList(), parametros, areaHa, talhao, colhidoSacas)
        gravarEstado(context, estado)
        withContext(Dispatchers.IO) {
            val agora = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(Date())
            registroDoTalhao(estado, agora, BuildConfig.VERSION_NAME, versaoContador(context), automatico)
                ?.let { gravaTalhao(context, it) }
        }
    }
    // Fotos de amostragem antigas não servem para nada depois de contadas.
    LaunchedEffect(Unit) {
        withContext(Dispatchers.IO) {
            val limite = System.currentTimeMillis() - 2 * 86_400_000L
            File(context.cacheDir, "fotos").listFiles()?.filter { it.lastModified() < limite }?.forEach { it.delete() }
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = aoVoltar) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.voltar_ao_resumo))
            }
            Text(stringResource(R.string.campo_titulo), fontSize = 20.sp, fontWeight = FontWeight.SemiBold,
                 color = MaterialTheme.colorScheme.onBackground)
        }
        Text(
            stringResource(R.string.campo_intro),
            fontSize = 13.sp, lineHeight = 18.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        var fotosGuardadas by remember { mutableIntStateOf(0) }
        var colheitas by remember { mutableIntStateOf(0) }
        LaunchedEffect(Unit) { fotosGuardadas = withContext(Dispatchers.IO) { contaAmostras(context) } }
        LaunchedEffect(colhidoSacas, areaHa) {
            if (inicial == null) colheitas = withContext(Dispatchers.IO) { talhoesComColheita(context) }
        }

        NovoPonto(
            numero = pontos.size + 1,
            parametros = parametros,
            automatico = automatico,
            limites = limites,
            automaticosAntes = pontos.count { it.vagensDoContador != null },
            aoGuardarFotos = { fotosGuardadas = contaAmostras(context) },
        ) { pontos.add(it) }

        if (pontos.isNotEmpty()) {
            CartaoCampo(stringResource(R.string.campo_pontos_guardados), Icons.Filled.DoneAll) {
                pontos.forEachIndexed { i, p ->
                    val kg = if (p.valido() && parametros.espacamento > 0)
                        kgPorHectare(plantasPorM2(p, parametros.espacamento), vagensPorPlanta(p),
                                     parametros.graosPorVagem, parametros.pesoMilGraos) else null
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.weight(1f)) {
                            Text(kg?.let { stringResource(R.string.campo_ponto_sc, i + 1, decimal(it / 60, 1)) }
                                     ?: stringResource(R.string.campo_ponto, i + 1),
                                 fontSize = 14.sp, fontWeight = FontWeight.SemiBold,
                                 color = MaterialTheme.colorScheme.onSurface)
                            Text(stringResource(R.string.campo_ponto_detalhe, p.plantas, decimal(p.metrosDeLinha, 1),
                                                p.vagens, p.arrancadas),
                                 fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        IconButton(onClick = { pontos.removeAt(i) }) {
                            Icon(Icons.Filled.Delete, contentDescription = stringResource(R.string.campo_apagar_ponto, i + 1),
                                 tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }

        CartaoCampo(stringResource(R.string.campo_cultivar), Icons.Filled.Tune) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CampoNumero(espacamento, { espacamento = it }, stringResource(R.string.campo_entre_linhas), Modifier.weight(1f))
                CampoNumero(graos, { graos = it }, stringResource(R.string.campo_graos_vagem), Modifier.weight(1f))
                CampoNumero(pesoMil, { pesoMil = it }, stringResource(R.string.campo_mil_graos), Modifier.weight(1f), inteiro = true)
            }
            Nota(stringResource(R.string.campo_cultivar_nota))
        }

        CartaoCampo(stringResource(R.string.campo_area_talhao), Icons.Filled.Straighten) {
            var medindo by rememberSaveable { mutableStateOf(false) }
            CampoNumero(area, { area = it }, stringResource(R.string.campo_area_ha), Modifier.fillMaxWidth())
            if (medindo) {
                MedicaoGps(
                    aoConcluir = { ha -> area = decimal(ha, 2); medindo = false },
                    aoCancelar = { medindo = false }
                )
            } else {
                OutlinedButton(onClick = { medindo = true }, modifier = Modifier.padding(top = 8.dp)) {
                    Icon(Icons.Filled.MyLocation, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.campo_medir_gps))
                }
            }
        }

        FotosParaTreino(fotosGuardadas, colheitas) { fotosGuardadas = it; colheitas = 0 }

        val estimativa = estimaLavoura(pontos, parametros)
        ResultadoCampo(
            estimativa = estimativa,
            areaHa = areaHa,
            preco = preco,
            aoMudarPreco = { preco = it },
            fontePreco = fontePreco,
            referenciaKgHa = referenciaKgHa,
            rotuloReferencia = rotuloReferencia,
        )

        ColheitaDoTalhao(
            estimativa = estimativa,
            areaHa = areaHa,
            colhido = colhido,
            aoMudar = { colhido = it },
            temAlgo = pontos.isNotEmpty() || colhidoSacas != null,
        ) {
            // O talhão que fica para trás continua em talhoes.json, com a colheita.
            pontos.clear()
            area = ""
            colhido = ""
            talhao = novoTalhao()
        }
    }
}

/** O ponto que está sendo amostrado: as duas fotos e as quatro contagens. */
@Composable
private fun NovoPonto(
    numero: Int,
    parametros: ParametrosCampo,
    automatico: Boolean,
    limites: LimitesAutomatico,
    automaticosAntes: Int,
    aoGuardarFotos: () -> Unit,
    aoGuardar: (PontoAmostra) -> Unit,
) {
    val context = LocalContext.current
    val escopo = rememberCoroutineScope()
    var fotoLinha by rememberSaveable { mutableStateOf<String?>(null) }
    var fotoVagens by rememberSaveable { mutableStateOf<String?>(null) }
    val marcasLinha = remember { mutableStateListOf<Offset>() }
    val marcasVagens = remember { mutableStateListOf<Offset>() }
    var plantas by rememberSaveable { mutableStateOf("") }
    var metros by rememberSaveable { mutableStateOf("1") }
    var arrancadas by rememberSaveable { mutableStateOf("5") }
    var vagens by rememberSaveable { mutableStateOf("") }
    // O que o contador automático achou na foto das vagens, e se o produtor
    // já mexeu nas marcas depois disso.
    var automatica by remember { mutableStateOf<ContagemAutomatica?>(null) }
    var conferida by remember { mutableStateOf(false) }
    var qualidade by remember { mutableStateOf<QualidadeFoto?>(null) }

    val ponto = PontoAmostra(
        plantas = plantas.numero()?.toInt() ?: 0,
        metrosDeLinha = metros.numero() ?: 0.0,
        arrancadas = arrancadas.numero()?.toInt() ?: 0,
        vagens = vagens.numero()?.toInt() ?: 0,
    )
    // No modo automático, o número do contador entra sozinho, salvo quando a
    // foto, o número ou a amostragem pedem a conferência do produtor. Se ele
    // mudou o número à mão, a responsabilidade é dele, e não se pede mais nada.
    val contada = automatica
    val motivo = if (automatico && contada != null && !conferida && ponto.vagens == contada.vagens)
        motivoParaConferir(qualidade, contada.vagens, ponto.arrancadas, automaticosAntes, limites) else null

    CartaoCampo(stringResource(R.string.campo_ponto, numero), Icons.Filled.CameraAlt) {
        Text(stringResource(R.string.campo_plantas_na_linha), fontWeight = FontWeight.SemiBold, fontSize = 14.sp,
             color = MaterialTheme.colorScheme.onSurface)
        Nota(stringResource(R.string.campo_plantas_nota))
        FotoParaContar("linha", fotoLinha, { fotoLinha = it; marcasLinha.clear() }, marcasLinha,
                       Color(0xFF16A34A)) { plantas = it.toString() }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
            CampoNumero(plantas, { plantas = it }, stringResource(R.string.campo_plantas), Modifier.weight(1f), inteiro = true)
            CampoNumero(metros, { metros = it }, stringResource(R.string.campo_em_metros), Modifier.weight(1f))
        }

        Spacer(Modifier.height(16.dp))
        Text(stringResource(R.string.campo_vagens_por_planta), fontWeight = FontWeight.SemiBold, fontSize = 14.sp,
             color = MaterialTheme.colorScheme.onSurface)
        Nota(stringResource(if (automatico) R.string.campo_vagens_nota_auto else R.string.campo_vagens_nota))
        FotoParaContar(
            "vagens", fotoVagens,
            { fotoVagens = it; marcasVagens.clear(); automatica = null; conferida = false; qualidade = null },
            marcasVagens, Color(0xFFD97706),
            automatica = automatica,
            conferida = conferida,
            modoAutomatico = automatico,
            aoContarSozinho = { r, q ->
                automatica = r; conferida = false; qualidade = q; vagens = r.vagens.toString()
            },
            // O contador marca só umas 6 em cada 10 vagens, embora estime o total.
            // Antes, o primeiro toque trocava a estimativa pela contagem das
            // marcas, e corrigir uma marca errada derrubava o número em 40%.
            // Agora o número só passa às marcas quando o produtor pede.
            aoUsarMarcas = { conferida = true; vagens = marcasVagens.size.toString() },
        ) {
            if (automatica == null || conferida) vagens = it.toString()
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
            CampoNumero(arrancadas, { arrancadas = it }, stringResource(R.string.campo_plantas_arrancadas), Modifier.weight(1f),
                        inteiro = true)
            CampoNumero(vagens, { vagens = it }, stringResource(R.string.campo_vagens_contadas), Modifier.weight(1f), inteiro = true)
        }

        motivo?.let {
            Text(stringResource(R.string.campo_confira, it.em(context)),
                 fontSize = 13.sp, lineHeight = 18.sp, color = MaterialTheme.colorScheme.error,
                 modifier = Modifier.padding(top = 8.dp))
        }
        if (ponto.valido() && parametros.espacamento > 0) {
            val kg = kgPorHectare(plantasPorM2(ponto, parametros.espacamento), vagensPorPlanta(ponto),
                                  parametros.graosPorVagem, parametros.pesoMilGraos)
            Text(stringResource(R.string.campo_este_ponto, decimal(plantasPorM2(ponto, parametros.espacamento), 1),
                                decimal(vagensPorPlanta(ponto), 1), decimal(kg / 60, 1)),
                 fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface,
                 modifier = Modifier.padding(top = 10.dp))
        }
        Button(
            onClick = {
                aoGuardar(ponto.copy(vagensDoContador = automatica?.vagens, conferido = automatica?.let { conferida }))
                // As fotos marcadas vão para o material de treino da contagem
                // automática. Copia tudo antes de limpar a tela.
                val contexto = mapOf(
                    "metros_de_linha" to ponto.metrosDeLinha,
                    "plantas_arrancadas" to ponto.arrancadas.toDouble(),
                    "espacamento_m" to parametros.espacamento,
                )
                // Marcas só do contador, que o produtor não conferiu, ensinariam
                // o modelo com os próprios erros: essa foto fica de fora.
                val auto = automatica
                val origemVagens = if (auto == null) MarcasDe.PRODUTOR else MarcasDe.CONTADOR_CONFERIDO
                val fotos = listOfNotNull(
                    fotoLinha?.let { Triple(it, "planta", marcasLinha.map { m -> m.x to m.y }) to (ponto.plantas to MarcasDe.PRODUTOR) },
                    fotoVagens?.takeIf { auto == null || conferida }
                        ?.let { Triple(it, "vagem", marcasVagens.map { m -> m.x to m.y }) to (ponto.vagens to origemVagens) },
                ).filter { it.first.third.isNotEmpty() }
                if (fotos.isNotEmpty()) {
                    escopo.launch {
                        withContext(Dispatchers.IO) {
                            for ((foto, contagem) in fotos) {
                                val (informada, origem) = contagem
                                guardaAmostra(context, Uri.parse(foto.first), foto.second, foto.third, informada, contexto,
                                              origem, if (origem == MarcasDe.CONTADOR_CONFERIDO) auto else null)
                            }
                        }
                        aoGuardarFotos()
                    }
                }
                fotoLinha = null; fotoVagens = null
                marcasLinha.clear(); marcasVagens.clear()
                plantas = ""; vagens = ""
                automatica = null; conferida = false; qualidade = null
            },
            enabled = ponto.valido() && motivo == null,
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp)
        ) {
            Text(stringResource(R.string.campo_guardar_ponto))
        }
    }
}

/**
 * Botões de câmera e galeria e, com a foto escolhida, o contador por toque.
 *
 * A câmera é a do próprio celular (ACTION_IMAGE_CAPTURE), que grava num
 * arquivo do cache do app entregue por FileProvider. Assim o app não precisa
 * da permissão de câmera nem de biblioteca de câmera.
 *
 * Com [aoContarSozinho], aparece o botão do contador automático: ele troca as
 * marcas pelas sugeridas e devolve a contagem; [aoContar] continua valendo
 * para cada toque do produtor depois disso.
 */
@Composable
private fun FotoParaContar(
    prefixo: String,
    foto: String?,
    aoTrocarFoto: (String?) -> Unit,
    marcas: SnapshotStateList<Offset>,
    cor: Color,
    automatica: ContagemAutomatica? = null,
    conferida: Boolean = false,
    modoAutomatico: Boolean = false,
    aoContarSozinho: ((ContagemAutomatica, QualidadeFoto?) -> Unit)? = null,
    aoUsarMarcas: (() -> Unit)? = null,
    aoContar: (Int) -> Unit,
) {
    val context = LocalContext.current
    val escopo = rememberCoroutineScope()
    var contando by remember(foto) { mutableStateOf(false) }
    var falhou by remember(foto) { mutableStateOf(false) }
    val fotoAtual by rememberUpdatedState(foto)
    // O Android pode encerrar o app enquanto a câmera está aberta; o endereço
    // da foto pendente precisa sobreviver a isso.
    var pendente by rememberSaveable { mutableStateOf<String?>(null) }
    var aviso by remember { mutableStateOf<String?>(null) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
        if (ok) pendente?.let { aoTrocarFoto(it) }
    }
    val galeria = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        uri?.let { aoTrocarFoto(it.toString()) }
    }

    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
        OutlinedButton(onClick = {
            val pasta = File(context.cacheDir, "fotos").apply { mkdirs() }
            val arquivo = File(pasta, "${prefixo}_${System.currentTimeMillis()}.jpg")
            val uri = FileProvider.getUriForFile(context, context.packageName + ".fotos", arquivo)
            pendente = uri.toString()
            try {
                camera.launch(uri)
            } catch (_: ActivityNotFoundException) {
                aviso = context.getString(R.string.campo_sem_camera)
            }
        }) {
            Icon(Icons.Filled.PhotoCamera, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp))
            Text(stringResource(if (foto == null) R.string.campo_camera else R.string.campo_nova_foto))
        }
        OutlinedButton(onClick = {
            galeria.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        }) {
            Icon(Icons.Filled.PhotoLibrary, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp))
            Text(stringResource(R.string.campo_galeria))
        }
    }
    aviso?.let { Nota(it) }

    if (foto != null) {
        val imagem by produceState<ImageBitmap?>(null, foto) {
            value = withContext(Dispatchers.IO) { carregaFoto(context, Uri.parse(foto))?.asImageBitmap() }
        }
        val img = imagem
        if (img == null) {
            Nota(stringResource(R.string.campo_abrindo_foto))
        } else {
            Spacer(Modifier.height(8.dp))
            if (aoContarSozinho != null) {
                val conta = {
                    contando = true
                    falhou = false
                    val contada = foto
                    escopo.launch {
                        val (r, q) = withContext(Dispatchers.Default) {
                            val bmp = img.asAndroidBitmap()
                            contaVagens(context, bmp) to runCatching { qualidadeDaFoto(bmp) }.getOrNull()
                        }
                        // Se o produtor trocou a foto enquanto contava, o resultado é de outra foto.
                        if (fotoAtual != contada) return@launch
                        contando = false
                        if (r == null) {
                            falhou = true
                        } else {
                            marcas.clear()
                            marcas.addAll(r.marcas.map { (x, y) -> Offset(x, y) })
                            aoContarSozinho(r, q)
                        }
                    }
                }
                // No modo automático, conta assim que a foto abre.
                LaunchedEffect(img) { if (modoAutomatico && automatica == null && !contando) conta() }
                FilledTonalButton(
                    onClick = { conta() },
                    enabled = !contando,
                    modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)
                ) {
                    if (contando) {
                        CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.campo_contando))
                    } else {
                        Icon(Icons.Filled.AutoAwesome, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(when {
                            automatica != null -> R.string.campo_contar_de_novo
                            modoAutomatico -> R.string.campo_contar_sozinho
                            else -> R.string.campo_contar_teste
                        }))
                    }
                }
                if (falhou) Nota(stringResource(R.string.campo_contar_falhou))
            }
            ContadorNaFoto(img, marcas, cor) { aoContar(marcas.size) }
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.campo_marcadas, marcas.size), fontWeight = FontWeight.Bold, fontSize = 14.sp,
                     color = cor, modifier = Modifier.weight(1f))
                TextButton(onClick = { if (marcas.isNotEmpty()) { marcas.removeAt(marcas.lastIndex); aoContar(marcas.size) } },
                           enabled = marcas.isNotEmpty()) { Text(stringResource(R.string.campo_desfazer)) }
                TextButton(onClick = { marcas.clear(); aoContar(0) }, enabled = marcas.isNotEmpty()) {
                    Text(stringResource(R.string.campo_limpar))
                }
            }
            automatica?.let { a ->
                // Um modelo baixado traz a própria frase sobre de onde aprendeu e quanto erra.
                val baixado = remember { modeloBaixado(context)?.takeIf { it.versao > VERSAO_EMBUTIDA } }
                // A nota do modelo baixado vem do anúncio, em português, como foi publicada.
                val origem = baixado?.nota ?: stringResource(R.string.campo_origem_embutido, 6)
                if (!conferida) {
                    Nota(stringResource(if (modoAutomatico) R.string.campo_contou_auto else R.string.campo_contou_teste,
                                        a.vagens, origem))
                    aoUsarMarcas?.let { usar ->
                        OutlinedButton(onClick = usar, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
                            Text(stringResource(R.string.campo_usar_marcas, marcas.size))
                        }
                    }
                } else {
                    Nota(stringResource(R.string.campo_conferida, a.vagens))
                }
                Nota(stringResource(R.string.campo_versao_contador, baixado?.versao ?: VERSAO_EMBUTIDA))
            }
        }
    }
}

/**
 * A foto com as marcas por cima. Toque marca ou desmarca; dois dedos ampliam
 * e, com a foto ampliada, um dedo arrasta. Sem ampliação, arrastar rola a tela
 * normalmente.
 *
 * As marcas ficam em coordenadas da foto (0 a 1), e não da tela, para não
 * saírem do lugar quando a foto é ampliada.
 */
@Composable
private fun ContadorNaFoto(foto: ImageBitmap, marcas: SnapshotStateList<Offset>, cor: Color, aoMudar: () -> Unit) {
    var escala by remember(foto) { mutableFloatStateOf(1f) }
    var desloc by remember(foto) { mutableStateOf(Offset.Zero) }
    val mudou by rememberUpdatedState(aoMudar)
    val densidade = LocalDensity.current
    val raioToque = with(densidade) { 18.dp.toPx() }
    val raioMarca = with(densidade) { 7.dp.toPx() }
    val traco = with(densidade) { 2.5.dp.toPx() }

    Box(
        Modifier
            .fillMaxWidth()
            .aspectRatio(foto.width.toFloat() / foto.height)
            .clipToBounds()
            .pointerInput(foto) {
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false)
                    do {
                        val evento = awaitPointerEvent()
                        if (evento.changes.count { it.pressed } >= 2 || escala > 1f) {
                            val zoom = evento.calculateZoom()
                            val pan = evento.calculatePan()
                            val centro = evento.calculateCentroid(useCurrent = true)
                            val nova = (escala * zoom).coerceIn(1f, 6f)
                            var d = if (centro.isSpecified) centro - (centro - desloc) * (nova / escala) + pan
                                    else desloc + pan
                            val w = size.width.toFloat()
                            val h = size.height.toFloat()
                            d = Offset(d.x.coerceIn(w * (1 - nova), 0f), d.y.coerceIn(h * (1 - nova), 0f))
                            escala = nova
                            desloc = d
                            if (zoom != 1f || pan != Offset.Zero) {
                                evento.changes.forEach { if (it.positionChanged()) it.consume() }
                            }
                        }
                    } while (evento.changes.any { it.pressed })
                }
            }
            .pointerInput(foto) {
                detectTapGestures { toque ->
                    val w = size.width.toFloat()
                    val h = size.height.toFloat()
                    val perto = marcas.indexOfFirst { m ->
                        (Offset(m.x * w * escala + desloc.x, m.y * h * escala + desloc.y) - toque).getDistance() < raioToque
                    }
                    if (perto >= 0) {
                        marcas.removeAt(perto)
                    } else {
                        val c = (toque - desloc) / escala
                        marcas.add(Offset(c.x / w, c.y / h))
                    }
                    mudou()
                }
            }
    ) {
        Image(
            bitmap = foto,
            contentDescription = stringResource(R.string.campo_foto_descricao),
            contentScale = ContentScale.FillBounds,
            modifier = Modifier.fillMaxSize().graphicsLayer {
                scaleX = escala; scaleY = escala
                translationX = desloc.x; translationY = desloc.y
                transformOrigin = TransformOrigin(0f, 0f)
            }
        )
        Canvas(Modifier.fillMaxSize()) {
            marcas.forEach { m ->
                val c = Offset(m.x * size.width * escala + desloc.x, m.y * size.height * escala + desloc.y)
                drawCircle(Color.White, raioMarca + traco, c, style = Stroke(traco))
                drawCircle(cor, raioMarca, c, style = Stroke(traco))
            }
        }
    }
}

/**
 * Lê a foto reduzida a no máximo [maxLado] pixels e de pé: a câmera grava a
 * orientação no EXIF, e o BitmapFactory a ignora. Uma foto de 12 MP inteira
 * ocuparia quase 50 MB de memória só para ser tocada.
 */
internal fun carregaFoto(context: Context, uri: Uri, maxLado: Int = 2048): Bitmap? {
    val cr = context.contentResolver
    return try {
        val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        cr.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, limites) }
        if (limites.outWidth <= 0 || limites.outHeight <= 0) return null
        var amostra = 1
        while (maxOf(limites.outWidth, limites.outHeight) / amostra > maxLado) amostra *= 2
        val bmp = cr.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = amostra })
        } ?: return null
        val orientacao = cr.openInputStream(uri)?.use {
            ExifInterface(it).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
        } ?: ExifInterface.ORIENTATION_NORMAL
        val graus = when (orientacao) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90f
            ExifInterface.ORIENTATION_ROTATE_180 -> 180f
            ExifInterface.ORIENTATION_ROTATE_270 -> 270f
            else -> 0f
        }
        if (graus == 0f) bmp
        else Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, Matrix().apply { postRotate(graus) }, true)
    } catch (_: Exception) {
        null
    } catch (_: OutOfMemoryError) {
        null
    }
}

/**
 * Medição da área andando pelo contorno: o produtor vai a cada canto do
 * talhão, na ordem, e marca. Cantos, e não o trajeto inteiro, porque o GPS do
 * celular parado alguns segundos num ponto erra bem menos que andando.
 */
@SuppressLint("MissingPermission") // a permissão é conferida antes de pedir posições
@Composable
private fun MedicaoGps(aoConcluir: (Double) -> Unit, aoCancelar: () -> Unit) {
    val context = LocalContext.current
    fun temPermissao() = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
        PackageManager.PERMISSION_GRANTED
    var permitido by remember { mutableStateOf(temPermissao()) }
    val pedir = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        permitido = temPermissao()
    }
    var atual by remember { mutableStateOf<Location?>(null) }
    var semGps by remember { mutableStateOf(false) }
    val cantos = remember { mutableStateListOf<Pair<Double, Double>>() }

    if (!permitido) {
        Nota(stringResource(R.string.campo_gps_permissao))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                pedir.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
            }) { Text(stringResource(R.string.campo_permitir_localizacao)) }
            TextButton(onClick = aoCancelar) { Text(stringResource(R.string.campo_cancelar)) }
        }
        return
    }

    DisposableEffect(Unit) {
        val gerente = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        // Objeto com todos os métodos, e não lambda: até o Android 10 a
        // interface não tinha implementação padrão para os demais, e o app
        // fecharia quando o GPS fosse ligado ou desligado.
        val ouvinte = object : LocationListener {
            override fun onLocationChanged(location: Location) { atual = location }
            override fun onProviderEnabled(provider: String) { semGps = false }
            override fun onProviderDisabled(provider: String) { semGps = true }
            @Deprecated("Exigido até o Android 10")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        }
        try {
            semGps = !gerente.isProviderEnabled(LocationManager.GPS_PROVIDER)
            gerente.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000L, 0f, ouvinte, Looper.getMainLooper())
        } catch (_: Exception) {
            semGps = true
        }
        onDispose { gerente.removeUpdates(ouvinte) }
    }

    val loc = atual
    val precisao = loc?.takeIf { it.hasAccuracy() }?.accuracy
    Column(Modifier.padding(top = 8.dp)) {
        Nota(stringResource(R.string.campo_gps_instrucao))
        Text(
            when {
                semGps -> stringResource(R.string.campo_gps_desligado)
                loc == null -> stringResource(R.string.campo_gps_procurando)
                precisao == null -> stringResource(R.string.campo_gps_sem_precisao)
                else -> stringResource(R.string.campo_gps_precisao, precisao.toInt()) +
                        if (precisao > PRECISAO_MAX_M) " " + stringResource(R.string.campo_gps_espere) else ""
            },
            fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface
        )
        Text(stringResource(R.string.campo_cantos, cantos.size) +
             if (cantos.size >= 3) " · " + stringResource(R.string.campo_cantos_area, decimal(areaHectares(cantos), 2)) else "",
             fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
            Button(
                onClick = { loc?.let { cantos.add(it.latitude to it.longitude) } },
                enabled = loc != null && precisao != null && precisao <= PRECISAO_MAX_M
            ) { Text(stringResource(R.string.campo_marcar_canto)) }
            TextButton(onClick = { if (cantos.isNotEmpty()) cantos.removeAt(cantos.lastIndex) },
                       enabled = cantos.isNotEmpty()) { Text(stringResource(R.string.campo_desfazer)) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { aoConcluir(areaHectares(cantos)) }, enabled = cantos.size >= 3) {
                Text(stringResource(R.string.campo_usar_area))
            }
            TextButton(onClick = aoCancelar) { Text(stringResource(R.string.campo_cancelar)) }
        }
    }
}

/**
 * As fotos marcadas guardadas no celular, para treinar a contagem automática.
 * Exportar gera um .zip e abre o compartilhamento do Android: o produtor
 * escolhe para onde mandar (Drive, e-mail, WhatsApp).
 */
@Composable
private fun FotosParaTreino(quantas: Int, colheitas: Int, aoMudar: (Int) -> Unit) {
    val context = LocalContext.current
    val escopo = rememberCoroutineScope()
    var confirmarApagar by remember { mutableStateOf(false) }
    var aviso by remember { mutableStateOf<String?>(null) }

    CartaoCampo(stringResource(R.string.campo_fotos_titulo), Icons.Filled.School) {
        Nota(
            if (quantas == 0) stringResource(R.string.campo_fotos_nenhuma)
            else pluralStringResource(R.plurals.campo_fotos_guardadas, quantas, quantas, decimal(tamanhoAmostrasMb(context), 1))
        )
        if (colheitas > 0) {
            Nota(pluralStringResource(R.plurals.campo_talhoes_colheita, colheitas, colheitas))
        }
        if (quantas > 0 || colheitas > 0) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                Button(onClick = {
                    escopo.launch {
                        val zip = withContext(Dispatchers.IO) { empacotaAmostras(context) }
                        if (zip == null) { aviso = context.getString(R.string.campo_sem_fotos); return@launch }
                        val uri = FileProvider.getUriForFile(context, context.packageName + ".fotos", zip)
                        val envio = Intent(Intent.ACTION_SEND).apply {
                            type = "application/zip"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            putExtra(Intent.EXTRA_SUBJECT, context.getString(R.string.campo_zip_assunto))
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        try {
                            context.startActivity(Intent.createChooser(envio, context.getString(R.string.campo_zip_enviar)))
                        } catch (_: ActivityNotFoundException) {
                            aviso = context.getString(R.string.campo_sem_app_compartilhar)
                        }
                    }
                }) {
                    Icon(Icons.Filled.Share, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(stringResource(R.string.campo_exportar_zip))
                }
                TextButton(onClick = { confirmarApagar = true }) { Text(stringResource(R.string.campo_apagar)) }
            }
        }
        aviso?.let { Nota(it) }
    }

    if (confirmarApagar) {
        AlertDialog(
            onDismissRequest = { confirmarApagar = false },
            title = { Text(stringResource(R.string.campo_apagar_titulo)) },
            text = { Text(stringResource(R.string.campo_apagar_texto)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmarApagar = false
                    escopo.launch {
                        withContext(Dispatchers.IO) { apagaAmostras(context) }
                        aoMudar(0)
                    }
                }) { Text(stringResource(R.string.campo_apagar)) }
            },
            dismissButton = { TextButton(onClick = { confirmarApagar = false }) { Text(stringResource(R.string.campo_cancelar)) } }
        )
    }
}

/**
 * O que saiu do talhão, pelo romaneio, comparado com a estimativa no pé. É o
 * único jeito de saber quanto a estimativa (e o contador) erram na lavoura.
 */
@Composable
private fun ColheitaDoTalhao(
    estimativa: Estimativa?,
    areaHa: Double?,
    colhido: String,
    aoMudar: (String) -> Unit,
    temAlgo: Boolean,
    aoNovoTalhao: () -> Unit,
) {
    var confirmar by remember { mutableStateOf(false) }
    CartaoCampo(stringResource(R.string.campo_depois_colheita), Icons.Filled.CheckCircle) {
        Nota(stringResource(R.string.campo_colheita_nota))
        CampoNumero(colhido, aoMudar, stringResource(R.string.campo_colhido), Modifier.fillMaxWidth().padding(top = 4.dp))
        val kg = colheitaKgHa(colhido.numero(), areaHa)
        when {
            colhido.numero() == null -> {}
            areaHa == null -> Nota(stringResource(R.string.campo_informe_area))
            kg != null -> {
                Text(stringResource(R.string.campo_colheita_sc, decimal(kg / 60, 1)), fontSize = 16.sp, fontWeight = FontWeight.SemiBold,
                     color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.padding(top = 8.dp))
                // 3.456 digitado como milhar vira três sacas e meia: o número absurdo avisa.
                if (kg / 60 < 5 || kg / 60 > 150) {
                    Nota(stringResource(R.string.campo_confira_numero, decimal(kg / 60, 1)))
                }
                if (estimativa != null) {
                    val dif = (estimativa.kgHa / kg - 1) * 100
                    Nota(stringResource(if (dif >= 0) R.string.campo_estimativa_acima else R.string.campo_estimativa_abaixo,
                                        decimal(estimativa.scHa, 1), decimal(kotlin.math.abs(dif), 0)))
                }
            }
        }
        if (temAlgo) {
            OutlinedButton(onClick = { confirmar = true }, modifier = Modifier.padding(top = 8.dp)) {
                Text(stringResource(R.string.campo_outro_talhao))
            }
        }
    }
    if (confirmar) {
        AlertDialog(
            onDismissRequest = { confirmar = false },
            title = { Text(stringResource(R.string.campo_outro_talhao_titulo)) },
            text = { Text(stringResource(R.string.campo_outro_talhao_texto)) },
            confirmButton = {
                TextButton(onClick = { confirmar = false; aoNovoTalhao() }) { Text(stringResource(R.string.campo_comecar)) }
            },
            dismissButton = { TextButton(onClick = { confirmar = false }) { Text(stringResource(R.string.campo_cancelar)) } }
        )
    }
}

@Composable
private fun ResultadoCampo(
    estimativa: Estimativa?,
    areaHa: Double?,
    preco: String,
    aoMudarPreco: (String) -> Unit,
    fontePreco: String?,
    referenciaKgHa: Double?,
    rotuloReferencia: String?,
) {
    CartaoCampo(stringResource(R.string.campo_sua_lavoura), Icons.Filled.Agriculture) {
        if (estimativa == null) {
            Nota(stringResource(R.string.campo_guarde_ponto))
            return@CartaoCampo
        }
        Text(stringResource(R.string.campo_sc_ha, decimal(estimativa.scHa, 1)), fontSize = 28.sp, fontWeight = FontWeight.Bold,
             color = MaterialTheme.colorScheme.primary)
        Text(stringResource(R.string.campo_resultado_detalhe, milhar(estimativa.kgHa), decimal(estimativa.plantasPorM2, 1),
                            decimal(estimativa.vagensPorPlanta, 1)),
             fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface)
        Text(
            if (estimativa.pontos == 1) stringResource(R.string.campo_um_ponto)
            else stringResource(R.string.campo_media_pontos, estimativa.pontos, decimal(estimativa.kgHaMin / 60, 1),
                                decimal(estimativa.kgHaMax / 60, 1)),
            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        val valorPreco = preco.numero()?.takeIf { it > 0 }
        Spacer(Modifier.height(10.dp))
        CampoNumero(preco, aoMudarPreco, stringResource(R.string.campo_preco_saca), Modifier.fillMaxWidth())
        if (fontePreco != null) Nota(fontePreco)

        Spacer(Modifier.height(8.dp))
        if (areaHa != null) {
            val sacas = estimativa.scHa * areaHa
            Text(stringResource(R.string.campo_sacas_em, milhar(sacas), decimal(areaHa, 2)), fontSize = 16.sp,
                 fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
            if (valorPreco != null) {
                // Total sem centavos: a estimativa não tem essa precisão.
                Text(stringResource(R.string.campo_total_talhao, milhar(sacas * valorPreco), reais(estimativa.scHa * valorPreco)),
                     fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
            }
        } else if (valorPreco != null) {
            Text(stringResource(R.string.campo_por_hectare, reais(estimativa.scHa * valorPreco)),
                 fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
        }

        if (referenciaKgHa != null && referenciaKgHa > 0 && rotuloReferencia != null) {
            val dif = (estimativa.kgHa / referenciaKgHa - 1) * 100
            Spacer(Modifier.height(8.dp))
            Text(stringResource(if (dif >= 0) R.string.campo_modelo_acima else R.string.campo_modelo_abaixo,
                                rotuloReferencia, decimal(referenciaKgHa / 60, 1), decimal(kotlin.math.abs(dif), 0)),
                 fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp)
        }
        Spacer(Modifier.height(8.dp))
        Nota(stringResource(R.string.campo_nota_final))
    }
}

@Composable
private fun CartaoCampo(titulo: String, icone: androidx.compose.ui.graphics.vector.ImageVector, conteudo: @Composable ColumnScope.() -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 8.dp)) {
                Icon(icone, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text(titulo, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
            }
            conteudo()
        }
    }
}

@Composable
private fun Nota(texto: String) {
    Text(texto, fontSize = 12.sp, lineHeight = 16.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
         modifier = Modifier.padding(top = 4.dp))
}

@Composable
private fun CampoNumero(valor: String, aoMudar: (String) -> Unit, rotulo: String, modifier: Modifier, inteiro: Boolean = false) {
    val isDark = isSystemInDarkTheme()
    OutlinedTextField(
        value = valor,
        onValueChange = aoMudar,
        label = { Text(rotulo, fontSize = 12.sp) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = if (inteiro) KeyboardType.Number else KeyboardType.Decimal),
        modifier = modifier,
        colors = OutlinedTextFieldDefaults.colors(
            focusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9),
            unfocusedContainerColor = if (isDark) Color(0xFF161b22) else Color(0xFFF1F5F9)
        )
    )
}
