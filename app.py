# --- 8. ZOEKFUNCTIE & BULK ACTIES ---
c_in, c_bu = st.columns([2, 1], gap="large")

with c_in:
    zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of omschrijving...", label_visibility="collapsed", key="zoek_input")

# --- NIEUW: BULK ACTIE CONTAINER ---
with c_bu:
    with st.expander("📦 Bulk Locatie Wijzigen"):
        nieuwe_locatie = st.selectbox("Nieuwe Locatie", LOCATIE_OPTIES, key="bulk_loc")
        if st.button("Toepassen op selectie", use_container_width=True):
            # Haal de ID's op van de rijen die zijn aangevinkt in de editor
            # We kijken naar de state van de editor
            if "editor" in st.session_state and "edited_rows" in st.session_state.editor:
                # Dit deel verwerkt de wijzigingen die in de editor zijn gedaan
                pass 
            
            # De meest betrouwbare manier is om de checkbox uit de 'edited_df' te lezen
            # (Zie stap 10 voor de daadwerkelijke verwerking na de knopdruk)
            st.session_state.bulk_update_trigger = True

# --- 9. TABEL VOORBEREIDEN ---
view_df = df.copy()

# Filteren op zoekterm
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Voeg een tijdelijke selectiekolom toe (altijd False bij start)
view_df["Selecteer"] = False
view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

# Kolomvolgorde (Selecteer vooraan gezet)
volgorde = ["Selecteer", "Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad_bool", "Omschrijving", "ID"]
view_df = view_df[volgorde]

# Editor weergeven
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("S"),
        "Locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, required=True),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("✅ Uit"),
        "ID": None,
    },
    disabled=["Aantal", "Breedte", "Hoogte", "Order", "Omschrijving"],
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# --- 10. VERBETERDE OPSLAGLOGICA ---

# 1. Check op Bulk Update
if st.session_state.get("bulk_update_trigger", False):
    geselecteerde_ids = edited_df[edited_df["Selecteer"] == True]["ID"].tolist()
    
    if geselecteerde_ids:
        # Update alleen de Locatie voor de geselecteerde ID's in de hoofd-dataframe
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(geselecteerde_ids), "Locatie"] = nieuwe_locatie
        sla_data_op(st.session_state.mijn_data)
        st.session_state.bulk_update_trigger = False
        st.success(f"Locatie voor {len(geselecteerde_ids)} rijen gewijzigd naar {nieuwe_locatie}!")
        st.rerun()
    else:
        st.warning("Selecteer eerst rijen met het vinkje in de eerste kolom.")
        st.session_state.bulk_update_trigger = False

# 2. Check op handmatige wijzigingen in de tabel zelf
elif not edited_df.drop(columns=["Selecteer"]).equals(view_df.drop(columns=["Selecteer"])):
    # Sync de checkbox voor 'Uit voorraad'
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # Update hoofd-data op basis van ID
    for index, row in edited_df.iterrows():
        rid = row["ID"]
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == rid, ["Locatie", "Uit voorraad"]] = [row["Locatie"], row["Uit voorraad"]]
    
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
