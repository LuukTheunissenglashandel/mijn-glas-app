import streamlit as st
import pandas as pd
from supabase import create_client, Client
import base64
import os
from datetime import datetime
import pytz
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

# ... (Configuratie & Data Classes blijven gelijk) ...

# =============================================================================
# 3. SERVICE LAAG (GEOPTIMALISEERD)
# =============================================================================

class VoorraadService:
    def __init__(self, repo: GlasVoorraadRepository):
        self.repo = repo

    def laad_data(self, zoekterm: str, page: int) -> Tuple[pd.DataFrame, int]:
        # Cache op repository niveau is sneller
        @st.cache_data(ttl=600, show_spinner=False)
        def _cached_fetch(zoek: str, p: int):
            return self.repo.get_paged_data(zoek, p, ROWS_PER_PAGE)
        
        data, count = _cached_fetch(zoekterm, page)
        kolommen = ["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]
        
        if not data: 
            return pd.DataFrame(columns=kolommen), 0
            
        df = pd.DataFrame(data)
        # Vectorized operation in plaats van .apply() voor snelheid
        selected_ids = st.session_state.app_state.selected_ids
        df["Selecteren"] = df["id"].isin(selected_ids)
        
        # Zorg dat kolommen bestaan zonder loops
        for col in kolommen:
            if col not in df.columns: df[col] = None
            
        return df[kolommen], count

    def trigger_mutation(self):
        st.cache_data.clear()

# =============================================================================
# 5. GEOPTIMALISEERD INTERACTIEF BLOK
# =============================================================================

def sync_selections():
    """Wordt aangeroepen bij ELKE wijziging in de data_editor."""
    if "main_editor" in st.session_state:
        edits = st.session_state.main_editor.get("edited_rows", {})
        df = st.session_state.app_state.mijn_data
        
        for idx_str, changes in edits.items():
            idx = int(idx_str)
            if "Selecteren" in changes:
                rid = df.iloc[idx]["id"]
                if changes["Selecteren"]:
                    st.session_state.app_state.selected_ids.add(rid)
                else:
                    st.session_state.app_state.selected_ids.discard(rid)

@st.fragment
def render_main_interface(service):
    state = st.session_state.app_state
    
    # Zoekveld optimalisatie: gebruik 'on_change' in plaats van handmatige vergelijking
    c1, c2 = st.columns([7, 2])
    zoek_val = c1.text_input(
        "Zoeken", 
        value=state.zoek_veld, 
        placeholder="🔍 Zoek op order, omschrijving of locatie...", 
        label_visibility="collapsed",
        key="search_input"
    )
    
    # Update state alleen als het echt nodig is, voorkom dubbele rerun
    if zoek_val != state.zoek_veld:
        state.zoek_veld = zoek_val
        state.current_page = 0
        st.rerun(scope="fragment")

    # Data ophalen
    state.mijn_data, state.total_count = service.laad_data(state.zoek_veld, state.current_page)
    
    # Snelle selectie berekening (zonder extra DB call indien mogelijk)
    sel_count = len(state.selected_ids)
    suffix = f" ({sel_count})" if sel_count > 0 else ""

    # Actie knoppen
    if state.selected_ids:
        b1, b2 = st.columns(2)
        if b1.button("❌ SLUIT" if state.show_location_grid else "📍 LOCATIE WIJZIGEN", use_container_width=True):
            state.show_location_grid = not state.show_location_grid
            st.rerun(scope="fragment")
        
        with b2:
            if not state.confirm_delete:
                if st.button(f"🗑️ MEEGENOMEN {suffix}", use_container_width=True, type="primary"):
                    state.confirm_delete = True
                    st.rerun(scope="fragment")
            else:
                st.warning("Verwijderen?")
                mj1, mj2 = st.columns(2)
                if mj1.button("Ja", use_container_width=True):
                    service.push_undo_state(list(state.selected_ids))
                    service.repo.delete_many(list(state.selected_ids))
                    state.selected_ids.clear()
                    state.confirm_delete = False
                    service.trigger_mutation()
                    st.rerun(scope="fragment")
                if mj2.button("Nee", use_container_width=True):
                    state.confirm_delete = False
                    st.rerun(scope="fragment")

    # Tabel weergave
    st.data_editor(
        state.mijn_data,
        column_config={
            "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"),
            "id": None,
            "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
            "aantal": st.column_config.NumberColumn("Aant.", width="small")
        },
        hide_index=True, 
        use_container_width=True, 
        key="main_editor", 
        height=400, # Vaste hoogte voorkomt "layout shift"
        disabled=["id"],
        on_change=sync_selections
    )

    # Verwerk inline edits (locatie/aantal aanpassingen)
    if "main_editor" in st.session_state:
        edits = st.session_state.main_editor.get("edited_rows", {})
        db_updates = []
        for idx_str, changes in edits.items():
            # Filter alleen de data-wijzigingen (niet de checkbox)
            clean_changes = {k: v for k, v in changes.items() if k != "Selecteren"}
            if clean_changes:
                row_id = state.mijn_data.iloc[int(idx_str)]["id"]
                db_updates.append({"id": int(row_id), **clean_changes})
        
        if db_updates:
            service.repo.bulk_update_fields(db_updates)
            service.trigger_mutation()
            # We doen hier GEEN rerun, st.data_editor houdt zijn eigen state bij
            # Dit voorkomt het verspringen van de cursor/focus.

    # Paginering (Versimpeld voor snelheid)
    num_p = max(1, (state.total_count - 1) // ROWS_PER_PAGE + 1)
    if num_p > 1:
        p1, p2, p3 = st.columns([1, 2, 1])
        if p1.button("⬅️", disabled=state.current_page == 0):
            state.current_page -= 1
            st.rerun(scope="fragment")
        p2.markdown(f"<center>Pagina {state.current_page + 1} / {num_p}</center>", unsafe_allow_html=True)
        if p3.button("➡️", disabled=state.current_page == num_p - 1):
            state.current_page += 1
            st.rerun(scope="fragment")
