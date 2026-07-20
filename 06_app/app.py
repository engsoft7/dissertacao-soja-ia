# ---------------------------------------------------------
    # SÉRIE HISTÓRICA E GRÁFICOS (COM TENDÊNCIA E CLIMA)
    # ---------------------------------------------------------
    st.subheader("Produtividade observada (PAM/IBGE)")
    
    serie_plot = serie.assign(
        produtividade=serie[M.ALVO] * fator,
        produtividade_rotulo=[qtd(v) for v in serie[M.ALVO]],
        area_rotulo=[br(a) for a in serie["soy_area_ha"]],
        repetido=serie.groupby("municipio")[M.ALVO].diff().eq(0).fillna(False),
        Nome=[disp(m) for m in serie["municipio"]]
    )

    # CORREÇÃO PARA O CELULAR: Eixo X como Quantitativo (Q) e formato de ano sem vírgula (format="d")
    eixo_x_inteligente = alt.X("ano:Q", title="Ano-safra", axis=alt.Axis(format="d", tickMinStep=2))

    # Base do Gráfico
    base = alt.Chart(serie_plot).encode(x=eixo_x_inteligente)
    
    # 1. Linha principal
    linha = base.mark_line(point=True).encode(
        y=alt.Y("produtividade:Q", title=unidade, scale=alt.Scale(zero=False), axis=EIXO_BR),
        color=alt.Color("Nome:N", legend=alt.Legend(title="Município", orient="bottom")),
        tooltip=["ano", "Nome", alt.Tooltip("produtividade_rotulo:N", title=unidade)],
    )
    
    # 2. Linha de Tendência (Regressão Linear)
    tendencia = base.transform_regression("ano", "produtividade", groupby=["Nome"]).mark_line(
        strokeDash=[5, 5], strokeWidth=2, opacity=0.6
    ).encode(
        color=alt.Color("Nome:N", legend=None)
    )
    
    # 3. Pontos de repetição de dados (qualidade do IBGE)
    marcas = base.transform_filter(alt.datum.repetido == True).mark_point(
        size=110, filled=True, color="#B00020"
    ).encode(
        y="produtividade:Q",
        tooltip=[alt.Tooltip("ano", title="Valor idêntico ao ano anterior")]
    )

    # 4. Faixas de El Niño / La Niña (também ajustado para ano:Q)
    df_clima = pd.DataFrame([
        {"ano": 2003, "Clima": "El Niño"}, {"ano": 2010, "Clima": "El Niño"},
        {"ano": 2015, "Clima": "El Niño"}, {"ano": 2016, "Clima": "El Niño"}, {"ano": 2024, "Clima": "El Niño"},
        {"ano": 2008, "Clima": "La Niña"}, {"ano": 2011, "Clima": "La Niña"}, 
        {"ano": 2021, "Clima": "La Niña"}, {"ano": 2022, "Clima": "La Niña"}
    ])
    clima_chart = alt.Chart(df_clima).mark_rule(size=8, opacity=0.3).encode(
        x=eixo_x_inteligente,
        color=alt.Color("Clima:N", scale=alt.Scale(domain=["El Niño", "La Niña"], range=["#d73027", "#4575b4"]), legend=alt.Legend(title="Eventos Climáticos", orient="bottom"))
    )

    # Junta as 4 camadas em uma só (use_container_width garante que não vaze no celular)
    grafico_prod = alt.layer(clima_chart, linha, tendencia, marcas).resolve_scale(color='independent')
    st.altair_chart(grafico_prod, use_container_width=True)
    
    st.caption("A linha tracejada indica a tendência tecnológica histórica. Faixas verticais marcam anos de fortes fenômenos climáticos. Pontos vermelhos indicam repetição cega de dados do IBGE.")

    st.subheader("Área de soja mapeada (MapBiomas)")
    area = alt.Chart(serie_plot).mark_area(opacity=0.4).encode(
        x=eixo_x_inteligente,
        y=alt.Y("soy_area_ha:Q", title="hectares", axis=EIXO_BR),
        color=alt.Color("Nome:N", legend=alt.Legend(title="Município", orient="bottom")),
        tooltip=["ano", "Nome", alt.Tooltip("area_rotulo:N", title="hectares")],
    )
    st.altair_chart(area, use_container_width=True)

    b1, b2 = st.columns(2)
    b1.download_button("Baixar série do município (CSV)", serie.to_csv(index=False).encode("utf-8"), file_name=f"soja_{municipio.lower().replace(' ', '_')}.csv", mime="text/csv", use_container_width=True)
    b2.download_button("Baixar base completa (CSV)", DADOS.read_bytes(), file_name=DADOS.name, mime="text/csv", use_container_width=True)
