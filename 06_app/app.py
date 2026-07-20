with st.expander("Sobre este painel"):
    st.markdown(
        """
Produto técnico da dissertação **Aplicação da Inteligência Artificial na
Previsão da Produtividade da Soja** — Mestrado Profissional em Computação
Aplicada (PPCA/UFPA, Campus de Tucuruí).

**Autor:** Maycon Lima dos Santos · **Orientador:** Prof. Dr. Caio Carvalho
Moreira · **Ano:** 2026

**Metodologia, em resumo:** a estimativa combina a média histórica do município
e a tendência tecnológica com uma correção climática aprendida por rede neural
(MLP) sobre NDVI/EVI (MODIS), chuva (CHIRPS) e clima (ERA5-Land), restritos à
área de soja da máscara anual do MapBiomas. A validação é temporal
(*leave-one-year-out*) e a margem de erro exibida é o RMSE dessa validação.
Detalhes na seção 6 da dissertação.

**Código e dados:** [github.com/engsoft7/dissertacao-soja-ia](https://github.com/engsoft7/dissertacao-soja-ia)
· DOI [10.5281/zenodo.21286115](https://doi.org/10.5281/zenodo.21286115)

**Como citar:** SANTOS, Maycon Lima dos. *Aplicação da Inteligência Artificial
na Previsão da Produtividade da Soja: códigos e dados*. Zenodo, 2026.
DOI: 10.5281/zenodo.21286115.
"""
    )

st.caption(
    "Código e dados: https://github.com/engsoft7/dissertacao-soja-ia · "
    "Este painel não substitui levantamentos de campo."
)
