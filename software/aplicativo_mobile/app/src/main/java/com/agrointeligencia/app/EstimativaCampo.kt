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
import java.util.Locale

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
// conferência, não vai para o material de treino.

private const val PREF_CAMPO = "estimativa_campo"
// Precisão mínima para aceitar um canto do talhão. Com 20 m de erro em cada
// canto, um talhão de 10 ha já erra a área em mais de 10%.
private const val PRECISAO_MAX_M = 20f
private val BR: Locale = Locale.forLanguageTag("pt-BR")

/** O que a tela guarda entre uma abertura e outra do aplicativo. */
data class EstadoCampo(
    val pontos: List<PontoAmostra> = emptyList(),
    val parametros: ParametrosCampo = ParametrosCampo(),
    val areaHa: Double? = null,
)

private fun String.numero(): Double? = trim().replace(',', '.').toDoubleOrNull()

private fun decimal(v: Double, casas: Int = 1): String = String.format(BR, "%,.${casas}f", v)

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

    val parametros = ParametrosCampo(espacamento.numero() ?: 0.0, graos.numero() ?: 0.0, pesoMil.numero() ?: 0.0)
    val areaHa = area.numero()?.takeIf { it > 0 }

    // Guarda a cada mudança: contar trinta vagens e perder ao fechar o app é defeito.
    LaunchedEffect(pontos.toList(), parametros, areaHa) {
        if (inicial == null) gravarEstado(context, EstadoCampo(pontos.toList(), parametros, areaHa))
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
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Voltar ao Resumo")
            }
            Text("Estimativa no campo", fontSize = 20.sp, fontWeight = FontWeight.SemiBold,
                 color = MaterialTheme.colorScheme.onBackground)
        }
        Text(
            "Conte plantas e vagens em alguns pontos do talhão e o app calcula a produtividade " +
            "da sua lavoura, em sacas e em reais. Faça de 5 a 10 pontos espalhados, longe das bordas, " +
            "a partir do enchimento de grãos (R5–R6), quando as vagens já estão formadas.",
            fontSize = 13.sp, lineHeight = 18.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        var fotosGuardadas by remember { mutableIntStateOf(0) }
        LaunchedEffect(Unit) { fotosGuardadas = withContext(Dispatchers.IO) { contaAmostras(context) } }

        NovoPonto(
            numero = pontos.size + 1,
            parametros = parametros,
            aoGuardarFotos = { fotosGuardadas = contaAmostras(context) },
        ) { pontos.add(it) }

        if (pontos.isNotEmpty()) {
            CartaoCampo("Pontos guardados", Icons.Filled.DoneAll) {
                pontos.forEachIndexed { i, p ->
                    val kg = if (p.valido() && parametros.espacamento > 0)
                        kgPorHectare(plantasPorM2(p, parametros.espacamento), vagensPorPlanta(p),
                                     parametros.graosPorVagem, parametros.pesoMilGraos) else null
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.weight(1f)) {
                            Text("Ponto ${i + 1}" + (kg?.let { ": ${decimal(it / 60, 1)} sc/ha" } ?: ""),
                                 fontSize = 14.sp, fontWeight = FontWeight.SemiBold,
                                 color = MaterialTheme.colorScheme.onSurface)
                            Text("${p.plantas} plantas em ${decimal(p.metrosDeLinha, 1)} m · " +
                                 "${p.vagens} vagens em ${p.arrancadas} plantas",
                                 fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        IconButton(onClick = { pontos.removeAt(i) }) {
                            Icon(Icons.Filled.Delete, contentDescription = "Apagar o ponto ${i + 1}",
                                 tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }

        CartaoCampo("Cultivar e espaçamento", Icons.Filled.Tune) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CampoNumero(espacamento, { espacamento = it }, "Entre linhas", Modifier.weight(1f))
                CampoNumero(graos, { graos = it }, "Grãos/vagem", Modifier.weight(1f))
                CampoNumero(pesoMil, { pesoMil = it }, "Mil grãos (g)", Modifier.weight(1f), inteiro = true)
            }
            Nota("Espaçamento entre linhas em metros (0,45 = 45 cm). " +
                 "Grãos por vagem e peso de mil grãos mudam com a cultivar e com o ano. Os valores " +
                 "iniciais são típicos; se você conhece os da sua cultivar, use os seus.")
        }

        CartaoCampo("Área do talhão", Icons.Filled.Straighten) {
            var medindo by rememberSaveable { mutableStateOf(false) }
            CampoNumero(area, { area = it }, "Área (ha)", Modifier.fillMaxWidth())
            if (medindo) {
                MedicaoGps(
                    aoConcluir = { ha -> area = decimal(ha, 2); medindo = false },
                    aoCancelar = { medindo = false }
                )
            } else {
                OutlinedButton(onClick = { medindo = true }, modifier = Modifier.padding(top = 8.dp)) {
                    Icon(Icons.Filled.MyLocation, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Medir andando com o GPS")
                }
            }
        }

        FotosParaTreino(fotosGuardadas) { fotosGuardadas = it }

        ResultadoCampo(
            estimativa = estimaLavoura(pontos, parametros),
            areaHa = areaHa,
            preco = preco,
            aoMudarPreco = { preco = it },
            fontePreco = fontePreco,
            referenciaKgHa = referenciaKgHa,
            rotuloReferencia = rotuloReferencia,
        )
    }
}

/** O ponto que está sendo amostrado: as duas fotos e as quatro contagens. */
@Composable
private fun NovoPonto(
    numero: Int,
    parametros: ParametrosCampo,
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

    val ponto = PontoAmostra(
        plantas = plantas.numero()?.toInt() ?: 0,
        metrosDeLinha = metros.numero() ?: 0.0,
        arrancadas = arrancadas.numero()?.toInt() ?: 0,
        vagens = vagens.numero()?.toInt() ?: 0,
    )

    CartaoCampo("Ponto $numero", Icons.Filled.CameraAlt) {
        Text("1. Plantas na linha", fontWeight = FontWeight.SemiBold, fontSize = 14.sp,
             color = MaterialTheme.colorScheme.onSurface)
        Nota("Estique uma trena ao lado de uma linha e fotografe de cima. Toque em cada planta " +
             "para marcar; toque de novo para desmarcar.")
        FotoParaContar("linha", fotoLinha, { fotoLinha = it; marcasLinha.clear() }, marcasLinha,
                       Color(0xFF16A34A)) { plantas = it.toString() }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
            CampoNumero(plantas, { plantas = it }, "Plantas", Modifier.weight(1f), inteiro = true)
            CampoNumero(metros, { metros = it }, "Em quantos metros", Modifier.weight(1f))
        }

        Spacer(Modifier.height(16.dp))
        Text("2. Vagens por planta", fontWeight = FontWeight.SemiBold, fontSize = 14.sp,
             color = MaterialTheme.colorScheme.onSurface)
        Nota("Arranque algumas plantas seguidas da mesma linha, deite sobre um pano escuro, " +
             "sem sobrepor, e fotografe de cima. Toque em cada vagem com grão, ou use Contar sozinho " +
             "e confira; dois dedos ampliam a foto.")
        FotoParaContar(
            "vagens", fotoVagens,
            { fotoVagens = it; marcasVagens.clear(); automatica = null; conferida = false },
            marcasVagens, Color(0xFFD97706),
            automatica = automatica,
            conferida = conferida,
            aoContarSozinho = { r -> automatica = r; conferida = false; vagens = r.vagens.toString() },
        ) {
            vagens = it.toString()
            if (automatica != null) conferida = true
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
            CampoNumero(arrancadas, { arrancadas = it }, "Plantas arrancadas", Modifier.weight(1f), inteiro = true)
            CampoNumero(vagens, { vagens = it }, "Vagens contadas", Modifier.weight(1f), inteiro = true)
        }

        if (ponto.valido() && parametros.espacamento > 0) {
            val kg = kgPorHectare(plantasPorM2(ponto, parametros.espacamento), vagensPorPlanta(ponto),
                                  parametros.graosPorVagem, parametros.pesoMilGraos)
            Text("Este ponto: ${decimal(plantasPorM2(ponto, parametros.espacamento), 1)} plantas/m², " +
                 "${decimal(vagensPorPlanta(ponto), 1)} vagens/planta, ${decimal(kg / 60, 1)} sc/ha",
                 fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface,
                 modifier = Modifier.padding(top = 10.dp))
        }
        Button(
            onClick = {
                aoGuardar(ponto)
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
                automatica = null; conferida = false
            },
            enabled = ponto.valido(),
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp)
        ) {
            Text("Guardar ponto e amostrar outro")
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
    aoContarSozinho: ((ContagemAutomatica) -> Unit)? = null,
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
                aviso = "Este celular não tem aplicativo de câmera disponível. Use a galeria."
            }
        }) {
            Icon(Icons.Filled.PhotoCamera, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp))
            Text(if (foto == null) "Câmera" else "Nova foto")
        }
        OutlinedButton(onClick = {
            galeria.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        }) {
            Icon(Icons.Filled.PhotoLibrary, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp))
            Text("Galeria")
        }
    }
    aviso?.let { Nota(it) }

    if (foto != null) {
        val imagem by produceState<ImageBitmap?>(null, foto) {
            value = withContext(Dispatchers.IO) { carregaFoto(context, Uri.parse(foto))?.asImageBitmap() }
        }
        val img = imagem
        if (img == null) {
            Nota("Abrindo a foto…")
        } else {
            Spacer(Modifier.height(8.dp))
            if (aoContarSozinho != null) {
                FilledTonalButton(
                    onClick = {
                        contando = true
                        falhou = false
                        val contada = foto
                        escopo.launch {
                            val r = withContext(Dispatchers.Default) { contaVagens(context, img.asAndroidBitmap()) }
                            // Se o produtor trocou a foto enquanto contava, o resultado é de outra foto.
                            if (fotoAtual != contada) return@launch
                            contando = false
                            if (r == null) {
                                falhou = true
                            } else {
                                marcas.clear()
                                marcas.addAll(r.marcas.map { (x, y) -> Offset(x, y) })
                                aoContarSozinho(r)
                            }
                        }
                    },
                    enabled = !contando,
                    modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)
                ) {
                    if (contando) {
                        CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Contando…")
                    } else {
                        Icon(Icons.Filled.AutoAwesome, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(if (automatica == null) "Contar sozinho (teste)" else "Contar sozinho de novo")
                    }
                }
                if (falhou) Nota("Não foi possível contar sozinho neste celular. Conte tocando nas vagens.")
            }
            ContadorNaFoto(img, marcas, cor) { aoContar(marcas.size) }
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Text("${marcas.size} marcadas", fontWeight = FontWeight.Bold, fontSize = 14.sp,
                     color = cor, modifier = Modifier.weight(1f))
                TextButton(onClick = { if (marcas.isNotEmpty()) { marcas.removeAt(marcas.lastIndex); aoContar(marcas.size) } },
                           enabled = marcas.isNotEmpty()) { Text("Desfazer") }
                TextButton(onClick = { marcas.clear(); aoContar(0) }, enabled = marcas.isNotEmpty()) { Text("Limpar") }
            }
            automatica?.let { a ->
                // Um modelo baixado traz a própria frase sobre de onde aprendeu e quanto erra.
                val baixado = remember { modeloBaixado(context)?.takeIf { it.versao > VERSAO_EMBUTIDA } }
                val origem = baixado?.nota
                    ?: ("Ele aprendeu com fotos de plantas da China, onde erra em média 6%, e ainda não foi " +
                        "conferido em lavouras do Pará.")
                Nota(
                    if (!conferida)
                        "O contador estimou ${a.vagens} vagens e marcou ${a.marcas.size} onde as viu. $origem " +
                        "Confira: toque nas vagens sem marca e nas marcas erradas. " +
                        "A partir do primeiro toque, vale a contagem das marcas."
                    else
                        "Contagem conferida por você, a partir das marcas do contador (que estimou ${a.vagens})."
                )
                Nota("Contador versão ${baixado?.versao ?: VERSAO_EMBUTIDA}, treinado com a base YOLO POD " +
                     "(Xiang et al., 2023, Plant Methods), licença CC BY 4.0.")
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
            contentDescription = "Foto para contar; toque para marcar",
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
        Nota("Para medir a área o app precisa da sua localização precisa, só enquanto esta tela está aberta.")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                pedir.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
            }) { Text("Permitir localização") }
            TextButton(onClick = aoCancelar) { Text("Cancelar") }
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
        Nota("Vá até cada canto do talhão, na ordem do contorno, espere o sinal firmar e marque.")
        Text(
            when {
                semGps -> "O GPS está desligado. Ligue a localização do celular."
                loc == null -> "Procurando o GPS… a céu aberto leva alguns segundos."
                precisao == null -> "GPS sem estimativa de precisão."
                else -> "Precisão agora: ±${precisao.toInt()} m" +
                        if (precisao > PRECISAO_MAX_M) " (espere melhorar)" else ""
            },
            fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface
        )
        Text("Cantos marcados: ${cantos.size}" +
             if (cantos.size >= 3) " · área ${decimal(areaHectares(cantos), 2)} ha" else "",
             fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
            Button(
                onClick = { loc?.let { cantos.add(it.latitude to it.longitude) } },
                enabled = loc != null && precisao != null && precisao <= PRECISAO_MAX_M
            ) { Text("Marcar canto") }
            TextButton(onClick = { if (cantos.isNotEmpty()) cantos.removeAt(cantos.lastIndex) },
                       enabled = cantos.isNotEmpty()) { Text("Desfazer") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { aoConcluir(areaHectares(cantos)) }, enabled = cantos.size >= 3) { Text("Usar esta área") }
            TextButton(onClick = aoCancelar) { Text("Cancelar") }
        }
    }
}

/**
 * As fotos marcadas guardadas no celular, para treinar a contagem automática.
 * Exportar gera um .zip e abre o compartilhamento do Android: o produtor
 * escolhe para onde mandar (Drive, e-mail, WhatsApp).
 */
@Composable
private fun FotosParaTreino(quantas: Int, aoMudar: (Int) -> Unit) {
    val context = LocalContext.current
    val escopo = rememberCoroutineScope()
    var confirmarApagar by remember { mutableStateOf(false) }
    var aviso by remember { mutableStateOf<String?>(null) }

    CartaoCampo("Fotos para treinar a contagem automática", Icons.Filled.School) {
        Nota(
            if (quantas == 0)
                "Cada foto em que você marca plantas ou vagens fica guardada no celular, com as marcações, " +
                "quando você guarda o ponto. Elas servem para treinar um modelo que conte sozinho. " +
                "Marque todas as plantas ou vagens da foto, não só algumas."
            else
                "$quantas ${if (quantas == 1) "foto marcada guardada" else "fotos marcadas guardadas"} " +
                "no celular (${decimal(tamanhoAmostrasMb(context), 1)} MB). Ficam só aqui até você exportar."
        )
        if (quantas > 0) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                Button(onClick = {
                    escopo.launch {
                        val zip = withContext(Dispatchers.IO) { empacotaAmostras(context) }
                        if (zip == null) { aviso = "Não há fotos para exportar."; return@launch }
                        val uri = FileProvider.getUriForFile(context, context.packageName + ".fotos", zip)
                        val envio = Intent(Intent.ACTION_SEND).apply {
                            type = "application/zip"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            putExtra(Intent.EXTRA_SUBJECT, "Fotos marcadas de soja (AgroInteligência)")
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        try {
                            context.startActivity(Intent.createChooser(envio, "Enviar as fotos marcadas"))
                        } catch (_: ActivityNotFoundException) {
                            aviso = "Nenhum aplicativo para compartilhar o arquivo."
                        }
                    }
                }) {
                    Icon(Icons.Filled.Share, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Exportar (.zip)")
                }
                TextButton(onClick = { confirmarApagar = true }) { Text("Apagar") }
            }
        }
        aviso?.let { Nota(it) }
    }

    if (confirmarApagar) {
        AlertDialog(
            onDismissRequest = { confirmarApagar = false },
            title = { Text("Apagar as fotos marcadas?") },
            text = { Text("As $quantas fotos e as marcações saem do celular. Exporte antes se quiser guardá-las.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmarApagar = false
                    escopo.launch {
                        withContext(Dispatchers.IO) { apagaAmostras(context) }
                        aoMudar(0)
                    }
                }) { Text("Apagar") }
            },
            dismissButton = { TextButton(onClick = { confirmarApagar = false }) { Text("Cancelar") } }
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
    CartaoCampo("Sua lavoura", Icons.Filled.Agriculture) {
        if (estimativa == null) {
            Nota("Guarde ao menos um ponto, com plantas e vagens, para ver a estimativa.")
            return@CartaoCampo
        }
        Text("${decimal(estimativa.scHa, 1)} sc/ha", fontSize = 28.sp, fontWeight = FontWeight.Bold,
             color = MaterialTheme.colorScheme.primary)
        Text("${milhar(estimativa.kgHa)} kg/ha · ${decimal(estimativa.plantasPorM2, 1)} plantas/m² · " +
             "${decimal(estimativa.vagensPorPlanta, 1)} vagens/planta",
             fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface)
        val pontos = if (estimativa.pontos == 1) "1 ponto" else "${estimativa.pontos} pontos"
        Text(
            if (estimativa.pontos == 1) "Com $pontos só. Amostre mais pontos para a média valer para o talhão."
            else "Média de $pontos, que variaram de ${decimal(estimativa.kgHaMin / 60, 1)} a " +
                 "${decimal(estimativa.kgHaMax / 60, 1)} sc/ha.",
            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        val valorPreco = preco.numero()?.takeIf { it > 0 }
        Spacer(Modifier.height(10.dp))
        CampoNumero(preco, aoMudarPreco, "Preço da saca (R$)", Modifier.fillMaxWidth())
        if (fontePreco != null) Nota(fontePreco)

        Spacer(Modifier.height(8.dp))
        if (areaHa != null) {
            val sacas = estimativa.scHa * areaHa
            Text("${milhar(sacas)} sacas em ${decimal(areaHa, 2)} ha", fontSize = 16.sp,
                 fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
            if (valorPreco != null) {
                // Total sem centavos: a estimativa não tem essa precisão.
                Text("R$ ${milhar(sacas * valorPreco)} no talhão · R$ ${reais(estimativa.scHa * valorPreco)}/ha",
                     fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
            }
        } else if (valorPreco != null) {
            Text("R$ ${reais(estimativa.scHa * valorPreco)} por hectare. Informe a área para ver o total.",
                 fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
        }

        if (referenciaKgHa != null && referenciaKgHa > 0 && rotuloReferencia != null) {
            val dif = (estimativa.kgHa / referenciaKgHa - 1) * 100
            Spacer(Modifier.height(8.dp))
            Text("Modelo do app para $rotuloReferencia: ${decimal(referenciaKgHa / 60, 1)} sc/ha, média do " +
                 "município. Sua lavoura está ${decimal(kotlin.math.abs(dif), 0)}% " +
                 (if (dif >= 0) "acima." else "abaixo."),
                 fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 16.sp)
        }
        Spacer(Modifier.height(8.dp))
        Nota("É o que a lavoura tem no pé, antes das perdas na colheita e com o peso de grão informado. " +
             "A precisão depende de quantos pontos e de quão bem eles representam o talhão.")
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
