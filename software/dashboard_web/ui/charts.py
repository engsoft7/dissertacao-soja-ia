import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def plot_produtividade(serie_plot: pd.DataFrame, is_dark: bool = True,
                       unidade: str = "", projecao: pd.DataFrame | None = None):
    """`unidade` rotula o eixo e o hover; sem ela o gráfico não diz se os
    valores estão em sacas ou em quilos, que o usuário alterna no topo.

    `projecao` traz as safras à frente da última publicada, no mesmo desenho
    que o aplicativo Android usa desde sempre: linha tracejada, emendada no
    último ano observado pelo valor real — para as duas não darem degrau —, e
    marcador só nos anos futuros. O painel não desenhava nada disso, e a
    projeção vivia só como número na outra tela.

    Espera as colunas `ano`, `produtividade`, `Nome`, `margem` e `previsto`,
    esta última falsa na safra-pivô e verdadeira nas projetadas."""
    bg_color = "rgba(0,0,0,0)"
    # Mesmos tons de --text-muted e --card-border do tema do painel.
    font_color = "#a1a1a6" if is_dark else "#6e6e73"
    grid_color = "rgba(255,255,255,0.09)" if is_dark else "rgba(0,0,0,0.08)"
    
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

    # Safras à frente da última publicada, no naipe do aplicativo.
    if projecao is not None and not projecao.empty:
        cor_do_municipio = {t.name: t.line.color for t in fig.data
                            if t.type == "scatter" and t.line.color}
        for nome, g in projecao.groupby("Nome", sort=False):
            g = g.sort_values("ano")
            # Marcador só no futuro: na safra-pivô o ponto já está desenhado
            # pela série observada, e dois marcadores no mesmo lugar sujam.
            tamanhos = [8 if p else 0 for p in g["previsto"]]
            fig.add_scatter(
                x=g["ano"], y=g["produtividade"],
                mode="lines+markers",
                name=f"{nome} — projeção",
                line=dict(color=cor_do_municipio.get(nome), dash="dash", width=3),
                marker=dict(size=tamanhos, symbol="circle-open",
                            line=dict(width=2)),
                customdata=g[["margem", "previsto"]].values,
                # A margem viaja no hover porque, nesta tela, é o único lugar
                # onde ela aparece — os indicadores do topo estão na outra.
                hovertemplate="<b>%{x}</b><br>Projeção: %{y:.1f} ± "
                              "%{customdata[0]:.1f}"
                              + (f" {unidade}" if unidade else "")
                              + "<extra></extra>",
            )

    # Carrega o histórico oficial de eventos El Niño e La Niña (dinâmico via NOAA)
    from pathlib import Path
    import json
    enso_path = Path(__file__).resolve().parents[3] / "pesquisa" / "dados" / "eventos_enso.json"
    # Sem o arquivo, nenhuma faixa: uma lista fixa aqui já marcou safras erradas.
    el_ninos, la_ninas = [], []
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
        # Legenda abaixo do eixo: era onde a barra de ferramentas do Plotly
        # não alcançava, e ficou por ler bem ali. O painel esconde a barra
        # (app.py), então a margem de cima não precisa mais reservar a faixa
        # em que ela aparecia.
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0),
        margin=dict(t=30, b=90)
    )
    
    return fig

def plot_area(serie_plot: pd.DataFrame, is_dark: bool = True):
    bg_color = "rgba(0,0,0,0)"
    # Mesmos tons de --text-muted e --card-border do tema do painel.
    font_color = "#a1a1a6" if is_dark else "#6e6e73"
    grid_color = "rgba(255,255,255,0.09)" if is_dark else "rgba(0,0,0,0.08)"
    
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
        # Legenda abaixo do eixo: era onde a barra de ferramentas do Plotly
        # não alcançava, e ficou por ler bem ali. O painel esconde a barra
        # (app.py), então a margem de cima não precisa mais reservar a faixa
        # em que ela aparecia.
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0),
        margin=dict(t=30, b=90)
    )
    
    return fig


def _layout_preco(fig, is_dark: bool, titulo_y: str):
    font_color = "#a1a1a6" if is_dark else "#6e6e73"
    grid_color = "rgba(255,255,255,0.09)" if is_dark else "rgba(0,0,0,0.08)"
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=font_color),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor=grid_color, title=titulo_y,
                   tickformat=",.0f"),
        hovermode="x unified",
        separators=",.",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0),
        margin=dict(t=30, b=80),
    )
    return fig


_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def cor_para(is_dark: bool) -> str:
    """Mesma cor da estimativa do Pará no aplicativo (corPara, MainActivity.kt)."""
    return "#58A6FF" if is_dark else "#1D4ED8"


def plot_para_mensal(meses: list[dict], is_dark: bool = True):
    """Médias mensais do Pará e de Chicago em R$/saca; a distância entre as linhas é a base."""
    df = pd.DataFrame(meses)
    df["data"] = pd.to_datetime(df["mes"] + "-01")
    cinza = "#a1a1a6" if is_dark else "#6e6e73"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["chicago"], name="Chicago em R$", mode="lines+markers",
        line=dict(color=cinza, width=2, dash="dash"),
        hovertemplate="Chicago: R$ %{y:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["para"], name="Pará (média mensal)", mode="lines+markers",
        line=dict(color=cor_para(is_dark), width=3), customdata=df["base"],
        hovertemplate="Pará: R$ %{y:,.2f}<br>base: %{customdata:+,.2f}<extra></extra>"))
    # Rótulos em português e um a cada três meses: o Plotly escreve "Oct/24".
    marcas = df.iloc[::-3].iloc[::-1]  # termina no mês corrente
    fig.update_xaxes(tickvals=marcas["data"],
                     ticktext=[_MESES[int(m[5:]) - 1] + "/" + m[2:4] for m in marcas["mes"]])
    return _layout_preco(fig, is_dark, "R$ por saca")


def plot_para_diario(velas: list[dict], is_dark: bool = True):
    """Chicago em R$ dia a dia (fechamento) e o Pará estimado (Chicago + base do mês)."""
    df = pd.DataFrame(velas)
    df["data"] = pd.to_datetime(df["t"], unit="s", utc=True).dt.tz_convert("America/Belem")
    cinza = "#a1a1a6" if is_dark else "#6e6e73"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["c"], name="Chicago em R$", mode="lines",
        line=dict(color=cinza, width=1.5),
        hovertemplate="Chicago: R$ %{y:,.2f}<extra></extra>"))
    if "pa" in df and df["pa"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["data"], y=df["pa"], name="Pará estimado", mode="lines",
            line=dict(color=cor_para(is_dark), width=2.5, dash="dash"),
            hovertemplate="Pará estimado: R$ %{y:,.2f}<extra></extra>"))
    # Sem pregão no fim de semana: sem o salto, o gráfico ligava sexta a
    # segunda com uma reta que parecia preço parado.
    fig.update_xaxes(tickformat="%d/%m", rangebreaks=[dict(bounds=["sat", "mon"])])
    return _layout_preco(fig, is_dark, "R$ por saca")


def cor_nivel(nivel: str, is_dark: bool = True) -> str:
    """Cores da janela de pulverização, as mesmas do aplicativo (corDoNivel, Tempo.kt)."""
    cores = {"boa": ("#3fb950", "#15803d"), "atenção": ("#d29922", "#b45309"),
             "evitar": ("#f85149", "#b91c1c")}
    escuro, claro = cores[nivel]
    return escuro if is_dark else claro


def plot_janela_pulverizacao(horas: list[dict], is_dark: bool = True):
    """Faixa das próximas horas, uma barra por hora na cor do nível, com os motivos no hover."""
    df = pd.DataFrame(horas)
    df["rotulo"] = df["hora"].map(lambda h: h.strftime("%d/%m %Hh"))
    df["detalhe"] = df.apply(
        lambda r: (f"{r['temperatura']:.0f} °C" if pd.notna(r["temperatura"]) else "–")
        + f", umidade {r['umidade']:.0f}%" * pd.notna(r["umidade"])
        + f", vento {r['vento_2m']:.0f} km/h na lavoura" * pd.notna(r["vento_2m"])
        + f", chuva {r['chance_chuva']:.0f}%" * pd.notna(r["chance_chuva"])
        + ("<br>" + "<br>".join(r["motivos"]) if r["motivos"] else ""), axis=1)
    fig = go.Figure()
    for nivel in ("boa", "atenção", "evitar"):
        s = df[df["nivel"] == nivel]
        fig.add_trace(go.Bar(
            x=s["rotulo"], y=[1] * len(s), name=nivel.capitalize(), customdata=s["detalhe"],
            marker_color=cor_nivel(nivel, is_dark),
            hovertemplate="<b>%{x}</b>: " + nivel + "<br>%{customdata}<extra></extra>"))
    font_color = "#a1a1a6" if is_dark else "#6e6e73"
    fig.update_layout(
        barmode="overlay", bargap=0.08, height=170,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=font_color),
        xaxis=dict(categoryorder="array", categoryarray=list(df["rotulo"]), showgrid=False,
                   tickangle=0, nticks=8),
        yaxis=dict(visible=False, range=[0, 1]),
        legend=dict(orientation="h", yanchor="top", y=-0.35, xanchor="left", x=0),
        margin=dict(t=10, b=60, l=10, r=10))
    return fig


def plot_chuva_et0(diario: dict, hoje, is_dark: bool = True):
    """Chuva e evapotranspiração de referência por dia: 7 dias passados e 7 previstos."""
    df = pd.DataFrame({"dia": pd.to_datetime(diario["time"]),
                       "chuva": diario.get("precipitation_sum"),
                       "et0": diario.get("et0_fao_evapotranspiration")})
    cinza = "#a1a1a6" if is_dark else "#6e6e73"
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["dia"], y=df["chuva"], name="Chuva", marker_color=cor_para(is_dark),
                         hovertemplate="Chuva: %{y:.1f} mm<extra></extra>"))
    fig.add_trace(go.Scatter(x=df["dia"], y=df["et0"], name="Evapotranspiração (ET0)", mode="lines+markers",
                             line=dict(color=cinza, width=2, dash="dash"),
                             hovertemplate="ET0: %{y:.1f} mm<extra></extra>"))
    hoje = pd.Timestamp(hoje)
    fig.add_vrect(x0=hoje - pd.Timedelta(hours=12), x1=df["dia"].max() + pd.Timedelta(hours=12),
                  fillcolor=cinza, opacity=0.08, line_width=0,
                  annotation_text="previsão", annotation_position="top left")
    fig.update_xaxes(tickformat="%d/%m")
    fig = _layout_preco(fig, is_dark, "mm por dia")
    fig.update_yaxes(tickformat=",.0f")
    return fig
