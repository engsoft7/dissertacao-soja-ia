import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def plot_produtividade(serie_plot: pd.DataFrame, is_dark: bool = True):
    bg_color = "rgba(0,0,0,0)"
    font_color = "#c9d1d9" if is_dark else "#333333"
    grid_color = "#30363d" if is_dark else "#e5e5e5"
    
    fig = px.line(
        serie_plot, 
        x="ano", 
        y="produtividade", 
        color="Nome", 
        markers=True,
        title="Histórico de Produtividade Agrícola",
        labels={"ano": "Ano-safra", "produtividade": "Produtividade", "Nome": "Município"}
    )
    
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=8, symbol="circle-open", line=dict(width=2)),
        hovertemplate="<b>%{x}</b><br>Produtividade: %{y}<extra></extra>",
        selector=dict(type="scatter")
    )
    
    import numpy as np
    
    # Restaura a Tendência Tecnológica Linear (Regressão OLS simples)
    if not serie_plot.empty:
        z = np.polyfit(serie_plot["ano"], serie_plot["produtividade"], 1)
        p = np.poly1d(z)
        fig.add_scatter(
            x=serie_plot["ano"], 
            y=p(serie_plot["ano"]), 
            mode="lines", 
            name="Tendência Tecnológica",
            line=dict(color="#8b949e" if is_dark else "rgba(0,0,0,0.5)", dash="dash", width=2), 
            hoverinfo="skip",
            showlegend=True
        )

    # Constroi o dataframe historico de anomalias climaticas (Hardcoded exatamente como no antigo Altair)
    df_clima = pd.DataFrame([
        {"ano": 2003, "Clima": "El Niño"}, {"ano": 2010, "Clima": "El Niño"}, 
        {"ano": 2015, "Clima": "El Niño"}, {"ano": 2016, "Clima": "El Niño"}, 
        {"ano": 2024, "Clima": "El Niño"}, {"ano": 2000, "Clima": "La Niña"}, 
        {"ano": 2008, "Clima": "La Niña"}, {"ano": 2011, "Clima": "La Niña"}, 
        {"ano": 2021, "Clima": "La Niña"}, {"ano": 2022, "Clima": "La Niña"}
    ])

    # Restaura as faixas climáticas de El Niño e La Niña e injeta de volta na Legenda
    el_nino_color = "rgba(215, 48, 39, 0.3)"
    la_nina_color = "rgba(69, 117, 180, 0.3)"
    
    anos_unicos = df_clima
    
    has_nino = False
    has_nina = False
    
    for index, row in anos_unicos.iterrows():
        # Cria barras verticais estritas em cima do ano, imitando as larguras antigas
        if row["Clima"] == "El Niño":
            fig.add_vrect(x0=row["ano"]-0.2, x1=row["ano"]+0.2, fillcolor=el_nino_color, line_width=0, layer="below")
            has_nino = True
        elif row["Clima"] == "La Niña":
            fig.add_vrect(x0=row["ano"]-0.2, x1=row["ano"]+0.2, fillcolor=la_nina_color, line_width=0, layer="below")
            has_nina = True
            
    # TRUQUE DO PLOTLY: Adiciona traces vazios apenas para jogar os blocos de clima na Legenda Oficial!
    if has_nino:
        fig.add_trace(go.Bar(x=[None], y=[None], marker_color=el_nino_color, name="Histórico El Niño", hoverinfo="none"))
    if has_nina:
        fig.add_trace(go.Bar(x=[None], y=[None], marker_color=la_nina_color, name="Histórico La Niña", hoverinfo="none"))


    
    fig.update_layout(
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        font=dict(family="Inter, sans-serif", color=font_color),
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor=grid_color, tickmode="linear", dtick=2),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor=grid_color),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

def plot_area(serie_plot: pd.DataFrame, is_dark: bool = True):
    bg_color = "rgba(0,0,0,0)"
    font_color = "#c9d1d9" if is_dark else "#333333"
    grid_color = "#30363d" if is_dark else "#e5e5e5"
    
    fig = px.area(
        serie_plot, 
        x="ano", 
        y="soy_area_ha", 
        color="Nome",
        title="Expansão da Área Plantada (Hectares)",
        labels={"ano": "Ano-safra", "soy_area_ha": "Hectares", "Nome": "Município"}
    )
    
    fig.update_traces(
        line=dict(width=2),
        hovertemplate="<b>%{x}</b><br>Área: %{y} ha<extra></extra>"
    )
    
    fig.update_layout(
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        font=dict(family="Inter, sans-serif", color=font_color),
        xaxis=dict(showgrid=False, tickmode="linear", dtick=2),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor=grid_color),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig
