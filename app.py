import streamlit as st
import sqlite3
import pandas as pd
import itertools
import math
from datetime import datetime

# ---------------------------
# CONFIG
# ---------------------------
DB_PATH = "liga.db"
PAGE_TITLE = "🏆 Liga do 13° - Sistema de Pontos Corridos"

# ---------------------------
# BANCO DE DADOS
# ---------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()

    # Jogadores
    c.execute('''
        CREATE TABLE IF NOT EXISTS jogadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            tag TEXT,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT
        )
    ''')

    # Temporadas
    c.execute('''
        CREATE TABLE IF NOT EXISTS temporadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            ativa INTEGER DEFAULT 0,
            criada_em TEXT
        )
    ''')

    # Rodadas / Confrontos
    c.execute('''
        CREATE TABLE IF NOT EXISTS rodadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temporada_id INTEGER,
            rodada INTEGER,
            jogador1_id INTEGER,
            jogador2_id INTEGER,
            estrelas_j1 INTEGER DEFAULT NULL,
            estrelas_j2 INTEGER DEFAULT NULL,
            porc_j1 REAL DEFAULT NULL,
            porc_j2 REAL DEFAULT NULL,
            tempo_j1 REAL DEFAULT NULL,
            tempo_j2 REAL DEFAULT NULL,
            resultado TEXT DEFAULT NULL,
            registrado_em TEXT,
            FOREIGN KEY (temporada_id) REFERENCES temporadas(id)
        )
    ''')

    conn.commit()
    return conn

# ---------------------------
# UTILIDADES SQL / DATA
# ---------------------------
def query_df(conn, sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)

# players
def add_player(conn, nome, tag=None):
    try:
        conn.execute("INSERT INTO jogadores (nome, tag, criado_em) VALUES (?, ?, ?)", (nome, tag, datetime.utcnow().isoformat()))
        conn.commit()
        return True
    except Exception as e:
        return False

def get_players(conn, only_active=True):
    sql = "SELECT * FROM jogadores"
    if only_active:
        sql += " WHERE ativo=1"
    return query_df(conn, sql)

# temporadas
def create_temporada(conn, nome):
    conn.execute("UPDATE temporadas SET ativa=0 WHERE ativa=1")
    cur = conn.execute("INSERT INTO temporadas (nome, ativa, criada_em) VALUES (?, 1, ?)", (nome, datetime.utcnow().isoformat()))
    conn.commit()
    return cur.lastrowid

def get_temporadas(conn):
    return query_df(conn, "SELECT * FROM temporadas ORDER BY id DESC")

def get_active_temporada(conn):
    df = query_df(conn, "SELECT * FROM temporadas WHERE ativa=1 LIMIT 1")
    return df.iloc[0] if not df.empty else None

# gerar round-robin e inserir rodadas
def gerar_round_robin(conn, temporada_id):
    players = get_players(conn)
    nomes_ids = list(zip(players['id'].tolist(), players['nome'].tolist()))
    n = len(nomes_ids)
    if n < 2:
        return "Número insuficiente de jogadores (mínimo 2)."

    # verifica se já existem confrontos para essa temporada
    existing = query_df(conn, "SELECT COUNT(*) as qtd FROM rodadas WHERE temporada_id=?", (temporada_id,)).iloc[0]['qtd']
    if existing > 0:
        return "Confrontos já foram gerados para esta temporada." 

    # Round-robin (cada jogador enfrenta todos os outros uma vez)
    pares = []
    for a, b in itertools.combinations(nomes_ids, 2):
        pares.append((a[0], b[0]))

    # distribuir em 'rodadas' aproximadas: we'll create R = n-1 rodadas and assign pairs sequentially
    R = max(1, n - 1)
    rodada_idx = 1
    for i, (p1, p2) in enumerate(pares):
        conn.execute("INSERT INTO rodadas (temporada_id, rodada, jogador1_id, jogador2_id) VALUES (?, ?, ?, ?)",
                     (temporada_id, rodada_idx, p1, p2))
        rodada_idx += 1
        if rodada_idx > R:
            rodada_idx = 1
    conn.commit()
    return f"Gerados {len(pares)} confrontos em {R} rodadas (temporada {temporada_id})."

# obtenção de rodadas por temporada
def get_rodadas_temporada(conn, temporada_id):
    sql = "SELECT r.*, j1.nome as jogador1, j2.nome as jogador2 FROM rodadas r LEFT JOIN jogadores j1 ON r.jogador1_id=j1.id LEFT JOIN jogadores j2 ON r.jogador2_id=j2.id WHERE r.temporada_id=? ORDER BY r.rodada, r.id"
    return query_df(conn, sql, (temporada_id,))

# registrar resultado com critérios
def determinar_vencedor(e1, e2, p1, p2, t1, t2):
    # critérios: estrelas > porcentagem > tempo (menor tempo vence)
    if e1 is None or e2 is None:
        return None
    if e1 > e2:
        return 1
    if e2 > e1:
        return 2
    # empate em estrelas
    if p1 is None or p2 is None:
        return None
    if p1 > p2:
        return 1
    if p2 > p1:
        return 2
    # empate em porcentagem
    if t1 is None or t2 is None:
        return None
    # menor tempo vence
    if t1 < t2:
        return 1
    if t2 < t1:
        return 2
    # empate completo -> rematch required
    return 0

def registrar_resultado(conn, rodada_id, e1, e2, p1, p2, t1, t2):
    vencedor = determinar_vencedor(e1, e2, p1, p2, t1, t2)
    resultado = None
    if vencedor == 1:
        resultado = 'j1'
    elif vencedor == 2:
        resultado = 'j2'
    elif vencedor == 0:
        resultado = 'empate_rematch'
    # atualiza
    conn.execute('''UPDATE rodadas SET estrelas_j1=?, estrelas_j2=?, porc_j1=?, porc_j2=?, tempo_j1=?, tempo_j2=?, resultado=?, registrado_em=? WHERE id=?''',
                 (e1, e2, p1, p2, t1, t2, resultado, datetime.utcnow().isoformat(), rodada_id))
    conn.commit()
    return resultado

# ---------------------------
# ESTATÍSTICAS DERIVADAS
# ---------------------------

def calcular_classificacao(conn, temporada_id):
    rodadas = get_rodadas_temporada(conn, temporada_id)
    if rodadas.empty:
        return pd.DataFrame(columns=['jogador','pontos','vitorias','derrotas','empates','est_ataque_total','est_defesa_total','saldo_estrelas','porc_ataque_avg','tempo_ataque_avg','partidas'])

    players = {}
    for _, row in rodadas.iterrows():
        for side in [1,2]:
            pid = row[f'jogador{side}_id']
            pname = row[f'jogador{side}']
            if pid not in players:
                players[pid] = {
                    'jogador': pname,
                    'pontos': 0,
                    'vitorias': 0,
                    'derrotas': 0,
                    'empates': 0,
                    'est_ataque_total': 0,
                    'est_defesa_total': 0,
                    'porc_ataque_list': [],
                    'tempo_ataque_list': [],
                    'partidas': 0
                }
        # se resultado preenchido
        if pd.isna(row['estrelas_j1']) or pd.isna(row['estrelas_j2']):
            continue
        # update counts
        j1 = row['jogador1_id']
        j2 = row['jogador2_id']
        e1 = int(row['estrelas_j1'])
        e2 = int(row['estrelas_j2'])
        p1 = float(row['porc_j1'])
        p2 = float(row['porc_j2'])
        t1 = float(row['tempo_j1'])
        t2 = float(row['tempo_j2'])

        # partidas
        players[j1]['partidas'] += 1
        players[j2]['partidas'] += 1

        # estrelas
        players[j1]['est_ataque_total'] += e1
        players[j1]['est_defesa_total'] += e2
        players[j2]['est_ataque_total'] += e2
        players[j2]['est_defesa_total'] += e1

        # porcentagem e tempo
        players[j1]['porc_ataque_list'].append(p1)
        players[j1]['tempo_ataque_list'].append(t1)
        players[j2]['porc_ataque_list'].append(p2)
        players[j2]['tempo_ataque_list'].append(t2)

        # vencedor
        res = determinar_vencedor(e1, e2, p1, p2, t1, t2)
        if res == 1:
            players[j1]['pontos'] += 1
            players[j1]['vitorias'] += 1
            players[j2]['derrotas'] += 1
        elif res == 2:
            players[j2]['pontos'] += 1
            players[j2]['vitorias'] += 1
            players[j1]['derrotas'] += 1
        elif res == 0:
            players[j1]['empates'] += 1
            players[j2]['empates'] += 1

    # montar df
    rows = []
    for pid, d in players.items():
        porc_avg = float(sum(d['porc_ataque_list']) / len(d['porc_ataque_list'])) if d['porc_ataque_list'] else 0.0
        tempo_avg = float(sum(d['tempo_ataque_list']) / len(d['tempo_ataque_list'])) if d['tempo_ataque_list'] else 0.0
        saldo = d['est_ataque_total'] - d['est_defesa_total']
        rows.append({
            'jogador_id': pid,
            'jogador': d['jogador'],
            'pontos': d['pontos'],
            'vitorias': d['vitorias'],
            'derrotas': d['derrotas'],
            'empates': d['empates'],
            'est_ataque_total': d['est_ataque_total'],
            'est_defesa_total': d['est_defesa_total'],
            'saldo_estrelas': saldo,
            'porc_ataque_avg': round(porc_avg,2),
            'tempo_ataque_avg': round(tempo_avg,2),
            'partidas': d['partidas']
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values(by=['pontos','saldo_estrelas','porc_ataque_avg','tempo_ataque_avg'], ascending=[False, False, False, True]).reset_index(drop=True)
    df.insert(0, 'Posição', range(1, len(df)+1))
    return df

# histórico individual
def get_historico_jogador(conn, temporada_id, jogador_id):
    sql = "SELECT r.*, j1.nome as jogador1, j2.nome as jogador2 FROM rodadas r LEFT JOIN jogadores j1 ON r.jogador1_id=j1.id LEFT JOIN jogadores j2 ON r.jogador2_id=j2.id WHERE r.temporada_id=? AND (r.jogador1_id=? OR r.jogador2_id=?) ORDER BY r.rodada"
    return query_df(conn, sql, (temporada_id, jogador_id, jogador_id))

# ---------------------------
# STREAMLIT APP
# ---------------------------

st.set_page_config(page_title=PAGE_TITLE, layout="wide")
st.title(PAGE_TITLE)

conn = init_db()

menu = st.sidebar.selectbox("Menu", [
    "Classificação",
    "Rodadas",
    "Cadastrar Resultados",
    "Jogadores",
    "Temporadas",
    "Histórico Individual",
    "Exportar CSV"
])

# ---------------------------
# CLASSIFICAÇÃO
# ---------------------------
if menu == "Classificação":
    st.subheader("📊 Tabela de Classificação")
    active = get_active_temporada(conn)
    if active is None:
        st.info("Nenhuma temporada ativa. Crie e inicie uma temporada na aba 'Temporadas'.")
    else:
        df = calcular_classificacao(conn, active['id'])
        if df.empty:
            st.info("Ainda não há resultados registrados nesta temporada.")
        else:
            st.dataframe(df[['Posição','jogador','pontos','vitorias','derrotas','empates','partidas','saldo_estrelas','est_ataque_total','est_defesa_total','porc_ataque_avg','tempo_ataque_avg']], use_container_width=True)

# ---------------------------
# RODADAS
# ---------------------------
elif menu == "Rodadas":
    st.subheader("📅 Rodadas e Confrontos")
    active = get_active_temporada(conn)
    if active is None:
        st.info("Nenhuma temporada ativa. Crie e inicie uma temporada na aba 'Temporadas'.")
    else:
        rod = get_rodadas_temporada(conn, active['id'])
        if rod.empty:
            st.info("Confrontos não gerados ainda. Use 'Temporadas' -> 'Gerar confrontos'.")
        else:
            for r in sorted(rod['rodada'].unique()):
                st.markdown(f"### Rodada {r}")
                sub = rod[rod['rodada']==r][['id','jogador1','jogador2','estrelas_j1','estrelas_j2','porc_j1','porc_j2','tempo_j1','tempo_j2','resultado']]
                st.dataframe(sub.rename(columns={'id':'Confronto ID','jogador1':'Jogador 1','jogador2':'Jogador 2','estrelas_j1':'E1','estrelas_j2':'E2'}), use_container_width=True)

# ---------------------------
# CADASTRAR RESULTADOS
# ---------------------------
elif menu == "Cadastrar Resultados":
    st.subheader("✍️ Registrar Resultado")
    active = get_active_temporada(conn)
    if active is None:
        st.info("Nenhuma temporada ativa.")
    else:
        rod = get_rodadas_temporada(conn, active['id'])
        if rod.empty:
            st.info("Nenhum confronto gerado para esta temporada.")
        else:
            choices = rod.apply(lambda r: f"ID {r['id']}: {r['jogador1']} vs {r['jogador2']} (R{r['rodada']})", axis=1).tolist()
            sel = st.selectbox("Escolha o confronto", choices)
            cid = int(sel.split()[1].strip(':'))
            row = rod[rod['id']==cid].iloc[0]
            st.markdown(f"**{row['jogador1']}** vs **{row['jogador2']}** (Rodada {row['rodada']})")

            e1 = st.number_input(f"⭐ Estrelas {row['jogador1']}", 0, 3, value=int(row['estrelas_j1']) if not pd.isna(row['estrelas_j1']) else 0)
            e2 = st.number_input(f"⭐ Estrelas {row['jogador2']}", 0, 3, value=int(row['estrelas_j2']) if not pd.isna(row['estrelas_j2']) else 0)
            p1 = st.number_input(f"% Ataque {row['jogador1']}", 0.0, 100.0, value=float(row['porc_j1']) if not pd.isna(row['porc_j1']) else 0.0, step=0.1)
            p2 = st.number_input(f"% Ataque {row['jogador2']}", 0.0, 100.0, value=float(row['porc_j2']) if not pd.isna(row['porc_j2']) else 0.0, step=0.1)
            t1 = st.number_input(f"⏱️ Tempo {row['jogador1']} (segundos)", 0.0, 9999.0, value=float(row['tempo_j1']) if not pd.isna(row['tempo_j1']) else 0.0, step=1.0)
            t2 = st.number_input(f"⏱️ Tempo {row['jogador2']} (segundos)", 0.0, 9999.0, value=float(row['tempo_j2']) if not pd.isna(row['tempo_j2']) else 0.0, step=1.0)

            if st.button("Salvar Resultado"):
                resultado = registrar_resultado(conn, cid, int(e1), int(e2), float(p1), float(p2), float(t1), float(t2))
                if resultado == 'empate_rematch':
                    st.warning("Empate exato: marque como 'Rematch' — o sistema registrou como 'empate_rematch'. Refaça o confronto in-game e registre novamente.")
                else:
                    st.success("Resultado registrado com sucesso ✅")

# ---------------------------
# JOGADORES
# ---------------------------
elif menu == "Jogadores":
    st.subheader("👥 Gerenciar Jogadores")
    with st.form("add_player"):
        nome = st.text_input("Nome do jogador")
        tag = st.text_input("TAG (opcional)")
        submitted = st.form_submit_button("Adicionar")
        if submitted:
            if nome.strip() == "":
                st.error("Nome não pode ficar vazio.")
            else:
                ok = add_player(conn, nome.strip(), tag.strip() or None)
                if ok:
                    st.success("Jogador adicionado.")
                else:
                    st.error("Erro ao adicionar — nome talvez já exista.")
    st.markdown("---")
    st.write(get_players(conn, only_active=False))

# ---------------------------
# TEMPORADAS
# ---------------------------
elif menu == "Temporadas":
    st.subheader("🗂️ Temporadas")
    with st.form("criar_temp"):
        nome = st.text_input("Nome da Temporada", value=f"Temporada {datetime.utcnow().year}")
        criar = st.form_submit_button("Criar e Ativar")
        if criar:
            tid = create_temporada(conn, nome)
            st.success(f"Temporada criada e ativada: {nome} (ID {tid})")
    st.markdown("---")
    temporadas = get_temporadas(conn)
    st.dataframe(temporadas, use_container_width=True)

    st.markdown("### Gerar confrontos para a temporada ativa")
    active = get_active_temporada(conn)
    if active is None:
        st.info("Não há temporada ativa.")
    else:
        st.write(f"Temporada ativa: {active['nome']} (ID {active['id']})")
        if st.button("Gerar Round-Robin para temporada ativa"):
            msg = gerar_round_robin(conn, active['id'])
            st.success(msg)

# ---------------------------
# HISTÓRICO INDIVIDUAL
# ---------------------------
elif menu == "Histórico Individual":
    st.subheader("📜 Histórico Individual")
    active = get_active_temporada(conn)
    if active is None:
        st.info("Nenhuma temporada ativa.")
    else:
        players = get_players(conn)
        sel = st.selectbox("Selecione Jogador", players['nome'].tolist())
        pid = int(players[players['nome']==sel]['id'].iloc[0])
        hist = get_historico_jogador(conn, active['id'], pid)
        if hist.empty:
            st.info("Nenhum confronto registrado para esse jogador nesta temporada.")
        else:
            st.dataframe(hist[['rodada','jogador1','jogador2','estrelas_j1','estrelas_j2','porc_j1','porc_j2','tempo_j1','tempo_j2','resultado']], use_container_width=True)

# ---------------------------
# EXPORTAR CSV
# ---------------------------
elif menu == "Exportar CSV":
    st.subheader("📤 Exportar")
    active = get_active_temporada(conn)
    if active is None:
        st.info("Nenhuma temporada ativa.")
    else:
        df = calcular_classificacao(conn, active['id'])
        if df.empty:
            st.info("Nada para exportar ainda.")
        else:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Exportar classificação CSV", data=csv, file_name=f"classificacao_temporada_{active['id']}.csv", mime='text/csv')

# ---------------------------
# FIM
# ---------------------------

st.markdown("---")
st.caption("Sistema refatorado: pontuação por vitória (1 ponto), critérios de desempate aplicados na classificação: Saldo de Estrelas > Média de Destruição > Tempo Médio (menor melhor).")