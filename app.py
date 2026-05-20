import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import gspread
import json
import plotly.express as px
import textwrap

# --- CONNEXION GOOGLE SHEETS ---
def connect_gsheets():
    try:
        # 1. Si l'application est sur internet (Streamlit Cloud)
        if "google_secret" in st.secrets:
            creds_dict = json.loads(st.secrets["google_secret"])
            gc = gspread.service_account_from_dict(creds_dict)
        # 2. Si l'application est sur ton ordi (Thonny/VS Code)
        else:
            gc = gspread.service_account(filename='secrets.json')
            
        sh = gc.open("BDD_Coparentalite")
        return sh
    except Exception as e:
        st.error(f"Erreur de connexion à Google Sheets : {e}")
        return None

sh = connect_gsheets()

# --- INITIALISATION ET ROBUSTESSE DES FEUILLES ---
def ensure_worksheet_exists(sh, name, headers):
    try:
        ws = sh.worksheet(name)
        # Vérification des colonnes pour migration transparente
        existing_headers = ws.row_values(1)
        if not existing_headers:
            ws.update([headers])
        else:
            # Migration pour ajouter la colonne "Catégorie" si absente
            if name == "Frais" and "Catégorie" not in existing_headers:
                ws.update_cell(1, len(existing_headers) + 1, "Catégorie")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows="500", cols=str(max(5, len(headers))))
        ws.update([headers])
    return ws

if sh:
    # On s'assure que toutes les feuilles existent avec la bonne structure
    ensure_worksheet_exists(sh, "Garde", ["Date", "Parent"])
    ensure_worksheet_exists(sh, "Notes", ["Date", "Parent", "Texte"])
    ensure_worksheet_exists(sh, "Activites", ["Date Début", "Date Fin", "Type", "Description", "Parent en charge"])
    ensure_worksheet_exists(sh, "Frais", ["Date", "Payé par", "Montant (€)", "Description", "Remboursé", "Catégorie"])
    ensure_worksheet_exists(sh, "FraisRecurrents", ["Description", "Payé par", "Montant (€)", "Catégorie", "Jour du mois"])

# --- FONCTIONS POUR LIRE ET ÉCRIRE ---
def get_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors de la lecture de la feuille {sheet_name} : {e}")
        return pd.DataFrame()

def save_full_df(sheet_name, df):
    try:
        worksheet = sh.worksheet(sheet_name)
        worksheet.clear()
        # On réécrit les colonnes + les données
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde de {sheet_name} : {e}")

def append_row(sheet_name, row_list):
    try:
        worksheet = sh.worksheet(sheet_name)
        worksheet.append_row(row_list, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error(f"Erreur lors de l'ajout d'une ligne dans {sheet_name} : {e}")

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="App de Garde Alternée", page_icon="👨‍👩‍👧", layout="wide")

# Injection de styles CSS globaux pour un rendu premium
style_global = textwrap.dedent("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        text-align: center;
        font-weight: 800;
        font-size: 2.8em;
        background: linear-gradient(135deg, #1e3a8a, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
    .subtitle {
        text-align: center;
        color: #64748b;
        font-size: 1.1em;
        margin-bottom: 25px;
    }
    
    /* Onglets stylisés */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        justify-content: center;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f1f5f9;
        border-radius: 10px;
        color: #475569;
        font-weight: 600;
        padding: 40px 25px;
        min-width: 150px;
        transition: all 0.3s ease;
        border: none;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e2e8f0;
        color: #1e293b;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: white !important;
        box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3);
    }
    </style>
""")
st.markdown(style_global, unsafe_allow_html=True)

st.markdown('<h1 class="main-title">👨‍👩‍👧 Coparentalité sereine</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Votre espace partagé d\'agenda, d\'activités et de dépenses</p>', unsafe_allow_html=True)

# --- PARAMÈTRES (SIDEBAR) ---
st.sidebar.markdown("""
<div style='text-align: center; margin-bottom: 15px;'>
    <h2 style='font-weight: 800; color: #1e3a8a; margin: 0;'>⚙️ Paramètres</h2>
</div>
""", unsafe_allow_html=True)

nom_p1 = st.sidebar.text_input("Prénom du parent 1", "Papa")
nom_p2 = st.sidebar.text_input("Prénom du parent 2", "Maman")

st.sidebar.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
st.sidebar.markdown("<h3 style='font-weight: 600; font-size: 1.1em; margin-bottom: 5px;'>🔄 Roulement de garde</h3>", unsafe_allow_html=True)
nouvelle_ref = st.sidebar.date_input("Vendredi de référence", value=date(2026, 5, 15))
parent_reprise = st.sidebar.radio("Qui commence ce vendredi ?", [nom_p1, nom_p2])

# --- CHARGEMENT DES DONNÉES DEPUIS LE CLOUD ---
if sh:
    # 1. exceptions de garde
    df_exceptions = get_data("Garde")
    if df_exceptions.empty or 'Date' not in df_exceptions.columns: 
        df_exceptions = pd.DataFrame(columns=["Date", "Parent"])
        
    # 2. notes et mémos
    df_notes = get_data("Notes")
    if df_notes.empty or 'Date' not in df_notes.columns: 
        df_notes = pd.DataFrame(columns=["Date", "Parent", "Texte"])
        
    # 3. activités et rendez-vous
    df_activites = get_data("Activites")
    if df_activites.empty or 'Date Début' not in df_activites.columns: 
        df_activites = pd.DataFrame(columns=["Date Début", "Date Fin", "Type", "Description", "Parent en charge"])
        
    # 4. frais et dépenses
    df_frais = get_data("Frais")
    if df_frais.empty or 'Date' not in df_frais.columns: 
        df_frais = pd.DataFrame(columns=["Date", "Payé par", "Montant (€)", "Description", "Remboursé", "Catégorie"])
    else:
        # Migration automatique de la colonne Catégorie
        if "Catégorie" not in df_frais.columns:
            df_frais["Catégorie"] = "Autre 🪙"
        else:
            df_frais["Catégorie"] = df_frais["Catégorie"].fillna("Autre 🪙").astype(str).replace("", "Autre 🪙")
            
        if "Remboursé" not in df_frais.columns:
            df_frais["Remboursé"] = False
        else:
            df_frais["Remboursé"] = df_frais["Remboursé"].astype(str).str.upper() == "TRUE"
            
    # 5. frais récurrents
    df_recurrents = get_data("FraisRecurrents")
    if df_recurrents.empty or 'Description' not in df_recurrents.columns:
        df_recurrents = pd.DataFrame(columns=["Description", "Payé par", "Montant (€)", "Catégorie", "Jour du mois"])
else:
    st.stop() # On arrête si la connexion échoue

# --- DÉTERMINATION DE LA GARDE POUR UNE DATE DONNÉE ---
def obtenir_garde_parent(date_cible):
    d_str = str(date_cible)
    exc = df_exceptions[df_exceptions['Date'].astype(str) == d_str]
    if not exc.empty:
        return exc.iloc[0]['Parent'], True # (Parent, Est une exception)
    else:
        diff = (date_cible - nouvelle_ref).days
        p_a = parent_reprise
        p_b = nom_p2 if parent_reprise == nom_p1 else nom_p1
        nom_g = p_a if (diff // 7) % 2 == 0 else p_b
        return nom_g, False

# =========================================================================
# 📅 BANDEAU HEBDOMADAIRE PERSISTANT "EN UN COUP D'ŒIL" (TOUS LES ONGLETS)
# =========================================================================
st.markdown("<h4 style='font-weight: 600; color: #475569; margin-bottom: 10px;'>⚡ Cette semaine en un coup d'œil</h4>", unsafe_allow_html=True)

# Détermination des 7 jours de la semaine courante (lundi à dimanche)
aujourdhui = date.today()
lundi = aujourdhui - timedelta(days=aujourdhui.weekday())
jours_semaine = [lundi + timedelta(days=i) for i in range(7)]
noms_jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

# Affichage des 7 colonnes pour le bandeau
cols_bandeau = st.columns(7)

# CSS pour le bandeau
style_bandeau = textwrap.dedent("""
    <style>
    .bandeau-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        border: 1px solid #e2e8f0;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .bandeau-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.06);
    }
    .bandeau-today {
        border: 2px solid #3b82f6 !important;
        background: linear-gradient(135deg, #eff6ff, #dbeafe) !important;
    }
    .bandeau-day-name {
        font-size: 0.8em;
        font-weight: bold;
        color: #64748b;
        text-transform: uppercase;
        margin-bottom: 2px;
    }
    .bandeau-day-num {
        font-size: 1.3em;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 8px;
    }
    .badge-p1 {
        background-color: #dbeafe;
        color: #1e40af;
        font-size: 0.75em;
        font-weight: bold;
        padding: 2px 8px;
        border-radius: 12px;
        display: inline-block;
    }
    .badge-p2 {
        background-color: #d1fae5;
        color: #065f46;
        font-size: 0.75em;
        font-weight: bold;
        padding: 2px 8px;
        border-radius: 12px;
        display: inline-block;
    }
    .badge-exc {
        background-color: #fef3c7;
        color: #92400e;
        font-size: 0.75em;
        font-weight: bold;
        padding: 2px 8px;
        border-radius: 12px;
        border: 1px dashed #d97706;
        display: inline-block;
    }
    .bandeau-act {
        font-size: 0.7em;
        background: #f8fafc;
        border-left: 3px solid #3b82f6;
        padding: 2px 4px;
        margin-top: 4px;
        border-radius: 3px;
        text-align: left;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    </style>
""")
st.markdown(style_bandeau, unsafe_allow_html=True)

for idx, jour_date in enumerate(jours_semaine):
    d_str = str(jour_date)
    parent_g, est_exception = obtenir_garde_parent(jour_date)
    
    # Classes CSS
    card_class = "bandeau-card"
    if jour_date == aujourdhui:
        card_class += " bandeau-today"
        
    badge_class = "badge-p1" if parent_g == nom_p1 else "badge-p2"
    if est_exception:
        badge_class = "badge-exc"
        
    # Activités du jour
    acts_html = ""
    for _, act in df_activites.iterrows():
        try:
            if str(act['Date Début']) <= d_str <= str(act['Date Fin']):
                acts_html += f'<div class="bandeau-act" title="{act["Description"]}">📌 {act["Description"]}</div>'
        except:
            pass
            
    # Construction de la chaîne HTML sans aucun retrait/indentation multiligne
    html_col = f'<div class="{card_class}">' \
               f'<div class="bandeau-day-name">{noms_jours[idx]}</div>' \
               f'<div class="bandeau-day-num">{jour_date.day}</div>' \
               f'<span class="{badge_class}">{parent_g}</span>' \
               f'<div style="margin-top: 6px;">{acts_html}</div>' \
               f'</div>'
               
    cols_bandeau[idx].markdown(html_col, unsafe_allow_html=True)

st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)

# --- ONGLETS PRINCIPAUX ---
tab1, tab2, tab3 = st.tabs(["📅 Garde & Notes", "⚽ Activités & Agenda", "💰 Frais & Budget"])

# =========================================================================
# ONGLET 1 : GARDE & NOTES (CALENDRIER MENSUEL PREMIUM)
# =========================================================================
with tab1:
    st.header("📅 Calendrier Mensuel")
    
    col_m1, col_m2 = st.columns(2)
    
    with col_m1.expander("🔄 Ajouter une exception de garde"):
        d_deb = st.date_input("Début", key="ex_deb")
        d_fin = st.date_input("Fin", value=d_deb, key="ex_fin")
        p_ex = st.selectbox("Garde pour", [nom_p1, nom_p2], key="ex_p")
        if st.button("Enregistrer l'exception", use_container_width=True):
            delta = d_fin - d_deb
            for i in range(delta.days + 1):
                append_row("Garde", [str(d_deb + timedelta(days=i)), p_ex])
            st.toast("Exception de garde enregistrée avec succès !", icon="✅")
            st.rerun()

    with col_m2.expander("✍️ Ajouter une note / mémo"):
        d_note = st.date_input("Date", key="n_date")
        p_note = st.selectbox("Auteur", [nom_p1, nom_p2], key="n_p")
        t_note = st.text_input("Texte", key="n_t", placeholder="Ex : Réunion parents-profs à 18h")
        if st.button("Enregistrer la note", use_container_width=True) and t_note:
            append_row("Notes", [str(d_note), p_note, t_note])
            st.toast("Note enregistrée !", icon="📝")
            st.rerun()

    # --- FILTRE ET CHOIX DU MOIS ---
    col_mois, col_annee = st.columns(2)
    noms_mois = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    m_choisi = col_mois.selectbox("Mois", range(1, 13), index=date.today().month-1, format_func=lambda x: noms_mois[x-1])
    a_choisie = col_annee.selectbox("Année", range(2025, 2029), index=1)
    
    cal = calendar.monthcalendar(a_choisie, m_choisi)
    
    # CSS du calendrier mensuel premium
    style_calendrier = textwrap.dedent("""
        <style>
        .cal-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 8px;
            text-align: center;
        }
        .cal-table th {
            padding: 12px;
            font-weight: 700;
            color: #475569;
            text-transform: uppercase;
            font-size: 0.85em;
            border-bottom: 2px solid #e2e8f0;
        }
        .cal-table td {
            height: 125px;
            width: 14%;
            background: #ffffff;
            border-radius: 16px;
            border: 1px solid #f1f5f9;
            vertical-align: top;
            padding: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.01);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .cal-table td:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 18px rgba(0,0,0,0.06);
            background: #fafafa;
        }
        .jour-num-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 800;
            font-size: 1.1em;
            color: #0f172a;
        }
        .note-badge {
            background: #fef3c7;
            color: #d97706;
            font-size: 0.7em;
            padding: 1px 4px;
            border-radius: 6px;
            border: 1px solid #fde68a;
        }
        
        /* Styles des parents sur le calendrier mensuel */
        .cal-garde-p1 {
            background: linear-gradient(135deg, #e3f2fd, #bbdefb);
            color: #1e3a8a;
            border: 1px solid #90caf9;
            border-radius: 8px;
            padding: 4px 6px;
            font-size: 0.8em;
            font-weight: bold;
            margin-top: 6px;
            text-align: center;
        }
        .cal-garde-p2 {
            background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
            color: #065f46;
            border: 1px solid #a5d6a7;
            border-radius: 8px;
            padding: 4px 6px;
            font-size: 0.8em;
            font-weight: bold;
            margin-top: 6px;
            text-align: center;
        }
        .cal-exception {
            background: linear-gradient(135deg, #fff3e0, #ffe0b2);
            color: #92400e;
            border: 2px dashed #f59e0b;
            border-radius: 8px;
            padding: 4px 6px;
            font-size: 0.8em;
            font-weight: 800;
            margin-top: 6px;
            text-align: center;
        }
        .cal-act-badge {
            background-color: #f8fafc;
            font-size: 0.75em;
            margin-top: 4px;
            text-align: left;
            padding: 3px 5px;
            border-radius: 5px;
            border-left: 3px solid #3b82f6;
            color: #334155;
            font-weight: 500;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        </style>
    """)
    st.markdown(style_calendrier, unsafe_allow_html=True)

    html_cal = '<table class="cal-table"><tr><th>Lundi</th><th>Mardi</th><th>Mercredi</th><th>Jeudi</th><th>Vendredi</th><th>Samedi</th><th>Dimanche</th></tr>'

    for semaine in cal:
        html_cal += "<tr>"
        for jour in semaine:
            if jour == 0:
                html_cal += '<td style="background:transparent; border:none; box-shadow:none;"></td>'
            else:
                d_obj = date(a_choisie, m_choisi, jour)
                d_str = str(d_obj)
                
                # Vérification des notes
                has_note = d_str in df_notes['Date'].astype(str).values
                note_indicator = '<span class="note-badge" title="Memo enregistré">📝 Memo</span>' if has_note else ""
                
                # Détermination de la garde
                parent_g, est_exception = obtenir_garde_parent(d_obj)
                
                if est_exception:
                    cl_parent = "cal-exception"
                else:
                    cl_parent = "cal-garde-p1" if parent_g == nom_p1 else "cal-garde-p2"
                
                # Activités
                acts_html = ""
                for _, act in df_activites.iterrows():
                    try:
                        if str(act['Date Début']) <= d_str <= str(act['Date Fin']):
                            acts_html += f'<div class="cal-act-badge" title="{act["Description"]}">📌 {act["Description"]}</div>'
                    except:
                        pass
                
                # Construction sur une seule ligne
                html_cal += f'<td>' \
                            f'<div class="jour-num-container"><span>{jour}</span>{note_indicator}</div>' \
                            f'<div class="{cl_parent}">{parent_g}</div>' \
                            f'<div style="margin-top: 5px; max-height: 70px; overflow-y: auto;">{acts_html}</div>' \
                            f'</td>'
        html_cal += "</tr>"
    html_cal += "</table>"
    st.markdown(html_cal, unsafe_allow_html=True)

    # --- AFFICHAGE ET GESTION DES NOTES ---
    st.markdown("<h3 style='font-weight: 700; margin-top: 30px;'>📝 Mémos et Notes du mois</h3>", unsafe_allow_html=True)
    
    # Filtrer les notes pour le mois affiché
    df_notes['Date'] = pd.to_datetime(df_notes['Date']).dt.date
    debut_mois = date(a_choisie, m_choisi, 1)
    fin_mois = date(a_choisie, m_choisi, calendar.monthrange(a_choisie, m_choisi)[1])
    df_notes_mois = df_notes[(df_notes['Date'] >= debut_mois) & (df_notes['Date'] <= fin_mois)]
    
    col_n1, col_n2 = st.columns(2)
    with col_n1:
        st.markdown(f"<div class='badge-p1' style='font-size:1.1em; padding:5px 15px;'>Mémos de {nom_p1}</div>", unsafe_allow_html=True)
        notes_p1 = df_notes_mois[df_notes_mois['Parent'] == nom_p1]
        if not notes_p1.empty:
            for index, n in notes_p1.iterrows():
                with st.chat_message("user"):
                    st.write(f"📅 **{n['Date']}** : {n['Texte']}")
                    if st.button("🗑️", key=f"del_note_{index}"):
                        # Suppression
                        df_notes = get_data("Notes")
                        df_notes = df_notes.drop(index)
                        save_full_df("Notes", df_notes)
                        st.toast("Mémo supprimé !")
                        st.rerun()
        else:
            st.caption("Aucun mémo ce mois-ci.")
            
    with col_n2:
        st.markdown(f"<div class='badge-p2' style='font-size:1.1em; padding:5px 15px;'>Mémos de {nom_p2}</div>", unsafe_allow_html=True)
        notes_p2 = df_notes_mois[df_notes_mois['Parent'] == nom_p2]
        if not notes_p2.empty:
            for index, n in notes_p2.iterrows():
                with st.chat_message("assistant"):
                    st.write(f"📅 **{n['Date']}** : {n['Texte']}")
                    if st.button("🗑️", key=f"del_note_{index}"):
                        # Suppression
                        df_notes = get_data("Notes")
                        df_notes = df_notes.drop(index)
                        save_full_df("Notes", df_notes)
                        st.toast("Mémo supprimé !")
                        st.rerun()
        else:
            st.caption("Aucun mémo ce mois-ci.")

# =========================================================================
# ONGLET 2 : ACTIVITÉS & AGENDA
# =========================================================================
with tab2:
    st.header("⚽ Activités & Rendez-vous des enfants")
    
    with st.expander("➕ Ajouter une nouvelle activité"):
        with st.form("add_act", clear_on_submit=True):
            c1, c2 = st.columns(2)
            d1 = c1.date_input("Du", key="act_d1")
            d2 = c2.date_input("Au", value=d1, key="act_d2")
            t = st.selectbox("Type", ["🏫 École", "⚽ Sport", "🩺 Médical", "🎨 Loisirs", "🪙 Autre"])
            desc = st.text_input("Description / Intitulé", placeholder="Ex : Camp louveteaux,")
            resp = st.radio("Parent en charge", [nom_p1, nom_p2, "Les deux"])
            
            if st.form_submit_button("Ajouter à l'agenda", use_container_width=True):
                if desc:
                    append_row("Activites", [str(d1), str(d2), t, desc, resp])
                    st.toast("Activité ajoutée !", icon="⚽")
                    st.rerun()
                else:
                    st.error("Veuillez renseigner une description !")
    
    st.subheader("📋 Liste de toutes les activités")
    st.info("💡 Vous pouvez double-cliquer sur les cellules pour corriger ou modifier directement l'agenda ci-dessous. Pensez à enregistrer après !")
    edited_act = st.data_editor(df_activites, num_rows="dynamic", use_container_width=True)
    if st.button("Enregistrer les modifications d'activités", use_container_width=True):
        save_full_df("Activites", edited_act)
        st.toast("Agenda mis à jour !")
        st.rerun()

# =========================================================================
# ONGLET 3 : FRAIS & BUDGET (SANS SOUS-ONGLETS, COMPLET & ASSAINI)
# =========================================================================
with tab3:
    st.header("💰 Dépenses communes et Remboursements")

    # --- BOUTON DE GÉNÉRATION DES FRAIS RÉCURRENTS (Optionnel, dans un expander discret) ---
    if not df_recurrents.empty:
        with st.expander("🔄 Générer les charges récurrentes du mois", expanded=False):
            mois_courant_nom = noms_mois[date.today().month - 1]
            st.write(f"Ajoutez automatiquement les charges pré-configurées dans votre feuille Google Sheet **FraisRecurrents** pour le mois de {mois_courant_nom} {date.today().year}.")
            if st.button(f"🚀 Générer les frais récurrents pour {mois_courant_nom}", use_container_width=True):
                df_frais_frais = get_data("Frais")
                frais_ajoutes_count = 0
                
                for _, rec_row in df_recurrents.iterrows():
                    try:
                        jour_frais = int(rec_row['Jour du mois'])
                        date_operation = date(date.today().year, date.today().month, jour_frais)
                        description_operation = f"[Récurrent] {rec_row['Description']}"
                        montant_operation = str(rec_row['Montant (€)']).replace('.', ',')
                        payeur_operation = rec_row['Payé par']
                        cat_operation = rec_row.get('Catégorie', 'Autre 🪙')
                        
                        if not df_frais_frais.empty:
                            doublon = df_frais_frais[
                                (df_frais_frais['Date'].astype(str) == str(date_operation)) & 
                                (df_frais_frais['Description'].astype(str) == description_operation)
                            ]
                        else:
                            doublon = pd.DataFrame()
                            
                        if doublon.empty:
                            append_row("Frais", [str(date_operation), payeur_operation, montant_operation, description_operation, False, cat_operation])
                            frais_ajoutes_count += 1
                    except Exception as ex:
                        pass
                
                if frais_ajoutes_count > 0:
                    st.toast(f"{frais_ajoutes_count} frais récurrents ont été générés !", icon="🚀")
                else:
                    st.toast("Aucun frais généré : tout est déjà à jour !", icon="✨")
                st.rerun()

    # --- Formulaire d'ajout d'une opération ---
    with st.expander("➕ Ajouter une nouvelle opération", expanded=True):
        with st.form("add_frais", clear_on_submit=True):
            type_op = st.radio("Type d'opération :", [
                "🔴 Dépense (Achat commun à diviser)", 
                "🟢 Rentrée d'argent (Remboursement tiers, mutuelle...)",
                "🔄 Virement de remboursement (D'un parent à l'autre)"
            ], horizontal=True)
            
            c1, c2 = st.columns(2)
            dfra = c1.date_input("Date de l'opération")
            payeur = c2.selectbox("Payé / Reçu par :", [nom_p1, nom_p2])
            
            c3, c4 = st.columns(2)
            montant_str = c3.text_input("Montant (€) - Ex: 12.50", value="")
            
            # Catégories conformes
            cat_choisie = c4.selectbox("Catégorie :", [
                "🏫 École",
                "🩺 Santé",
                "⚽ Loisirs & Activités",
                "👕 Habillement",
                "🚗 Transports",
                "🪙 Autre"
            ])
            
            descf = st.text_input("Objet / Description de la dépense")
            
            if st.form_submit_button("Enregistrer l'opération", use_container_width=True):
                if montant_str and descf:
                    montant_pour_sheets = montant_str.replace('.', ',')
                    
                    if "🟢" in type_op:
                        montant_pour_sheets = "-" + montant_pour_sheets.replace('-', '')
                    elif "🔄" in type_op:
                        descf = f"🔄 VIREMENT : {descf}"
                        
                    append_row("Frais", [str(dfra), payeur, montant_pour_sheets, descf, False, cat_choisie])
                    st.toast("Opération enregistrée avec succès !", icon="💰")
                    st.rerun()
                else:
                    st.error("⚠️ Veuillez saisir un montant et une description valide !")

    # Nettoyage et préparation des données
    total_du_p1 = 0.0
    total_du_p2 = 0.0
    
    if not df_frais.empty:
        df_frais.columns = df_frais.columns.str.strip()
        
        # Fonction robuste pour nettoyer les prix
        def clean_price(val):
            v = str(val).replace(',', '.')
            if '(' in v and ')' in v:
                v = '-' + v.replace('(', '').replace(')', '')
            v = v.replace('€', '').replace(' ', '').replace('\xa0', '')
            v = v.replace('−', '-').replace('—', '-')
            try:
                return float(v)
            except:
                return 0.0

        df_frais['Montant (€)'] = df_frais['Montant (€)'].apply(clean_price)
        
        # Copie pour les graphiques avant modification
        df_non_remb = df_frais[~df_frais['Remboursé']].copy()
        
        # Calcul des dettes
        for index, row in df_frais.iterrows():
            montant_total = float(row['Montant (€)'])
            moitie = abs(montant_total) / 2
            payeur_nom = row['Payé par']
            autre_parent = nom_p2 if payeur_nom == nom_p1 else nom_p1
            est_rembourse = row['Remboursé']
            description = str(row['Description'])
            
            if not est_rembourse:
                if "🔄 VIREMENT" in description:
                    if payeur_nom == nom_p1:
                        total_du_p2 += abs(montant_total)
                    else:
                        total_du_p1 += abs(montant_total)
                else:
                    if montant_total > 0: 
                        if payeur_nom == nom_p1:
                            total_du_p2 += moitie
                        else:
                            total_du_p1 += moitie
                    elif montant_total < 0: 
                        if payeur_nom == nom_p1:
                            total_du_p1 += moitie
                        else:
                            total_du_p2 += moitie

        # =========================================================================
        # 📊 LE SUPER TABLEAU DE BORD INTERACTIF (PLOTLY)
        # =========================================================================
        st.markdown("<h3 style='font-weight: 800; color: #1e3a8a; margin-top:25px;'>📊 Analyse du budget commun</h3>", unsafe_allow_html=True)
        
        col_chart1, col_chart2 = st.columns(2)
        
        # 1. Graphique en Donut des catégories
        with col_chart1:
            df_dep = df_non_remb[(df_non_remb['Montant (€)'] > 0) & (~df_non_remb['Description'].str.contains("🔄 VIREMENT"))]
            
            if not df_dep.empty:
                df_grouped = df_dep.groupby('Catégorie', as_index=False)['Montant (€)'].sum()
                
                fig_donut = px.pie(
                    df_grouped, 
                    values='Montant (€)', 
                    names='Catégorie', 
                    hole=0.45,
                    title="💰 Répartition des dépenses en cours par catégorie",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_donut.update_traces(textinfo='percent+label', pull=[0.02]*len(df_grouped))
                fig_donut.update_layout(
                    showlegend=False, 
                    margin=dict(t=40, b=0, l=0, r=0),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("Aucune dépense en cours pour le graphique par catégorie.")
        
        # 2. Graphique comparatif des contributions totales
        with col_chart2:
            df_dep_all = df_non_remb[(df_non_remb['Montant (€)'] > 0) & (~df_non_remb['Description'].str.contains("🔄 VIREMENT"))]
            
            if not df_dep_all.empty:
                df_contrib = df_dep_all.groupby('Payé par', as_index=False)['Montant (€)'].sum()
                
                fig_bar = px.bar(
                    df_contrib,
                    x='Payé par',
                    y='Montant (€)',
                    title="⚖️ Total dépensé par parent (Achats communs)",
                    labels={'Payé par': 'Parent', 'Montant (€)': 'Total Dépensé (€)'},
                    color='Payé par',
                    color_discrete_map={nom_p1: '#3b82f6', nom_p2: '#10b981'}
                )
                fig_bar.update_layout(
                    showlegend=False,
                    margin=dict(t=40, b=20, l=20, r=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Aucune contribution enregistrée.")

        st.markdown("---")

        # --- LISTE DES OPÉRATIONS ---
        st.subheader("📋 Liste des opérations en cours / validées")
        
        for index, row in df_frais.iterrows():
            montant_total = float(row['Montant (€)'])
            moitie = abs(montant_total) / 2
            payeur_nom = row['Payé par']
            autre_parent = nom_p2 if payeur_nom == nom_p1 else nom_p1
            est_rembourse = row['Remboursé']
            description = str(row['Description'])
            categorie = row.get('Catégorie', 'Autre 🪙')
            
            with st.container():
                col1, col2, col3, col4 = st.columns([1, 2, 3, 1])
                
                barre = "~~" if est_rembourse else "" 
                
                col1.write(f"📅 {row['Date']}")
                col1.markdown(f"<span style='font-size:0.85em; background:#f1f5f9; padding:2px 8px; border-radius:10px; color:#475569;'>{categorie}</span>", unsafe_allow_html=True)
                
                desc_propre = description.replace("🔄 VIREMENT : ", "")
                col2.write(f"{barre}**{desc_propre}**{barre}")
                
                if "🔄 VIREMENT" in description:
                    texte_detail = f"🔄 Virement de {abs(montant_total):.2f} €  \n👉 *De {payeur_nom} vers {autre_parent}*"
                elif montant_total >= 0:
                    texte_detail = f"🔴 Achat de {montant_total:.2f} € par {payeur_nom}  \n👉 *{autre_parent} doit {moitie:.2f} €*"
                else:
                    texte_detail = f"🟢 Reçu {abs(montant_total):.2f} € par {payeur_nom}  \n👉 *{payeur_nom} doit {moitie:.2f} € à {autre_parent}*"
                    
                col3.write(f"{barre}{texte_detail}{barre}")
                
                with col4:
                    c_act1, c_act2 = st.columns(2)
                    
                    if not est_rembourse:
                        bouton_titre = "🤝" if "🔄 VIREMENT" in description else "✅"
                        help_txt = "Valider la réception" if "🔄 VIREMENT" in description else "Valider le règlement"
                            
                        if c_act1.button(bouton_titre, key=f"remb_{index}", help=help_txt):
                            df_frais.at[index, 'Remboursé'] = True
                            save_full_df("Frais", df_frais)
                            st.toast("Règlement validé !")
                            st.rerun()
                    else:
                        c_act1.write("✔️ Validé") 
                        
                    if c_act2.button("🗑️", key=f"del_{index}", help="Supprimer cette ligne"):
                        df_frais = df_frais.drop(index)
                        save_full_df("Frais", df_frais)
                        st.toast("Opération supprimée !")
                        st.rerun()
            
            st.divider()
    else:
        st.info("Aucune dépense enregistrée.")

    # --- LE BILAN FINANCIER ---
    st.subheader("⚖️ Bilan financier global (Solde final)")
    st.write("Calcul instantané de la balance, achats et virements inclus :")
    
    diff_nette = total_du_p1 - total_du_p2
    
    col_sb1, col_sb2, col_sb3 = st.columns(3)
    col_sb1.metric(f"Dettes cumulées de {nom_p1}", f"{total_du_p1:.2f} €")
    col_sb2.metric(f"Dettes cumulées de {nom_p2}", f"{total_du_p2:.2f} €")
    
    if diff_nette > 0:
        col_sb3.error(f"💸 Finalement : **{nom_p1}** doit verser **{diff_nette:.2f} €** à {nom_p2}")
    elif diff_nette < 0:
        col_sb3.error(f"💸 Finalement : **{nom_p2}** doit verser **{abs(diff_nette):.2f} €** à {nom_p1}")
    else:
        if total_du_p1 == 0 and total_du_p2 == 0:
            col_sb3.success("✅ Tout est parfaitement réglé, aucun parent ne doit rien !")
        else:
            col_sb3.success("✅ Équilibre parfait ! (0 € de différence)")
