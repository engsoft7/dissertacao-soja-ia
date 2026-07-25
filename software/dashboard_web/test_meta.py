import streamlit as st
import streamlit.components.v1 as components

st.write("Test of theme color")

components.html("""
<script>
    try {
        var p = window.parent.document;
        console.log("Access to parent successful!");
    } catch(e) {
        console.error("No access to parent: " + e);
        document.write("No access to parent");
    }
</script>
""", height=50)
