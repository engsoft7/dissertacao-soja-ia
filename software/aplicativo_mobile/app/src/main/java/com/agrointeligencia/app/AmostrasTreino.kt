package com.agrointeligencia.app

import android.content.Context
import java.io.File

// FOTOS MARCADAS PARA TREINO: SAÍRAM DO APP NO 2.10.1.
//
// Até o 2.10.0, cada foto em que o produtor marcava plantas ou vagens na
// Estimativa no campo ficava guardada no celular, com as marcas e o talhão
// (talhoes.json), para ele exportar num .zip e ajudar a treinar a contagem
// automática. A função servia a quem desenvolve o contador, e não ao
// produtor, e saiu do app: as fotos e as marcas servem só à conta da tela.
//
// Ficam aqui a limpeza do que aquelas versões deixaram no celular e a conta
// da colheita, que a comparação entre colheita e estimativa usa.

/** A pasta interna em que as versões até o 2.10.0 guardavam as fotos marcadas e o talhoes.json. */
private const val PASTA_ANTIGA = "amostras_treino"

/** O .zip que as versões até o 2.10.0 montavam no cache para compartilhar. */
private val ZIP_ANTIGO = Regex("""fotos_marcadas_.*\.zip""")

/**
 * Apaga as fotos marcadas, as marcas, o talhoes.json e os .zip de exportação
 * que as versões até o 2.10.0 deixaram no celular. Os outros arquivos da
 * pasta de exportação (caderno e relatório) ficam. Devolve quantos arquivos
 * apagou; sem nada da época, não faz nada. Roda fora da thread principal.
 */
internal fun apagaAmostrasAntigas(context: Context): Int {
    var apagados = 0
    val pasta = File(context.filesDir, PASTA_ANTIGA)
    if (pasta.exists()) {
        apagados += pasta.walk().count { it.isFile }
        pasta.deleteRecursively()
    }
    File(context.cacheDir, "exportar").listFiles()
        ?.filter { it.isFile && ZIP_ANTIGO.matches(it.name) }
        ?.forEach { if (it.delete()) apagados++ }
    return apagados
}

/** Produtividade colhida, em kg/ha: as sacas de 60 kg sobre a área. */
internal fun colheitaKgHa(sacas: Double?, areaHa: Double?): Double? =
    if (sacas == null || areaHa == null || sacas <= 0 || areaHa <= 0) null else sacas * 60.0 / areaHa
