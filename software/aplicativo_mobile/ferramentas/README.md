# Ferramentas de manutenção do aplicativo

Sobras de edições pontuais em `MainActivity.kt`, guardadas como registro. Todas
já foram aplicadas e **não devem ser executadas de novo**: as duas `.sh`
substituem linhas por número, e o arquivo mudou desde então; rodá-las hoje
corromperia o código.

| arquivo | o que fez |
|---|---|
| `fix_brace.sh` | trocou a linha 212 por dois fechamentos de chave que faltavam |
| `fix_hist.sh` | reescreveu o cabeçalho "Histórico Completo" (linhas 232 a 238) com ícone e espaçamento |
| `update_report.txt` | saída de uma execução de `gradle dependencyUpdates` que falhou; não é lida por nada |

## Os três `patch_*.py` na pasta acima

`patch_offline_flag.py`, `patch_system_bars.py` e `patch_theme.py` são do mesmo
tipo, mas ficam em `software/aplicativo_mobile/`: constam da tabela de hashes do
commit depositado no INPI (`REGISTRO_INPI.md`, seção 9.3, linhas 22 a 24), e
movê-los mudaria o caminho registrado. Também já foram aplicados.
`patch_offline_flag.py` e `patch_system_bars.py`, reexecutados, não alteram nada.
`patch_theme.py`, sim: algumas das cores que ele substitui continuam no arquivo,
e uma segunda execução as envolveria de novo num `if (isDark)`, alterando 18
linhas. Não deve ser rodado.

| arquivo | o que fez |
|---|---|
| `patch_offline_flag.py` | o aplicativo deixa de abrir em modo offline por padrão; o modo passa a ser ligado só quando a chamada à API falha e desligado quando ela responde |
| `patch_system_bars.py` | pinta a barra de status e a de navegação com as cores do tema, claro ou escuro |
| `patch_theme.py` | troca o tema escuro fixo por um que segue o sistema, com variantes claras das cores de alta e baixa |

Os três operam sobre `app/src/main/java/com/agrointeligencia/app/MainActivity.kt`
por substituição de texto, a partir de `software/aplicativo_mobile/`.
