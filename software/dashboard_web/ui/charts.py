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
        hovertemplate="<b>%{x}</b><br>Produtividade: %{y}<extra></extra>"
    )
    
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
