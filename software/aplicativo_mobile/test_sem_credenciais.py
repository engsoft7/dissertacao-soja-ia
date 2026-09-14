# -*- coding: utf-8 -*-
"""
A configuração de assinatura não pode voltar a trazer credencial literal.

Existe porque já trouxe. Entre 23/07/2026 e 19/08/2026 o build.gradle.kts
carregou a senha da chave de assinatura escrita no próprio arquivo, e o
repositório é público: a remoção posterior tirou-a do estado atual, mas o
histórico do git é imutável e ela segue legível em três commits e nas árvores
das tags v2.1.0 e v2.1.1.

O arquivo .jks nunca foi versionado, e é só por isso que o estrago ficou
contido — senha sem o arquivo não assina nada. Mas a margem encolheu, e a lição
que vale guardar em código é a de que segredo não se escreve em arquivo
versionado, nem "temporariamente".

Este teste falha se alguém reescrever a assinatura com literal em vez de ler de
keystore.properties, que é ignorado pelo git.
"""
import os
import re

RAIZ = os.path.dirname(os.path.abspath(__file__))
GRADLE = os.path.join(RAIZ, 'app', 'build.gradle.kts')

# Cada campo sensível só pode ser atribuído a partir do arquivo de propriedades.
CAMPOS = ('storePassword', 'keyPassword', 'keyAlias', 'storeFile')


def _linhas_de_atribuicao():
    with open(GRADLE, encoding='utf-8') as f:
        for n, linha in enumerate(f, 1):
            sem_comentario = linha.split('//')[0]
            for campo in CAMPOS:
                if re.search(rf'\b{campo}\s*=', sem_comentario):
                    yield n, campo, sem_comentario.strip()


def test_assinatura_nao_traz_credencial_literal():
    ofensas = []
    for n, campo, linha in _linhas_de_atribuicao():
        # Aceita ler de keystoreProps; recusa qualquer literal entre aspas que
        # não seja o valor-padrão do caminho do keystore.
        if 'keystoreProps.getProperty' in linha:
            continue
        literais = re.findall(r'"([^"]*)"', linha)
        suspeitos = [v for v in literais if v and not v.endswith('.jks')]
        if suspeitos:
            ofensas.append(f'linha {n}: {campo} = {suspeitos}')
    assert not ofensas, (
        'credencial literal em build.gradle.kts — leia de keystore.properties, '
        'que o .gitignore cobre:\n  ' + '\n  '.join(ofensas))


def test_keystore_continua_fora_do_versionamento():
    with open(os.path.join(RAIZ, '..', '..', '.gitignore'), encoding='utf-8') as f:
        ignorados = f.read()
    for padrao in ('keystore.properties', '*.jks'):
        assert padrao in ignorados, f'{padrao} saiu do .gitignore'
