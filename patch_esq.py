with open("software/dashboard_web/app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Delete lines containing redundant dropdowns:
# The easiest way is to use regex. But since I know the exact code, I can just replace the chunk.
chunk_to_remove = """        municipio = st.selectbox(
            "Selecione o Município / Polo",
            municipios,
            key="mun_sel",
            format_func=disp,
            on_change=on_dropdown_change)

        comparar = st.toggle("Comparar com outro município", value=False)
        mun_comp: str | None = None
        if comparar:
            opcoes_comp = [m for m in municipios if m != municipio]
            mun_comp = st.selectbox(
                "Município para Comparação",
                opcoes_comp,
                format_func=disp)  # type: ignore

        st.write("")
        ano_alvo = st.number_input(
            "Safra Alvo para Projeção",
            min_value=int(
                df.ano.max()) + 1,
            max_value=int(
                df.ano.max()) + 3,
            value=int(
                df.ano.max()) + 1)"""

text = text.replace(chunk_to_remove, "")
text = text.replace('fator = SACA_KG if "Sacadas" in unidade else 1.0', "")

with open("software/dashboard_web/app.py", "w", encoding="utf-8") as f:
    f.write(text)
