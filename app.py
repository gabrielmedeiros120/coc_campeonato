import streamlit as st
import sqlite3
import random
import pandas as pd

# ==============================
# BANCO DE DADOS
# ==============================
def init_db():
    conn = sqlite3.connect("camp.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT UNIQUE)''')

    c.execute('''CREATE TABLE IF NOT EXISTS matches (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 round INTEGER,
                 player1 TEXT,
                 player2 TEXT,
                 result TEXT)''')
    conn.commit()
    conn.close()

def add_players(players):
    conn = sqlite3.connect("camp.db")
    c = conn.cursor()
    for p in players:
        c.execute("INSERT OR IGNORE INTO players (name) VALUES (?)", (p,))
    conn.commit()
    conn.close()

def generate_rounds(players):
    n = len(players)
    rounds = []
    for i in range(n - 1):
        round_matches = []
        for j in range(n // 2):
            p1 = players[j]
            p2 = players[n - 1 - j]
            round_matches.append((p1, p2))
        players = [players[0]] + [players[-1]] + players[1:-1]
        rounds.append(round_matches)
    return rounds

def save_rounds(rounds):
    conn = sqlite3.connect("camp.db")
    c = conn.cursor()
    for r, matches in enumerate(rounds, 1):
        for p1, p2 in matches:
            c.execute("INSERT INTO matches (round, player1, player2, result) VALUES (?, ?, ?, ?)",
                      (r, p1, p2, None))
    conn.commit()
    conn.close()

# ==============================
# FUNÇÕES AUXILIARES
# ==============================
def get_matches(round_number=None):
    conn = sqlite3.connect("camp.db")
    c = conn.cursor()
    if round_number:
        c.execute("SELECT * FROM matches WHERE round = ?", (round_number,))
    else:
        c.execute("SELECT * FROM matches")
    matches = c.fetchall()
    conn.close()
    return matches

def update_result(match_id, result):
    conn = sqlite3.connect("camp.db")
    c = conn.cursor()
    c.execute("UPDATE matches SET result = ? WHERE id = ?", (result, match_id))
    conn.commit()
    conn.close()

def get_classification():
    conn = sqlite3.connect("camp.db")
    c = conn.cursor()
    c.execute("SELECT name FROM players")
    players = [row[0] for row in c.fetchall()]
    conn.close()

    scores = {p: 0 for p in players}
    matches = get_matches()

    for m in matches:
        _, _, p1, p2, result = m
        if result == "p1":
            scores[p1] += 3
        elif result == "p2":
            scores[p2] += 3
        elif result == "draw":
            scores[p1] += 1
            scores[p2] += 1

    df = pd.DataFrame(scores.items(), columns=["Jogador", "Pontos"])
    df = df.sort_values(by="Pontos", ascending=False).reset_index(drop=True)
    return df

# ==============================
# STREAMLIT APP
# ==============================
st.set_page_config(page_title="Campeonato do Clã", layout="centered")
st.title("🏆 Campeonato do Clã")

menu = ["Classificação", "Rodadas", "Cadastrar resultados"]
choice = st.sidebar.radio("Menu", menu)

if choice == "Classificação":
    st.header("Tabela de Classificação")

    df = get_classification()

    # Cores customizadas
    def row_style(row):
        idx = row.name
        if idx < 5:  # Top 5
            return ['background-color: {}'.format('#b6fcb6' if idx % 2 == 0 else '#d7fcd7')] * len(row)
        elif idx >= len(df) - 5:  # Últimos 5
            return ['background-color: {}'.format('#fcb6b6' if idx % 2 == 0 else '#fcd7d7')] * len(row)
        else:
            return [''] * len(row)

    # Medalhas top 3
    medalhas = ["🥇", "🥈", "🥉"] + [""] * (len(df) - 3)
    df.insert(0, "", medalhas)

    st.dataframe(df.style.apply(row_style, axis=1), use_container_width=True)

elif choice == "Rodadas":
    st.header("Rodadas")
    rounds = set([m[1] for m in get_matches()])
    for r in sorted(rounds):
        st.subheader(f"Rodada {r}")
        matches = get_matches(r)
        for m in matches:
            _, _, p1, p2, result = m
            res_text = "⏳ Em aberto"
            if result == "p1":
                res_text = f"✅ {p1} venceu"
            elif result == "p2":
                res_text = f"✅ {p2} venceu"
            elif result == "draw":
                res_text = "🤝 Empate"
            st.write(f"{p1} x {p2} → {res_text}")

elif choice == "Cadastrar resultados":
    st.header("Cadastrar resultados")
    matches = get_matches()
    for m in matches:
        match_id, round_num, p1, p2, result = m
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            st.write(f"Rodada {round_num}: {p1} x {p2}")
        with col2:
            novo_resultado = st.selectbox(
                "Resultado",
                ["", f"{p1} venceu", f"{p2} venceu", "Empate"],
                index=0,
                key=f"result_{match_id}"
            )
        with col3:
            if st.button("Salvar", key=f"save_{match_id}"):
                if novo_resultado == f"{p1} venceu":
                    update_result(match_id, "p1")
                elif novo_resultado == f"{p2} venceu":
                    update_result(match_id, "p2")
                elif novo_resultado == "Empate":
                    update_result(match_id, "draw")
                st.success("Resultado atualizado!")
                st.rerun()

# ==============================
# INICIALIZAÇÃO DO BANCO
# ==============================
if "initialized" not in st.session_state:
    init_db()
    players = [
        "Necrod", "Mayara", "Cabo", "Cronos", "Ramos",
        "Diogo", "Senju", "Erick", "Magnata", "Vanahein"
    ]
    add_players(players)
    rounds = generate_rounds(players)
    save_rounds(rounds)
    st.session_state.initialized = True
