# app.py
import streamlit as st
import pandas as pd
import itertools
import hashlib
from datetime import datetime
import firebase_init
from firebase_admin import firestore

# ---------------------------
# CONFIG
# ---------------------------
PAGE_TITLE = "🏆 Liga do 13° - Sistema de Pontos Corridos (Firebase)"

# ---------------------------
# INICIALIZAÇÃO FIREBASE
# ---------------------------
@st.cache_resource
def init_firebase():
    return firebase_init.init_firebase()

fb = init_firebase()
db = fb['db']

# ---------------------------
# UTILIDADES
# ---------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, passhash: str) -> bool:
    return hash_password(password) == passhash

# ---------------------------
# FUNÇÕES FIREBASE - JOGADORES
# ---------------------------
def add_player(nome, tag=None):
    try:
        jogador_data = {
            'nome': nome,
            'tag': tag,
            'ativo': True,
            'criado_em': datetime.utcnow().isoformat()
        }
        db.collection('jogadores').add(jogador_data)
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar jogador: {e}")
        return False

def update_player(player_id, nome, tag):
    try:
        db.collection('jogadores').document(str(player_id)).update({
            'nome': nome,
            'tag': tag
        })
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar jogador: {e}")
        return False

def delete_player(player_id):
    try:
        # soft delete: marca ativo = False
        db.collection('jogadores').document(str(player_id)).update({'ativo': False})
        return True
    except Exception as e:
        st.error(f"Erro ao excluir jogador: {e}")
        return False

def get_players(only_active=True):
    try:
        if only_active:
            query = db.collection('jogadores').where('ativo', '==', True)
        else:
            query = db.collection('jogadores')
        
        docs = list(query.stream())
        players = []
        for doc in docs:
            player_data = doc.to_dict() or {}
            player_data['id'] = doc.id
            players.append(player_data)
        
        if not players:
            return pd.DataFrame()
        df = pd.DataFrame(players)
        # Garantir colunas existentes
        if 'nome' not in df.columns:
            df['nome'] = ''
        if 'tag' not in df.columns:
            df['tag'] = ''
        return df
    except Exception as e:
        st.error(f"Erro ao buscar jogadores: {e}")
        return pd.DataFrame()

# ---------------------------
# FUNÇÕES FIREBASE - USUÁRIOS
# ---------------------------
def create_user(username, password, is_admin=False):
    try:
        user_data = {
            'username': username,
            'passhash': hash_password(password),
            'is_admin': is_admin,
            'criado_em': datetime.utcnow().isoformat()
        }
        db.collection('usuarios').document(username).set(user_data)
        return True
    except Exception as e:
        st.error(f"Erro ao criar usuário: {e}")
        return False

def get_admin_exists():
    try:
        query = db.collection('usuarios').where('is_admin', '==', True).limit(1)
        docs = list(query.stream())
        return len(docs) > 0
    except Exception as e:
        st.error(f"Erro ao verificar admin: {e}")
        return False

def authenticate(username, password):
    try:
        doc_ref = db.collection('usuarios').document(username)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
            
        user_data = doc.to_dict()
        if verify_password(password, user_data.get('passhash', '')):
            return {
                'id': doc.id,
                'username': user_data.get('username'),
                'is_admin': user_data.get('is_admin', False)
            }
        return None
    except Exception as e:
        st.error(f"Erro na autenticação: {e}")
        return None

# ---------------------------
# FUNÇÕES FIREBASE - TEMPORADAS
# ---------------------------
def create_temporada(nome):
    try:
        # Desativar temporadas ativas
        active_query = db.collection('temporadas').where('ativa', '==', True)
        active_docs = list(active_query.stream())
        for doc in active_docs:
            db.collection('temporadas').document(doc.id).update({'ativa': False})
        
        # Criar nova temporada
        temporada_data = {
            'nome': nome,
            'ativa': True,
            'criada_em': datetime.utcnow().isoformat()
        }
        new_ref = db.collection('temporadas').add(temporada_data)
        # new_ref returns (DocumentReference, write_time) — DocumentReference is index 0 in some admin versions, but add() returns tuple
        # To be safe, fetch last added via query by created timestamp
        # We'll attempt to return the new doc id intelligently:
        if isinstance(new_ref, tuple) and len(new_ref) >= 1:
            doc_ref = new_ref[0]
            try:
                return doc_ref.id
            except Exception:
                pass
        # fallback: try to find by nome and criada_em recent
        recent = list(db.collection('temporadas').where('nome', '==', nome).order_by('criada_em', direction=firestore.Query.DESCENDING).limit(1).stream())
        if recent:
            return recent[0].id
        return None
    except Exception as e:
        st.error(f"Erro ao criar temporada: {e}")
        return None

def get_temporadas():
    try:
        # Busca todas as temporadas e ordena em Python (evita dependência de índice)
        docs = list(db.collection('temporadas').stream())
        temporadas = []
        for doc in docs:
            temp_data = doc.to_dict() or {}
            temp_data['id'] = doc.id
            temporadas.append(temp_data)
        if not temporadas:
            return pd.DataFrame()
        df = pd.DataFrame(temporadas)
        # ordenar por criada_em se existir
        if 'criada_em' in df.columns:
            df['criada_em_sort'] = pd.to_datetime(df['criada_em'], errors='coerce')
            df = df.sort_values(by='criada_em_sort', ascending=False).drop(columns=['criada_em_sort'])
        return df.reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao buscar temporadas: {e}")
        return pd.DataFrame()

def get_active_temporada():
    try:
        query = db.collection('temporadas').where('ativa', '==', True).limit(1)
        docs = list(query.stream())
        if docs:
            temp_data = docs[0].to_dict() or {}
            temp_data['id'] = docs[0].id
            return temp_data
        return None
    except Exception as e:
        st.error(f"Erro ao buscar temporada ativa: {e}")
        return None

# ---------------------------
# FUNÇÕES FIREBASE - RODADAS
# ---------------------------
def gerar_round_robin(temporada_id):
    try:
        players = get_players()
        if players.empty or len(players) < 2:
            return "Número insuficiente de jogadores (mínimo 2)."
        
        # Verificar se já existem confrontos
        existing_query = db.collection('rodadas').where('temporada_id', '==', temporada_id)
        existing_docs = list(existing_query.stream())
        if len(existing_docs) > 0:
            return "Confrontos já foram gerados para esta temporada."
        
        # Gerar pares
        player_ids = players['id'].astype(str).tolist()
        pares = list(itertools.combinations(player_ids, 2))
        
        # Distribuir em rodadas
        n = len(player_ids)
        R = max(1, n - 1)
        rodada_idx = 1
        
        for p1, p2 in pares:
            rodada_data = {
                'temporada_id': temporada_id,
                'rodada': rodada_idx,
                'jogador1_id': str(p1),
                'jogador2_id': str(p2),
                'estrelas_j1': None,
                'estrelas_j2': None,
                'porc_j1': None,
                'porc_j2': None,
                'tempo_j1': None,
                'tempo_j2': None,
                'resultado': None,
                'registrado_em': None
            }
            db.collection('rodadas').add(rodada_data)
            rodada_idx = 1 if rodada_idx >= R else rodada_idx + 1
        
        return f"Gerados {len(pares)} confrontos em {R} rodadas."
        
    except Exception as e:
        return f"Erro ao gerar round-robin: {e}"

def get_rodadas_temporada(temporada_id):
    try:
        # Evitar order_by no Firestore para não precisar de índice composto:
        query = db.collection('rodadas').where('temporada_id', '==', temporada_id)
        docs = list(query.stream())
        
        rodadas = []
        for doc in docs:
            rodada_data = doc.to_dict() or {}
            rodada_data['id'] = doc.id
            
            # Buscar nomes dos jogadores (se existirem)
            j1_id = str(rodada_data.get('jogador1_id', '')) if rodada_data.get('jogador1_id') is not None else ''
            j2_id = str(rodada_data.get('jogador2_id', '')) if rodada_data.get('jogador2_id') is not None else ''
            
            if j1_id:
                j1_doc = db.collection('jogadores').document(j1_id).get()
                rodada_data['jogador1'] = j1_doc.to_dict().get('nome', 'N/A') if j1_doc.exists else 'N/A'
            else:
                rodada_data['jogador1'] = 'N/A'
            if j2_id:
                j2_doc = db.collection('jogadores').document(j2_id).get()
                rodada_data['jogador2'] = j2_doc.to_dict().get('nome', 'N/A') if j2_doc.exists else 'N/A'
            else:
                rodada_data['jogador2'] = 'N/A'
            
            # Normalize types for sorting later
            try:
                rodada_data['rodada'] = int(rodada_data.get('rodada')) if rodada_data.get('rodada') is not None else 0
            except Exception:
                rodada_data['rodada'] = 0
            # ensure numeric types where possible
            for k in ('estrelas_j1','estrelas_j2'):
                v = rodada_data.get(k)
                rodada_data[k] = int(v) if isinstance(v, (int, float)) else (int(v) if v and str(v).isdigit() else None)
            for k in ('porc_j1','porc_j2','tempo_j1','tempo_j2'):
                v = rodada_data.get(k)
                try:
                    rodada_data[k] = float(v) if v is not None else None
                except Exception:
                    rodada_data[k] = None

            rodadas.append(rodada_data)
        
        if not rodadas:
            return pd.DataFrame()
        df = pd.DataFrame(rodadas)
        df = df.sort_values(by=['rodada', 'id']).reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar rodadas: {e}")
        return pd.DataFrame()

def determinar_vencedor(e1, e2, p1, p2, t1, t2):
    if e1 is None or e2 is None:
        return None
    if e1 > e2:
        return 1
    if e2 > e1:
        return 2
    if p1 is None or p2 is None:
        return None
    if p1 > p2:
        return 1
    if p2 > p1:
        return 2
    if t1 is None or t2 is None:
        return None
    if t1 < t2:
        return 1
    if t2 < t1:
        return 2
    return 0

def registrar_resultado(rodada_id, e1, e2, p1, p2, t1, t2):
    try:
        vencedor = determinar_vencedor(e1, e2, p1, p2, t1, t2)
        resultado = None
        if vencedor == 1:
            resultado = 'j1'
        elif vencedor == 2:
            resultado = 'j2'
        elif vencedor == 0:
            resultado = 'empate_rematch'
            
        db.collection('rodadas').document(str(rodada_id)).update({
            'estrelas_j1': int(e1),
            'estrelas_j2': int(e2),
            'porc_j1': float(p1),
            'porc_j2': float(p2),
            'tempo_j1': float(t1),
            'tempo_j2': float(t2),
            'resultado': resultado,
            'registrado_em': datetime.utcnow().isoformat()
        })
        return resultado
    except Exception as e:
        st.error(f"Erro ao registrar resultado: {e}")
        return None

# ---------------------------
# ESTATÍSTICAS DERIVADAS
# ---------------------------
def calcular_classificacao(temporada_id):
    rodadas = get_rodadas_temporada(temporada_id)
    if rodadas.empty:
        return pd.DataFrame(columns=['jogador','pontos','vitorias','derrotas','empates','est_ataque_total','est_defesa_total','saldo_estrelas','porc_ataque_avg','tempo_ataque_avg','partidas'])

    players = {}
    for _, row in rodadas.iterrows():
        for side in [1,2]:
            pid = row.get(f'jogador{side}_id')
            pname = row.get(f'jogador{side}')
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
        
        if pd.isna(row.get('estrelas_j1')) or pd.isna(row.get('estrelas_j2')):
            continue
            
        j1 = row.get('jogador1_id')
        j2 = row.get('jogador2_id')
        e1 = int(row.get('estrelas_j1')) if row.get('estrelas_j1') is not None else 0
        e2 = int(row.get('estrelas_j2')) if row.get('estrelas_j2') is not None else 0
        p1 = float(row.get('porc_j1')) if row.get('porc_j1') is not None else 0.0
        p2 = float(row.get('porc_j2')) if row.get('porc_j2') is not None else 0.0
        t1 = float(row.get('tempo_j1')) if row.get('tempo_j1') is not None else 0.0
        t2 = float(row.get('tempo_j2')) if row.get('tempo_j2') is not None else 0.0

        players[j1]['partidas'] += 1
        players[j2]['partidas'] += 1

        players[j1]['est_ataque_total'] += e1
        players[j1]['est_defesa_total'] += e2
        players[j2]['est_ataque_total'] += e2
        players[j2]['est_defesa_total'] += e1

        players[j1]['porc_ataque_list'].append(p1)
        players[j1]['tempo_ataque_list'].append(t1)
        players[j2]['porc_ataque_list'].append(p2)
        players[j2]['tempo_ataque_list'].append(t2)

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

def get_historico_jogador(temporada_id, jogador_id):
    try:
        query = db.collection('rodadas').where('temporada_id', '==', temporada_id)
        docs = list(query.stream())
        
        historico = []
        for doc in docs:
            rodada_data = doc.to_dict() or {}
            if str(rodada_data.get('jogador1_id')) == str(jogador_id) or str(rodada_data.get('jogador2_id')) == str(jogador_id):
                rodada_data['id'] = doc.id
                
                j1_doc = db.collection('jogadores').document(str(rodada_data.get('jogador1_id'))).get()
                j2_doc = db.collection('jogadores').document(str(rodada_data.get('jogador2_id'))).get()
                
                rodada_data['jogador1'] = j1_doc.to_dict().get('nome', 'N/A') if j1_doc.exists else 'N/A'
                rodada_data['jogador2'] = j2_doc.to_dict().get('nome', 'N/A') if j2_doc.exists else 'N/A'
                
                historico.append(rodada_data)
        
        if not historico:
            return pd.DataFrame()
        df = pd.DataFrame(historico)
        # ordenar por rodada
        if 'rodada' in df.columns:
            df['rodada'] = pd.to_numeric(df['rodada'], errors='coerce').fillna(0).astype(int)
            df = df.sort_values(by='rodada').reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar histórico: {e}")
        return pd.DataFrame()

# ---------------------------
# STREAMLIT APP
# ---------------------------
st.set_page_config(page_title=PAGE_TITLE, layout="wide")
st.title(PAGE_TITLE)

# session state for auth
if 'user' not in st.session_state:
    st.session_state['user'] = None
    st.session_state['is_admin'] = False
    st.session_state['logged_in'] = False

# --- Auth / setup (sidebar) ---
with st.sidebar:
    st.markdown("### Usuário")
    if not get_admin_exists():
        st.warning("Nenhum administrador encontrado. Crie um usuário admin para começar.")
        with st.form('create_admin'):
            admin_user = st.text_input('Nome do admin', value='admin')
            admin_pass = st.text_input('Senha (será armazenada com hash)', type='password')
            create = st.form_submit_button('Criar admin')
            if create:
                if admin_pass.strip() == '':
                    st.error('Senha não pode ser vazia')
                else:
                    ok = create_user(admin_user.strip(), admin_pass.strip(), is_admin=True)
                    if ok:
                        st.success('Admin criado. Faça login.')
                    else:
                        st.error('Erro ao criar admin — talvez usuário já exista.')
    else:
        if not st.session_state['logged_in']:
            with st.form('login'):
                uname = st.text_input('Usuário')
                upass = st.text_input('Senha', type='password')
                submitted = st.form_submit_button('Login')
                if submitted:
                    auth = authenticate(uname.strip(), upass)
                    if auth:
                        st.session_state['user'] = auth['username']
                        st.session_state['is_admin'] = auth['is_admin']
                        st.session_state['logged_in'] = True
                        st.success(f"Logado como {auth['username']}")
                    else:
                        st.error('Credenciais inválidas')
        else:
            st.markdown(f"**{st.session_state['user']}**")
            if st.button('Logout'):
                st.session_state['user'] = None
                st.session_state['is_admin'] = False
                st.session_state['logged_in'] = False
                st.experimental_rerun()

# Build menu dynamically based on permissions
menu_items = ["Público - Classificação & Confrontos", "Minha Conta"]
if st.session_state['logged_in']:
    # logged users can view classification, rodadas, historico
    menu_items += ["Classificação", "Rodadas", "Histórico Individual"]
    if st.session_state['is_admin']:
        # admin-only features
        menu_items += ["Cadastrar Resultados", "Jogadores", "Temporadas"]
# show the menu
menu = st.sidebar.selectbox("Menu", menu_items)

# ---------------------------
# PÚBLICO
# ---------------------------
if menu == "Público - Classificação & Confrontos":
    st.subheader("🌐 Visão Pública")
    active = get_active_temporada()
    if active is None:
        st.info("Nenhuma temporada ativa.")
    else:
        st.markdown(f"### Temporada ativa: **{active.get('nome','-')}** (ID {active.get('id')})")
        df = calcular_classificacao(active.get('id'))
        if df.empty:
            st.info("Ainda não há resultados registrados nesta temporada.")
        else:
            st.dataframe(df[['Posição','jogador','pontos','saldo_estrelas','porc_ataque_avg','tempo_ataque_avg']], use_container_width=True)
        st.markdown('---')
        st.markdown('### Confrontos públicos (somente leitura)')
        rod = get_rodadas_temporada(active.get('id'))
        if rod.empty:
            st.info('Confrontos não gerados ainda.')
        else:
            st.dataframe(rod[['rodada','jogador1','jogador2','estrelas_j1','estrelas_j2','porc_j1','porc_j2','tempo_j1','tempo_j2','resultado']], use_container_width=True)

# ---------------------------
# MINHA CONTA
# ---------------------------
elif menu == 'Minha Conta':
    st.subheader('👤 Minha Conta')
    if not st.session_state['logged_in']:
        st.info('Faça login na barra lateral para acessar sua conta.')
    else:
        st.write(f"Usuário: **{st.session_state['user']}**")
        st.write(f"Administrador: **{st.session_state['is_admin']}**")

# ---------------------------
# CLASSIFICAÇÃO
# ---------------------------
elif menu == "Classificação":
    st.subheader("📊 Tabela de Classificação")
    active = get_active_temporada()
    if active is None:
        st.info("Nenhuma temporada ativa. Crie e ative uma na aba 'Temporadas'.")
    else:
        df = calcular_classificacao(active.get('id'))
        if df.empty:
            st.info("Ainda não há resultados registrados nesta temporada.")
        else:
            st.dataframe(df[['Posição','jogador','pontos','vitorias','derrotas','empates','partidas','saldo_estrelas','est_ataque_total','est_defesa_total','porc_ataque_avg','tempo_ataque_avg']], use_container_width=True)

# ---------------------------
# RODADAS
# ---------------------------
elif menu == "Rodadas":
    st.subheader("📅 Rodadas e Confrontos")
    active = get_active_temporada()
    if active is None:
        st.info("Nenhuma temporada ativa. Crie e ative uma temporada na aba 'Temporadas'.")
    else:
        rod = get_rodadas_temporada(active.get('id'))
        if rod.empty:
            st.info("Confrontos não gerados ainda. Use 'Temporadas' -> 'Gerar confrontos' (admin).")
        else:
            for r in sorted(rod['rodada'].unique()):
                st.markdown(f"### Rodada {r}")
                sub = rod[rod['rodada']==r][['id','jogador1','jogador2','estrelas_j1','estrelas_j2','porc_j1','porc_j2','tempo_j1','tempo_j2','resultado']]
                st.dataframe(sub.rename(columns={'id':'Confronto ID','jogador1':'Jogador 1','jogador2':'Jogador 2','estrelas_j1':'E1','estrelas_j2':'E2'}), use_container_width=True)

# ---------------------------
# CADASTRAR RESULTADOS (APENAS ADMIN)
# ---------------------------
elif menu == "Cadastrar Resultados":
    st.subheader("✍️ Registrar Resultado (Admin)")
    if not st.session_state['is_admin']:
        st.warning('Apenas administradores podem registrar/editar resultados. Faça login com uma conta admin.')
    else:
        active = get_active_temporada()
        if active is None:
            st.info("Nenhuma temporada ativa.")
        else:
            rod = get_rodadas_temporada(active.get('id'))
            if rod.empty:
                st.info("Nenhum confronto gerado para esta temporada.")
            else:
                # build choices
                choices = []
                for _, r in rod.iterrows():
                    choices.append(f"ID {r['id']}: {r['jogador1']} vs {r['jogador2']} (R{r['rodada']})")
                sel = st.selectbox("Escolha o confronto", choices)
                cid = sel.split()[1].strip(':')
                row = rod[rod['id']==cid].iloc[0]
                st.markdown(f"**{row['jogador1']}** vs **{row['jogador2']}** (Rodada {row['rodada']})")

                e1 = st.number_input(f"⭐ Estrelas {row['jogador1']}", 0, 3, value=int(row['estrelas_j1']) if not pd.isna(row['estrelas_j1']) else 0)
                e2 = st.number_input(f"⭐ Estrelas {row['jogador2']}", 0, 3, value=int(row['estrelas_j2']) if not pd.isna(row['estrelas_j2']) else 0)
                p1 = st.number_input(f"% Ataque {row['jogador1']}", 0.0, 100.0, value=float(row['porc_j1']) if not pd.isna(row['porc_j1']) else 0.0, step=0.1)
                p2 = st.number_input(f"% Ataque {row['jogador2']}", 0.0, 100.0, value=float(row['porc_j2']) if not pd.isna(row['porc_j2']) else 0.0, step=0.1)
                t1 = st.number_input(f"⏱️ Tempo {row['jogador1']} (segundos)", 0.0, 9999.0, value=float(row['tempo_j1']) if not pd.isna(row['tempo_j1']) else 0.0, step=1.0)
                t2 = st.number_input(f"⏱️ Tempo {row['jogador2']} (segundos)", 0.0, 9999.0, value=float(row['tempo_j2']) if not pd.isna(row['tempo_j2']) else 0.0, step=1.0)

                if st.button("Salvar Resultado"):
                    resultado = registrar_resultado(cid, int(e1), int(e2), float(p1), float(p2), float(t1), float(t2))
                    if resultado == 'empate_rematch':
                        st.warning("Empate exato: marque como 'Rematch' — o sistema registrou como 'empate_rematch'. Refaça o confronto in-game e registre novamente.")
                    elif resultado is None:
                        st.error("Erro ao salvar resultado.")
                    else:
                        st.success("Resultado registrado com sucesso ✅")
                        # refresh view
                        st.experimental_rerun()

# ---------------------------
# JOGADORES (ADMIN: CRUD) 
# ---------------------------
elif menu == "Jogadores":
    st.subheader("👥 Gerenciar Jogadores")
    if not st.session_state['is_admin']:
        st.info('Apenas administradores podem adicionar/editar/excluir jogadores. Aqui está a lista pública:')
        st.write(get_players(only_active=True))
    else:
        with st.expander('Adicionar novo jogador'):
            with st.form('add_player'):
                nome = st.text_input("Nome do jogador")
                tag = st.text_input("TAG (opcional)")
                submitted = st.form_submit_button("Adicionar")
                if submitted:
                    if nome.strip() == "":
                        st.error("Nome não pode ficar vazio.")
                    else:
                        ok = add_player(nome.strip(), tag.strip() or None)
                        if ok:
                            st.success("Jogador adicionado.")
                        else:
                            st.error("Erro ao adicionar — nome talvez já exista.")
        st.markdown('---')
        st.markdown('### Editar/Excluir jogador')
        players = get_players(only_active=False)
        if players.empty:
            st.info('Nenhum jogador cadastrado.')
        else:
            sel = st.selectbox('Selecione jogador para editar/excluir', players['nome'].tolist())
            pid = players[players['nome']==sel]['id'].iloc[0]
            ptag = players[players['nome']==sel]['tag'].iloc[0] if 'tag' in players.columns else ''
            with st.form('edit_player'):
                new_name = st.text_input('Nome', value=sel)
                new_tag = st.text_input('TAG', value=ptag if ptag is not None else '')
                upd = st.form_submit_button('Salvar alteração')
                if upd:
                    if new_name.strip() == '':
                        st.error('Nome não pode ficar vazio')
                    else:
                        ok = update_player(pid, new_name.strip(), new_tag.strip() or None)
                        if ok:
                            st.success('Jogador atualizado')
                        else:
                            st.error('Erro ao atualizar')
            if st.button('Excluir jogador'):
                if delete_player(pid):
                    st.success('Jogador excluído')
                else:
                    st.error('Erro ao excluir')
            st.markdown('---')
            st.write(get_players(only_active=False))

# ---------------------------
# TEMPORADAS (APENAS ADMIN P/CRIAR/GERAR)
# ---------------------------
elif menu == "Temporadas":
    st.subheader("🗂️ Temporadas")
    if not st.session_state['is_admin']:
        st.info('Apenas administradores podem criar/ativar temporadas. Aqui está a lista:')
        st.dataframe(get_temporadas(), use_container_width=True)
    else:
        with st.form("criar_temp"):
            nome = st.text_input("Nome da Temporada", value=f"Temporada {datetime.utcnow().year}")
            criar = st.form_submit_button("Criar e Ativar")
            if criar:
                tid = create_temporada(nome)
                if tid:
                    st.success(f"Temporada criada e ativada: {nome} (ID {tid})")
                else:
                    st.error("Erro ao criar temporada")
        st.markdown("---")
        temporadas = get_temporadas()
        st.dataframe(temporadas, use_container_width=True)

        st.markdown("### Gerar confrontos para a temporada ativa")
        active = get_active_temporada()
        if active is None:
            st.info("Não há temporada ativa.")
        else:
            st.write(f"Temporada ativa: {active.get('nome')} (ID {active.get('id')})")
            if st.button("Gerar Round-Robin para temporada ativa"):
                msg = gerar_round_robin(active.get('id'))
                if msg:
                    st.success(msg)
                else:
                    st.error("Erro ao gerar confrontos")
                st.experimental_rerun()

# ---------------------------
# HISTÓRICO INDIVIDUAL
# ---------------------------
elif menu == "Histórico Individual":
    st.subheader("📜 Histórico Individual")
    active = get_active_temporada()
    if active is None:
        st.info("Nenhuma temporada ativa.")
    else:
        players = get_players()
        if players.empty:
            st.info('Nenhum jogador cadastrado.')
        else:
            sel = st.selectbox("Selecione Jogador", players['nome'].tolist())
            pid = players[players['nome']==sel]['id'].iloc[0]
            hist = get_historico_jogador(active.get('id'), pid)
            if hist.empty:
                st.info("Nenhum confronto registrado para esse jogador nesta temporada.")
            else:
                st.dataframe(hist[['rodada','jogador1','jogador2','estrelas_j1','estrelas_j2','porc_j1','porc_j2','tempo_j1','tempo_j2','resultado']], use_container_width=True)

# ---------------------------
# FIM
# ---------------------------
st.markdown("---")
st.caption("Sistema com Firebase: dados em tempo real e escalável. (Exportação CSV temporariamente removida)")