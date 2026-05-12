import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import gspread
import json # <-- NOUVEAU

# --- CONNEXION GOOGLE SHEETS ---
def connect_gsheets():
    try:
        # 1. Si l'application est sur internet (Streamlit Cloud)
        if "google_secret" in st.secrets:
            creds_dict = json.loads(st.secrets["google_secret"])
            gc = gspread.service_account_from_dict(creds_dict)
        # 2. Si l'application est sur ton ordi (Thonny)
        else:
            gc = gspread.service_account(filename='secrets.json')
            
        sh = gc.open("BDD_Coparentalite")
        return sh
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        return None

sh = connect_gsheets()

# ... (garde tout le reste de ton code identique en dessous) ...

# --- FONCTIONS POUR LIRE ET ÉCRIRE ---
def get_data(sheet_name):
    worksheet = sh.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_full_df(sheet_name, df):
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear()
    # On réécrit les colonnes + les données
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def append_row(sheet_name, row_list):
    worksheet = sh.worksheet(sheet_name)
    worksheet.append_row(row_list)

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="App de garde Alternée", page_icon="👨‍👩‍👧", layout="centered")
st.title("👨‍👩‍👧 Agenda pour un avenir serein")

# --- PARAMÈTRES (SIDEBAR) ---
st.sidebar.header("⚙️ Paramètres")
nom_p1 = st.sidebar.text_input("Prénom du Parent 1", "Papa")
nom_p2 = st.sidebar.text_input("Prénom du Parent 2", "Maman")

st.sidebar.markdown("---")
st.sidebar.header("🔄 Roulement de garde")
nouvelle_ref = st.sidebar.date_input("Vendredi de référence", value=date(2026, 5, 15))
parent_reprise = st.sidebar.radio("Qui commence ce vendredi ?", [nom_p1, nom_p2])

# --- CHARGEMENT DES DONNÉES DEPUIS LE CLOUD ---
if sh:
    df_exceptions = get_data("Garde")
    if df_exceptions.empty or 'Date' not in df_exceptions.columns: 
        df_exceptions = pd.DataFrame(columns=["Date", "Parent"])
        
    df_notes = get_data("Notes")
    if df_notes.empty or 'Date' not in df_notes.columns: 
        df_notes = pd.DataFrame(columns=["Date", "Parent", "Texte"])
        
    df_activites = get_data("Activites")
    if df_activites.empty or 'Date Début' not in df_activites.columns: 
        df_activites = pd.DataFrame(columns=["Date Début", "Date Fin", "Type", "Description", "Parent en charge"])
        
    df_frais = get_data("Frais")
    if df_frais.empty or 'Date' not in df_frais.columns: 
        df_frais = pd.DataFrame(columns=["Date", "Payé par", "Montant (€)", "Description", "Remboursé"])
    else:
        if "Remboursé" not in df_frais.columns:
            df_frais["Remboursé"] = False
        else:
            df_frais["Remboursé"] = df_frais["Remboursé"].astype(str).str.upper() == "TRUE"
else:
    st.stop() # On arrête si la connexion échoue # On arrête si la connexion échoue

# --- ONGLETS ---
tab1, tab2, tab3 = st.tabs(["📅 Garde & Notes", "⚽ Activités", "💰 Frais"])

# ==========================================
# ONGLET 1 : GARDE & NOTES
# ==========================================
with tab1:
    st.header("Calendrier Mensuel")
    
    col_m1, col_m2 = st.columns(2)
    
    with col_m1.expander("🔄 Ajouter une exception de garde"):
        d_deb = st.date_input("Début", key="ex_deb")
        d_fin = st.date_input("Fin", value=d_deb, key="ex_fin")
        p_ex = st.selectbox("Garde pour", [nom_p1, nom_p2], key="ex_p")
        if st.button("Enregistrer l'exception"):
            delta = d_fin - d_deb
            for i in range(delta.days + 1):
                append_row("Garde", [str(d_deb + timedelta(days=i)), p_ex])
            st.rerun()

    with col_m2.expander("✍️ Ajouter une note"):
        d_note = st.date_input("Date", key="n_date")
        p_note = st.selectbox("Auteur", [nom_p1, nom_p2], key="n_p")
        t_note = st.text_input("Texte", key="n_t")
        if st.button("Enregistrer la note") and t_note:
            append_row("Notes", [str(d_note), p_note, t_note])
            st.rerun()

    # --- AFFICHAGE CALENDRIER ---
    col_mois, col_annee = st.columns(2)
    noms_mois = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    m_choisi = col_mois.selectbox("Mois", range(1, 13), index=date.today().month-1, format_func=lambda x: noms_mois[x-1])
    a_choisie = col_annee.selectbox("Année", range(2025, 2028), index=1)
    
    cal = calendar.monthcalendar(a_choisie, m_choisi)
    
    html_cal = """<style>
    .cal-table { width: 100%; border-collapse: collapse; text-align: center; }
    .cal-table td { height: 120px; width: 14%; border: 1px solid #ddd; vertical-align: top; padding: 5px; }
    .jour-num { font-weight: bold; text-align: right; }
    .garde-p1 { background-color: #cce5ff; border-radius: 5px; padding: 3px; font-size: 0.8em; margin-top: 5px;}
    .garde-p2 { background-color: #d4edda; border-radius: 5px; padding: 3px; font-size: 0.8em; margin-top: 5px;}
    .exception { background-color: #ffcc80; border: 2px dashed #e65100; border-radius: 5px; padding: 3px; font-size: 0.8em; margin-top: 5px;}
    .act-badge { background-color: #eee; font-size: 0.7em; margin-top: 2px; text-align: left; padding: 2px; border-radius: 3px; border: 1px solid #ccc;}
    </style><table class="cal-table"><tr><th>Lun</th><th>Mar</th><th>Mer</th><th>Jeu</th><th>Ven</th><th>Sam</th><th>Dimanche</th></tr>"""

    for semaine in cal:
        html_cal += "<tr>"
        for jour in semaine:
            if jour == 0:
                html_cal += "<td></td>"
            else:
                d_obj = date(a_choisie, m_choisi, jour)
                d_str = str(d_obj)
                
                # Notes et étoiles
                has_note = d_str in df_notes['Date'].astype(str).values
                star = " ⭐" if has_note else ""
                
                # Détermination Garde
                exc = df_exceptions[df_exceptions['Date'].astype(str) == d_str]
                if not exc.empty:
                    nom_g = exc.iloc[0]['Parent']
                    cl = "exception"
                else:
                    diff = (d_obj - nouvelle_ref).days
                    p_a = parent_reprise
                    p_b = nom_p2 if parent_reprise == nom_p1 else nom_p1
                    nom_g = p_a if (diff // 7) % 2 == 0 else p_b
                    cl = "garde-p1" if nom_g == nom_p1 else "garde-p2"
                
                # Activités
                acts_html = ""
                for _, act in df_activites.iterrows():
                    try:
                        if str(act['Date Début']) <= d_str <= str(act['Date Fin']):
                            acts_html += f'<div class="act-badge">📌 {act["Description"]}</div>'
                    except: pass
                
                html_cal += f'<td><div class="jour-num">{jour}{star}</div><div class="{cl}">{nom_g}</div>{acts_html}</td>'
        html_cal += "</tr>"
    html_cal += "</table>"
    st.markdown(html_cal, unsafe_allow_html=True)

    # --- GESTION DES NOTES ---
    st.subheader("📝 Notes et Mémos")
    col_n1, col_n2 = st.columns(2)
    with col_n1:
        st.info(f"Notes de {nom_p1}")
        for _, n in df_notes[df_notes['Parent'] == nom_p1].iterrows():
            st.write(f"**{n['Date']}** : {n['Texte']}")
    with col_n2:
        st.success(f"Notes de {nom_p2}")
        for _, n in df_notes[df_notes['Parent'] == nom_p2].iterrows():
            st.write(f"**{n['Date']}** : {n['Texte']}")

# ==========================================
# ONGLET 2 : ACTIVITÉS
# ==========================================
with tab2:
    st.header("Activités & Rendez-vous")
    with st.form("add_act", clear_on_submit=True):
        c1, c2 = st.columns(2)
        d1 = c1.date_input("Du")
        d2 = c2.date_input("Au", value=d1)
        t = st.selectbox("Type", ["École", "Sport", "Médical", "Autre"])
        desc = st.text_input("Description (ex: Trail des Boucles Ardennaise)")
        resp = st.radio("Responsable", [nom_p1, nom_p2, "Les deux"])
        if st.form_submit_button("Ajouter"):
            append_row("Activites", [str(d1), str(d2), t, desc, resp])
            st.rerun()
    
    edited_act = st.data_editor(df_activites, num_rows="dynamic", use_container_width=True)
    if st.button("Enregistrer les modifications d'activités"):
        save_full_df("Activites", edited_act)
        st.rerun()
# ==========================================
# ONGLET 3 : FRAIS
# ==========================================
with tab3:
    st.header("💰 Dépenses Partagées")

    # --- 1. FORMULAIRE D'AJOUT ---
    with st.expander("➕ Ajouter une nouvelle dépense", expanded=True):
        with st.form("add_frais", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dfra = c1.date_input("Date")
            payeur = c2.selectbox("Payé par", [nom_p1, nom_p2])
            
            # Champ texte pour accepter la virgule ou le point sans broncher
            montant_str = st.text_input("Montant (€) - Ex: 12,50", value="")
            descf = st.text_input("Objet (ex: Chaussures, Veste, Cantine...)")
            
            if st.form_submit_button("Ajouter la dépense"):
                if montant_str and descf:
                    # LA SOLUTION DÉFINITIVE : On le transforme en VRAI nombre informatique (float)
                    montant_propre = montant_str.replace(',', '.')
                    try:
                        montant_final = float(montant_propre)
                    except ValueError:
                        montant_final = 0.0
                    
                    # On envoie montant_final (un vrai nombre) à Google Sheets, pas du texte !
                    append_row("Frais", [str(dfra), payeur, montant_final, descf, False])
                    st.rerun()
                else:
                    st.error("⚠️ N'oublie pas de mettre un montant et une description !")

    st.markdown("---")

    # --- 2. CALCUL DES COMPTES (BILAN) ---
    st.subheader("⚖️ Bilan des comptes en cours")
    
    if not df_frais.empty:
        # Nettoyage
        df_frais['Montant (€)'] = df_frais['Montant (€)'].astype(str).str.replace(',', '.')
        df_frais['Montant (€)'] = pd.to_numeric(df_frais['Montant (€)'], errors='coerce').fillna(0.0)
        
        frais_a_payer = df_frais[df_frais['Remboursé'] == False]
        
        total_p1 = frais_a_payer[frais_a_payer['Payé par'] == nom_p1]['Montant (€)'].sum()
        total_p2 = frais_a_payer[frais_a_payer['Payé par'] == nom_p2]['Montant (€)'].sum()
        
        col_b1, col_b2, col_b3 = st.columns(3)
        col_b1.metric(f"Payé par {nom_p1}", f"{total_p1:.2f} €")
        col_b2.metric(f"Payé par {nom_p2}", f"{total_p2:.2f} €")
        
        diff = total_p1 - total_p2
        if diff > 0:
            col_b3.warning(f"⚠️ {nom_p2} doit {diff / 2:.2f} € à {nom_p1}")
        elif diff < 0:
            col_b3.warning(f"⚠️ {nom_p1} doit {abs(diff) / 2:.2f} € à {nom_p2}")
        else:
            col_b3.success("✅ Comptes à l'équilibre !")
    else:
        st.info("Aucune dépense pour le moment.")

    st.markdown("---")

    # --- 3. LISTE ÉPURÉE DES DÉPENSES ---
    st.subheader("📋 Détail des dépenses")
    
    if not df_frais.empty:
        for index, row in df_frais.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
                
                barre = "~~" if row['Remboursé'] else "" 
                
                col1.write(f"📅 {row['Date']}")
                col2.write(f"{barre}**{row['Description']}** (par {row['Payé par']}){barre}")
                col3.write(f"{barre}**{float(row['Montant (€)']):.2f} €**{barre}")
                
                with col4:
                    c_act1, c_act2 = st.columns(2)
                    
                    if not row['Remboursé']:
                        if c_act1.button("✅", key=f"remb_{index}", help="Marquer comme remboursé"):
                            df_frais.at[index, 'Remboursé'] = True
                            save_full_df("Frais", df_frais)
                            st.rerun()
                    else:
                        c_act1.write("✔️") 
                        
                    if c_act2.button("🗑️", key=f"del_{index}", help="Supprimer en cas d'erreur"):
                        df_frais = df_frais.drop(index)
                        save_full_df("Frais", df_frais)
                        st.rerun()
                
                st.divider()