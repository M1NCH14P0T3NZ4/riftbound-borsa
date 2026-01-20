import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re
import time

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Intelligence", page_icon="📈", layout="wide")

# --- CONNESSIONE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Errore Secrets!")
    st.stop()

if "user" not in st.session_state: st.session_state.user = None

# --- FUNZIONI AUTH ---
def login_user(e, p):
    try:
        res = supabase.auth.sign_in_with_password({"email": e, "password": p})
        st.session_state.user = res.user
        st.rerun()
    except: st.error("Credenziali errate.")

def signup_user(e, p):
    try:
        supabase.auth.sign_up({"email": e, "password": p})
        st.info("Registrazione inviata! Conferma la mail (se richiesto) e accedi.")
    except Exception as ex: st.error(f"Errore: {ex}")

# --- LOGIN WALL ---
if st.session_state.user is None:
    st.title("🛡️ Accesso Piattaforma")
    t1, t2 = st.tabs(["Login", "Registrati"])
    with t1:
        e = st.text_input("Email")
        p = st.text_input("Password", type="password")
        if st.button("Entra"): login_user(e, p)
    with t2:
        ne = st.text_input("Nuova Email")
        np = st.text_input("Nuova Password", type="password")
        if st.button("Crea Account"): signup_user(ne, np)
    st.stop()

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def get_base_data():
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    # Pulizia nomi per ricerca facilitata nel bulk import
    df_c['name_clean'] = df_c['name'].str.lower().str.replace(r'[^a-z0-9]', '', regex=True)
    
    p_res = supabase.table("card_prices").select("*").eq("language", "EN").order("recorded_at", desc=True).limit(2000).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty: df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
    return df_c, df_p

def get_history(cid):
    res = supabase.table("card_prices").select("*").eq("card_id", cid).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty: df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

df_cards, df_market = get_base_data()

# --- SIDEBAR ---
with st.sidebar:
    st.write(f"👤 `{st.session_state.user.email}`")
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
    st.divider()
    sel_set = st.selectbox("Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
    f_cards = df_cards if sel_set == "Tutti" else df_cards[df_cards['set_code'] == sel_set]
    sel_card_display = st.selectbox("Cerca Carta:", sorted(f_cards['display_name'].unique()))
    sel_lang = st.radio("Mercato:", ["EN", "CN"])

c_info = df_cards[df_cards['display_name'] == sel_card_display].iloc[0]
c_id = c_info['card_id']

# --- DASHBOARD ---
st.title("💹 Riftbound Market Watch")
t1, t2, t3 = st.tabs(["🔍 Dettaglio & IA", "🌍 Mercato", "🎒 La mia Collezione"])

with t1:
    col_a, col_b = st.columns([1, 2.5])
    df_h = get_history(c_id)
    df_l = df_h[df_h['language'] == sel_lang] if not df_h.empty else pd.DataFrame()
    with col_a:
        st.image(c_info['image_url'], width='stretch')
        if not df_l.empty:
            lp, lt = float(df_l.iloc[-1]['price_low']), float(df_l.iloc[-1]['price_trend'])
            st.subheader("🤖 Segnale IA")
            if lp > lt * 1.15: st.warning(f"⚠️ SOPRAVALUTATA (+{round(((lp/lt)-1)*100)}%)")
            elif lp < lt * 0.85: st.success(f"🔥 OCCASIONE (-{round((1-(lp/lt))*100)}%)")
            else: st.info("⚖️ STABILE")
    with col_b:
        if not df_l.empty:
            temp = df_l[['recorded_at', 'price_low', 'price_trend']].copy()
            mlt = temp.melt(id_vars=['recorded_at'], value_vars=['price_low', 'price_trend'], var_name='Metric', value_name='Euro')
            mlt['Metric'] = mlt['Metric'].map({'price_low': 'Prezzo', 'price_trend': 'Trend (7g)'})
            fig = px.line(mlt, x="recorded_at", y="Euro", color="Metric", markers=True, template="plotly_dark",
                         color_discrete_map={'Prezzo': "#00CC96", 'Trend (7g)': "#FFA15A"})
            fig.update_layout(hovermode="x unified", xaxis_title=None, margin=dict(t=0))
            st.plotly_chart(fig, width='stretch')

with t2:
    if not df_market.empty:
        latest = df_market.sort_values('recorded_at').groupby('card_id').last().reset_index()
        st.metric("Valore Totale Set (1x EN)", f"{round(latest['price_low'].sum(), 2)} €")

# --- TAB 3: LA MIA COLLEZIONE (CORRETTA) ---
with t3:
    st.header("🎒 Gestione Raccoglitore")
    
    # 1. IMPORTAZIONE MASSIVA (FIXATA)
    with st.expander("📥 Importazione Rapida (Copia-Incolla nomi)"):
        st.write("Incolla un elenco di nomi (uno per riga).")
        txt_in = st.text_area("Elenco carte:", height=150, placeholder="Darius, Trifarian\nAcceptable Losses...")
        if st.button("Esegui Importazione"):
            lines = [l.strip() for l in txt_in.split("\n") if l.strip()]
            success, error_list = 0, []
            for name in lines:
                # Pulizia nome per ricerca flessibile
                clean_search = re.sub(r'[^a-z0-9]', '', name.lower())
                match = df_cards[(df_cards['name_clean'] == clean_search) & (df_cards['is_showcase'] == False)]
                
                if not match.empty:
                    tid = match.iloc[0]['card_id']
                    try:
                        supabase.table("user_collections").upsert(
                            {"user_id": st.session_state.user.id, "card_id": tid, "quantity": 1},
                            on_conflict="user_id,card_id"
                        ).execute()
                        success += 1
                    except Exception as e:
                        error_list.append(f"{name} (Errore DB)")
                else:
                    error_list.append(f"{name} (Non trovata)")
            
            if success > 0: st.success(f"Aggiunte {success} carte!")
            if error_list: st.error(f"Problemi con: {', '.join(error_list)}")
            time.sleep(1)
            st.rerun()

    # 2. MODIFICA SINGOLA (FIXATA)
    st.subheader(f"Modifica: {sel_card_display}")
    col_q, col_p = st.columns(2)
    with col_q: q = st.number_input("Quantità", min_value=0, step=1)
    with col_p: bp = st.number_input("Prezzo d'acquisto unitario (€)", min_value=0.0)
    
    if st.button("💾 Salva nel Portfolio"):
        try:
            # Specifichiamo on_conflict per evitare l'errore RLS/Unique
            supabase.table("user_collections").upsert({
                "user_id": st.session_state.user.id, 
                "card_id": c_id, 
                "quantity": int(q), 
                "purchase_price": float(bp)
            }, on_conflict="user_id,card_id").execute()
            st.success("Portfolio aggiornato!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Errore tecnico: {e}")

    # 3. VISUALIZZAZIONE
    st.divider()
    my_data = supabase.table("user_collections").select("quantity, purchase_price, cards(name, rarity, is_showcase)").eq("user_id", st.session_state.user.id).execute().data
    if my_data:
        df_my = pd.DataFrame(my_data)
        df_my['Nome'] = df_my['cards'].apply(lambda x: f"{x['name']} (✨)" if x and x['is_showcase'] else (x['name'] if x else 'N/A'))
        df_my['Rarità'] = df_my['cards'].apply(lambda x: x['rarity'] if x else 'N/A')
        st.subheader("🖼️ La tua collezione")
        st.dataframe(df_my[['Nome', 'Rarità', 'quantity', 'purchase_price']], width='stretch', hide_index=True)
    else:
        st.info("Portfolio vuoto.")

st.caption("Riftbound Borsa v6.2 | Sistema protetto e privato")
