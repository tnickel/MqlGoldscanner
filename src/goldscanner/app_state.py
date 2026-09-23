"""Prozessweite Singletons für die Streamlit-Seiten (cache_resource).

Seiten importieren NIE streamlit_app (das würde die App-Shell re-ausführen) —
sondern dieses Modul.
"""
from __future__ import annotations

import streamlit as st


@st.cache_resource(show_spinner=False)
def hole_db():
    from .db import Db
    return Db()
