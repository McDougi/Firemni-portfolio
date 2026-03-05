import streamlit as st
import pandas as pd
import sqlite3
import yfinance as yf
import plotly.express as px

# --- NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="Firemní Portfolio", layout="wide")

# --- DATABÁZE (SQLITE) ---
def init_db():
    conn = sqlite3.connect('portfolio.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT, ticker TEXT, amount REAL, 
                  buy_price REAL, type TEXT, rent_or_interest REAL)''')
    conn.commit()
    return conn

conn = init_db()

# --- FUNKCE PRO CENY ---
@st.cache_data(ttl=3600) # Cena se aktualizuje jednou za hodinu, aby to bylo rychlé
def get_price(ticker):
    if not ticker or ticker == "-": return 0
    try:
        data = yf.Ticker(ticker)
        return data.history(period="1d")['Close'].iloc[-1]
    except: return 0

# --- POSTRANNÍ PANEL (VKLÁDÁNÍ) ---
st.sidebar.header("➕ Nová investice")
category = st.sidebar.selectbox("Typ aktiva", ["Akcie/Krypto", "Nemovitost (Přímá)", "Participace (Úrok)"])

with st.sidebar.form("input_form", clear_on_submit=True):
    name = st.text_input("Název investice")
    ticker = st.text_input("Ticker (např. BTC-USD, AAPL) - jen pro Akcie/Krypto")
    amount = st.number_input("Množství / Investovaná částka", min_value=0.0)
    buy_price = st.number_input("Nákupní cena (za kus / celková)", min_value=0.0)
    rent_interest = st.number_input("Měsíční nájem / Roční úrok %", min_value=0.0)
    
    submit = st.form_submit_button("Uložit do portfolia")
    if submit:
        conn.execute("INSERT INTO assets (name, ticker, amount, buy_price, type, rent_or_interest) VALUES (?,?,?,?,?,?)",
                     (name, ticker, amount, buy_price, category, rent_interest))
        conn.commit()
        st.rerun()

# --- DATA A VÝPOČTY ---
df = pd.read_sql_query("SELECT * FROM assets", conn)

if not df.empty:
    # Výpočet aktuální hodnoty
    prices = {t: get_price(t) for t in df['ticker'].unique() if t}
    
    def calculate_current(row):
        if row['type'] == "Akcie/Krypto" and row['ticker'] in prices:
            return prices[row['ticker']] * row['amount']
        return row['buy_price'] # U ostatních držíme nákupní cenu

    df['Aktuální Hodnota'] = df.apply(calculate_current, axis=1)

    # --- DASHBOARD ---
    st.title("📊 Firemní Portfolio Dashboard")
    
    total_val = df['Aktuální Hodnota'].sum()
    st.metric("CELKOVÁ HODNOTA PORTFOLIA", f"{total_val:,.2f}")

    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Rozložení majetku")
        fig = px.pie(df, values='Aktuální Hodnota', names='type', hole=0.5)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Seznam aktiv")
        st.dataframe(df[['name', 'type', 'Aktuální Hodnota']], use_container_width=True)

    # --- SEKCE SMAZAT (PRO ÚDRŽBU) ---
    st.divider()
    st.subheader("🗑️ Správa dat")
    asset_to_delete = st.selectbox("Vyberte aktivum ke smazání", df['name'].tolist())
    if st.button("Smazat vybrané"):
        conn.execute("DELETE FROM assets WHERE name = ?", (asset_to_delete,))
        conn.commit()
        st.warning(f"Aktivum {asset_to_delete} bylo odstraněno.")
        st.rerun()

else:
    st.title("Vítejte!")
    st.info("Zatím jste nezadali žádná data. Použijte formulář vlevo.")
