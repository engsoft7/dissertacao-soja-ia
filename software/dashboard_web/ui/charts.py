import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def plot_produtividade(serie_plot: pd.DataFrame, is_dark: bool = True,
                       unidade: str = ""):
    """`unidade` rotula o eixo e o hover; sem ela o gráfico não diz se os
    valores estão em sacas ou em quilos, que o usuário alterna no topo."""
    bg_color = "rgba(0,0,0,0)"
    font_color = "#c9d1d9" if is_dark else "#333333"
    grid_color = "#30363d" if is_dark else "#e5e5e5"
    
    fig = px.line(
        serie_plot, 
        x="ano", 
        y="produtividade", 
        color="Nome", 
        markers=True,
        
        labels={"ano": "Ano-safra",
                "produtividade": f"Produtividade ({unidade})" if unidade else "Produtividade",
                "Nome": "Município"}
    )
    
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=8, symbol="circle-open", line=dict(width=2)),
        hovertemplate="<b>%{x}</b><br>Produtividade: %{y:.1f}"
                      + (f" {unidade}" if unidade else "") + "<extra></extra>",
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

    # Carrega o histórico oficial de eventos El Niño e La Niña (dinâmico via NOAA)
    from pathlib import Path
    import json
    enso_path = Path(__file__).resolve().parents[3] / "pesquisa" / "dados" / "eventos_enso.json"
    el_ninos = [2003, 2010, 2015, 2016, 2023, 2024]
    la_ninas = [2000, 2008, 2011, 2021, 2022]
    if enso_path.exists():
        try:
            d = json.loads(enso_path.read_text(encoding="utf-8"))
            el_ninos = d.get("el_ninos", el_ninos)
            la_ninas = d.get("la_ninas", la_ninas)
        except Exception:
            pass

    # O arquivo da NOAA vai além da última safra publicada pelo IBGE. Sem
    # recortar, o gráfico ganharia faixas de anos sem nenhum ponto plotado.
    if not serie_plot.empty:
        ano_min, ano_max = int(serie_plot["ano"].min()), int(serie_plot["ano"].max())
        el_ninos = [a for a in el_ninos if ano_min <= a <= ano_max]
        la_ninas = [a for a in la_ninas if ano_min <= a <= ano_max]

    clima_rows = [{"ano": a, "Clima": "El Niño"} for a in el_ninos] + [{"ano": a, "Clima": "La Niña"} for a in la_ninas]
    df_clima = pd.DataFrame(clima_rows)

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
        separators=",.",  # decimal com vírgula, milhar com ponto
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
        
        labels={"ano": "Ano-safra", "soy_area_ha": "Hectares", "Nome": "Município"}
    )
    
    fig.update_traces(
        line=dict(width=2),
        hovertemplate="<b>%{x}</b><br>Área: %{y:,.0f} ha<extra></extra>"
    )
    
    fig.update_layout(
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        font=dict(family="Inter, sans-serif", color=font_color),
        xaxis=dict(showgrid=False, tickmode="linear", dtick=2),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor=grid_color,
                   tickformat=",.0f"),
        hovermode="x unified",
        separators=",.",  # decimal com vírgula, milhar com ponto
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig
