import streamlit, os

def injetar_meta_nativas():
    """Injeta as tags 'theme-color' diretamente no index.html do Streamlit para o celular ficar nativo"""
    try:
        index_path = os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        if "theme-color" not in html:
            metas = (
                '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#ffffff">'
                '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#0e1117">'
            )
            html = html.replace("<head>", f"<head>{metas}")
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(html)
    except Exception:
        pass
