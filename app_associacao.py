import streamlit as st
from supabase import create_client
from datetime import date, datetime
import pandas as pd
import urllib.parse

st.set_page_config(page_title="Controle de Associação", page_icon="🤝", layout="wide")

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
except Exception:
    st.error("❌ Secrets não encontrados.")
    st.stop()

try:
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Erro ao conectar: {e}")
    st.stop()

ANO_ATUAL = datetime.now().year

st.markdown("""
<style>
    .stButton > button { background-color:#0f766e; color:white; border-radius:8px; font-weight:bold; }
    .stButton > button:hover { background-color:#0d5e57; }
</style>""", unsafe_allow_html=True)

# ── Utilitários ───────────────────────────────────────────────────────────────
def validar_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0]*11: return False
    soma = sum(int(cpf[i])*(10-i) for i in range(9))
    if (soma*10%11)%10 != int(cpf[9]): return False
    soma = sum(int(cpf[i])*(11-i) for i in range(10))
    return (soma*10%11)%10 == int(cpf[10])

def fmt_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, cpf or ""))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf)==11 else cpf

def fmt_data(d):
    if not d: return "—"
    try: return datetime.strptime(str(d), "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return str(d)

def tel_com_ddi(tel):
    if not tel: return None
    t = ''.join(filter(str.isdigit, tel))
    return ("55"+t) if not t.startswith("55") else t

def wa_link(telefone, msg):
    tel = tel_com_ddi(telefone)
    if not tel: return None
    return f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"

# ── Banco ─────────────────────────────────────────────────────────────────────
def buscar_associados():
    return db.table("assoc_associados").select("*").eq("ativo",True).order("nome").execute().data or []

def buscar_pagamentos_ano(ano):
    return db.table("assoc_pagamentos").select("*").eq("ano_referencia",ano).execute().data or []

def buscar_por_nome(termo):
    return db.table("assoc_associados").select("*").eq("ativo",True).ilike("nome", f"%{termo}%").order("nome").execute().data or []

def buscar_por_cpf(cpf):
    try:
        return db.table("assoc_associados").select("*").eq("cpf",''.join(filter(str.isdigit,cpf))).single().execute().data
    except: return None

# ── Dados globais ─────────────────────────────────────────────────────────────
associados = buscar_associados()
pagamentos = buscar_pagamentos_ano(ANO_ATUAL)
ids_pagos  = {p["associado_id"] for p in pagamentos}
total      = len(associados)
n_pagos    = sum(1 for a in associados if a["id"] in ids_pagos)
n_inad     = total - n_pagos
arrecadado = sum(p["valor"] for p in pagamentos)
valor_ref  = next((p["valor"] for p in pagamentos), 0.0)  # valor mais recente como referência
em_aberto  = n_inad * valor_ref if valor_ref else 0.0

# ── Cabeçalho + Métricas ──────────────────────────────────────────────────────
st.title("🤝 Controle de Associação")
st.caption(f"Ano de referência: **{ANO_ATUAL}**")

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("👥 Associados",      total)
c2.metric("✅ Pagaram",         n_pagos)
c3.metric("❌ Inadimplentes",   n_inad)
c4.metric("💰 Arrecadado",     f"R$ {arrecadado:,.2f}")
c5.metric("⏳ Em Aberto",      f"R$ {em_aberto:,.2f}")
st.markdown("---")

# ── Abas ──────────────────────────────────────────────────────────────────────
aba1,aba2,aba3,aba4,aba5,aba6 = st.tabs([
    "📋 Painel Geral",
    "➕ Cadastrar Associado",
    "🚀 Gerar Anuidade",
    "💳 Registrar Pagamento",
    "📊 Relatórios",
    "🗂️ Histórico",
])

# ═══ ABA 1 — PAINEL GERAL ════════════════════════════════════════════════════
with aba1:
    st.subheader("Status de Anuidade")
    col_f1, col_f2 = st.columns([2,1])
    with col_f1:
        filtro = st.selectbox("Filtrar:", ["Todos","Pagos","Inadimplentes / Em Aberto"])
    with col_f2:
        busca_painel = st.text_input("🔍 Buscar por nome", key="busca_painel")

    linhas = []
    for a in associados:
        pago = a["id"] in ids_pagos
        if filtro == "Pagos" and not pago: continue
        if filtro == "Inadimplentes / Em Aberto" and pago: continue
        if busca_painel and busca_painel.lower() not in a["nome"].lower(): continue
        pg = next((p for p in pagamentos if p["associado_id"]==a["id"]), None)
        linhas.append({
            "Nome":     a["nome"],
            "CPF":      fmt_cpf(a["cpf"]),
            "Telefone": a.get("telefone") or "—",
            "Status":   "✅ Pago" if pago else "❌ Em Aberto",
            "Valor":    f"R$ {pg['valor']:.2f}" if pg else "—",
            "Data":     fmt_data(pg["data_pagamento"]) if pg else "—",
            "Forma":    pg["forma"] if pg else "—",
            "_tel":     tel_com_ddi(a.get("telefone")),
            "_nome":    a["nome"],
        })

    if not linhas:
        st.info("Nenhum resultado.")
    else:
        df = pd.DataFrame(linhas)
        st.dataframe(df.drop(columns=["_tel","_nome"]), use_container_width=True, hide_index=True)

        if filtro == "Inadimplentes / Em Aberto":
            st.markdown("### 📲 Cobrar pelo WhatsApp")
            for r in linhas:
                if r["_tel"]:
                    msg = f"Olá {r['_nome']}, sua anuidade {ANO_ATUAL} está em aberto. Podemos acertar? 🤝"
                    st.markdown(f"[📲 {r['_nome']}](https://wa.me/{r['_tel']}?text={urllib.parse.quote(msg)})")

        csv = df.drop(columns=["_tel","_nome"]).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Exportar CSV", csv, f"status_{ANO_ATUAL}.csv", "text/csv")

# ═══ ABA 2 — CADASTRAR ═══════════════════════════════════════════════════════
with aba2:
    st.subheader("Novo Associado")

    if st.session_state.get("cadastro_ok"):
        st.success(f"✅ **{st.session_state.get('ultimo_nome','')}** cadastrado com sucesso!")
        st.session_state.cadastro_ok = False

    with st.form("form_assoc", clear_on_submit=True):
        st.markdown("**Dados Pessoais**")
        ca1, ca2 = st.columns(2)
        with ca1:
            nome   = st.text_input("Nome completo *")
            cpf_in = st.text_input("CPF * (somente números)")
            tel_in = st.text_input("DDD + Telefone * (ex: 17999998888)")
        with ca2:
            nasc = st.date_input("Data de nascimento", value=None,
                                 min_value=date(1920,1,1), max_value=date.today(),
                                 format="DD/MM/YYYY")

        st.markdown("**Endereço**")
        ce1, ce2 = st.columns(2)
        with ce1:
            rua    = st.text_input("Rua / Avenida")
            bairro = st.text_input("Bairro")
        with ce2:
            cidade = st.text_input("Cidade")
            cuf, ccep = st.columns(2)
            with cuf:
                uf = st.selectbox("Estado",[
                    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
                    "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"
                ], index=25)
            with ccep:
                cep = st.text_input("CEP")

        if st.form_submit_button("✅ Salvar Associado"):
            erros = []
            if not nome:                  erros.append("Nome é obrigatório.")
            if not cpf_in:                erros.append("CPF é obrigatório.")
            elif not validar_cpf(cpf_in): erros.append("CPF inválido.")
            if not tel_in:                erros.append("Telefone é obrigatório.")
            if erros:
                for e in erros: st.error(e)
            else:
                partes = [x for x in [
                    rua.strip().title() if rua else None,
                    bairro.strip().title() if bairro else None,
                    cidade.strip().title() if cidade else None,
                    uf,
                    ("CEP "+''.join(filter(str.isdigit,cep))) if cep else None
                ] if x]
                try:
                    db.table("assoc_associados").insert({
                        "nome":       nome.strip().title(),
                        "cpf":        ''.join(filter(str.isdigit,cpf_in)),
                        "telefone":   ''.join(filter(str.isdigit,tel_in)),
                        "nascimento": str(nasc) if nasc else None,
                        "endereco":   ", ".join(partes) if partes else None,
                    }).execute()
                    st.session_state.cadastro_ok = True
                    st.session_state.ultimo_nome = nome.strip().title()
                    st.rerun()
                except Exception as e:
                    if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                        st.error("⚠️ CPF já cadastrado.")
                    else:
                        st.error(f"Erro: {e}")

    st.markdown("---")
    st.subheader("🗂️ Associados Cadastrados")
    assoc_fresh = buscar_associados()
    if assoc_fresh:
        st.dataframe(pd.DataFrame([{
            "Nome":       a["nome"],
            "CPF":        fmt_cpf(a["cpf"]),
            "Telefone":   a.get("telefone") or "—",
            "Nascimento": fmt_data(a.get("nascimento")),
            "Endereço":   a.get("endereco") or "—",
        } for a in assoc_fresh]), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum associado cadastrado ainda.")

# ═══ ABA 3 — GERAR ANUIDADE ══════════════════════════════════════════════════
with aba3:
    st.subheader("🚀 Gerar Anuidade para Todos os Associados")
    st.info("Lança a anuidade para todos os associados ativos de uma vez. Quem já tiver lançamento no ano selecionado é ignorado.")

    with st.form("form_gerar"):
        cg1,cg2,cg3 = st.columns(3)
        with cg1: ano_gerar   = st.number_input("Ano", 2020, 2030, ANO_ATUAL)
        with cg2: valor_anuid = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
        with cg3: vencimento  = st.date_input("Vencimento", value=date(ANO_ATUAL,12,31), format="DD/MM/YYYY")
        enviar_wa = st.checkbox("📲 Mostrar links WhatsApp para notificar")

        if st.form_submit_button("🚀 Gerar para Todos"):
            if valor_anuid <= 0:
                st.error("Informe um valor válido.")
            else:
                pgs_ano      = buscar_pagamentos_ano(int(ano_gerar))
                ids_lancados = {p["associado_id"] for p in pgs_ano}
                todos        = buscar_associados()
                pendentes    = [a for a in todos if a["id"] not in ids_lancados]

                if not pendentes:
                    st.warning(f"Todos os associados já têm anuidade lançada para {int(ano_gerar)}.")
                else:
                    try:
                        db.table("assoc_pagamentos").insert([{
                            "associado_id":   a["id"],
                            "ano_referencia": int(ano_gerar),
                            "valor":          float(valor_anuid),
                            "data_pagamento": str(vencimento),
                            "forma":          "PIX",
                            "observacao":     f"Anuidade {int(ano_gerar)} — lançamento em lote",
                        } for a in pendentes]).execute()

                        st.success(f"✅ Anuidade {int(ano_gerar)} gerada para **{len(pendentes)} associados** — R$ {valor_anuid:.2f} cada.")
                        st.dataframe(pd.DataFrame([{
                            "Nome": a["nome"], "CPF": fmt_cpf(a["cpf"]), "Telefone": a.get("telefone") or "—"
                        } for a in pendentes]), use_container_width=True, hide_index=True)

                        if enviar_wa:
                            st.markdown("### 📲 Notificar pelo WhatsApp")
                            for a in pendentes:
                                if a.get("telefone"):
                                    msg = (f"Olá {a['nome']}, sua anuidade {int(ano_gerar)} foi gerada. "
                                           f"Valor: R$ {valor_anuid:.2f}. "
                                           f"Vencimento: {vencimento.strftime('%d/%m/%Y')}. Obrigado! 🤝")
                                    tel = tel_com_ddi(a["telefone"])
                                    st.markdown(f"[📲 {a['nome']}](https://wa.me/{tel}?text={urllib.parse.quote(msg)})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    st.markdown("---")
    st.subheader(f"Situação atual — {ANO_ATUAL}")
    pgs_atual    = buscar_pagamentos_ano(ANO_ATUAL)
    ids_lancados = {p["associado_id"] for p in pgs_atual}
    todos_ativos = buscar_associados()
    cr1,cr2,cr3  = st.columns(3)
    cr1.metric("Total de associados",  len(todos_ativos))
    cr2.metric("Com anuidade lançada", len(ids_lancados))
    cr3.metric("Sem lançamento ainda", len(todos_ativos)-len(ids_lancados))

# ═══ ABA 4 — REGISTRAR PAGAMENTO ═════════════════════════════════════════════
with aba4:
    st.subheader("Registrar Pagamento de Anuidade")
    st.caption("Busque o associado pelo nome, selecione e registre o pagamento.")

    # Busca por nome
    termo_pg = st.text_input("🔍 Digite o nome do associado", key="busca_pg")
    assoc_enc = None

    if termo_pg and len(termo_pg) >= 2:
        resultados = buscar_por_nome(termo_pg)
        if resultados:
            opcoes = {f"{a['nome']} — CPF: {fmt_cpf(a['cpf'])}": a for a in resultados}
            escolha = st.radio("Selecione o associado:", list(opcoes.keys()), key="radio_pg")
            assoc_enc = opcoes[escolha]

            # Status de pagamento
            if assoc_enc["id"] in ids_pagos:
                pg = next((p for p in pagamentos if p["associado_id"]==assoc_enc["id"]), None)
                st.warning(f"⚠️ Já consta pagamento em {fmt_data(pg['data_pagamento'])} — R$ {pg['valor']:.2f} via {pg['forma']}")
            else:
                st.info(f"📌 **{assoc_enc['nome']}** — anuidade {ANO_ATUAL} em aberto.")
        else:
            st.error("Nenhum associado encontrado com esse nome.")

    if assoc_enc:
        with st.form("form_pg", clear_on_submit=True):
            cp1,cp2 = st.columns(2)
            with cp1:
                ano_ref = st.number_input("Ano referência", 2020, 2030, ANO_ATUAL)
                valor   = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
            with cp2:
                forma   = st.selectbox("Forma", ["PIX","Dinheiro","Cartão","Transferência"])
                data_pg = st.date_input("Data do pagamento", value=date.today(), format="DD/MM/YYYY")
                obs     = st.text_input("Observação (opcional)")

            if st.form_submit_button("💳 Confirmar Pagamento"):
                if valor <= 0:
                    st.error("Valor inválido.")
                else:
                    db.table("assoc_pagamentos").insert({
                        "associado_id":   assoc_enc["id"],
                        "ano_referencia": int(ano_ref),
                        "valor":          float(valor),
                        "data_pagamento": str(data_pg),
                        "forma":          forma,
                        "observacao":     obs or None,
                    }).execute()
                    st.success(f"✅ Pagamento de **{assoc_enc['nome']}** registrado!")
                    if assoc_enc.get("telefone"):
                        msg = (f"Olá {assoc_enc['nome']}, confirmamos sua anuidade {int(ano_ref)}. "
                               f"Valor: R$ {valor:.2f} via {forma}. Obrigado! 🤝")
                        link = wa_link(assoc_enc["telefone"], msg)
                        if link: st.markdown(f"[📲 Enviar confirmação WhatsApp]({link})")
                    st.rerun()

# ═══ ABA 5 — RELATÓRIOS ══════════════════════════════════════════════════════
with aba5:
    st.subheader("📊 Relatórios")

    ano_rel = st.selectbox("Ano do relatório:", list(range(ANO_ATUAL, 2019, -1)), key="ano_rel")
    assoc_rel = buscar_associados()
    pgs_rel   = buscar_pagamentos_ano(ano_rel)
    ids_pg_rel = {p["associado_id"] for p in pgs_rel}

    pagos_rel  = [a for a in assoc_rel if a["id"] in ids_pg_rel]
    aberto_rel = [a for a in assoc_rel if a["id"] not in ids_pg_rel]
    total_pg_rel   = sum(p["valor"] for p in pgs_rel)
    valor_unit_rel = pgs_rel[0]["valor"] if pgs_rel else 0.0
    total_aberto_rel = len(aberto_rel) * valor_unit_rel

    # Cards de resumo
    st.markdown(f"### Resumo — {ano_rel}")
    r1,r2,r3,r4 = st.columns(4)
    r1.metric("Total de associados",   len(assoc_rel))
    r2.metric("✅ Pagos",              len(pagos_rel))
    r3.metric("❌ Em aberto",          len(aberto_rel))
    r4.metric("💰 Total arrecadado",  f"R$ {total_pg_rel:,.2f}")

    r5,r6,r7 = st.columns(3)
    r5.metric("⏳ Valor em aberto",   f"R$ {total_aberto_rel:,.2f}")
    r6.metric("📈 % Adimplência",     f"{(len(pagos_rel)/len(assoc_rel)*100):.1f}%" if assoc_rel else "—")
    r7.metric("📉 % Inadimplência",   f"{(len(aberto_rel)/len(assoc_rel)*100):.1f}%" if assoc_rel else "—")

    st.markdown("---")

    # Relatório por forma de pagamento
    if pgs_rel:
        st.markdown("### 💳 Arrecadação por Forma de Pagamento")
        df_forma = pd.DataFrame(pgs_rel).groupby("forma")["valor"].agg(["sum","count"]).reset_index()
        df_forma.columns = ["Forma","Total (R$)","Quantidade"]
        df_forma["Total (R$)"] = df_forma["Total (R$)"].apply(lambda x: f"R$ {x:,.2f}")
        st.dataframe(df_forma, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Lista de inadimplentes
    col_tab1, col_tab2 = st.tabs(["❌ Em Aberto (Inadimplentes)", "✅ Pagos"])

    with col_tab1:
        if aberto_rel:
            df_ab = pd.DataFrame([{
                "Nome":     a["nome"],
                "CPF":      fmt_cpf(a["cpf"]),
                "Telefone": a.get("telefone") or "—",
                "Endereço": a.get("endereco") or "—",
            } for a in aberto_rel])
            st.dataframe(df_ab, use_container_width=True, hide_index=True)

            st.markdown("### 📲 Cobrar pelo WhatsApp")
            for a in aberto_rel:
                if a.get("telefone"):
                    msg = (f"Olá {a['nome']}, sua anuidade {ano_rel} está em aberto. "
                           f"Valor: R$ {valor_unit_rel:.2f}. Podemos acertar? 🤝")
                    tel = tel_com_ddi(a["telefone"])
                    st.markdown(f"[📲 {a['nome']}](https://wa.me/{tel}?text={urllib.parse.quote(msg)})")

            csv_ab = df_ab.to_csv(index=False).encode("utf-8")
            st.download_button(f"⬇️ Exportar inadimplentes {ano_rel}", csv_ab, f"inadimplentes_{ano_rel}.csv", "text/csv")
        else:
            st.success(f"🎉 Todos os associados pagaram a anuidade de {ano_rel}!")

    with col_tab2:
        if pagos_rel:
            df_pg = pd.DataFrame([{
                "Nome":  a["nome"],
                "CPF":   fmt_cpf(a["cpf"]),
                "Valor": f"R$ {next((p['valor'] for p in pgs_rel if p['associado_id']==a['id']),0):.2f}",
                "Data":  fmt_data(next((p['data_pagamento'] for p in pgs_rel if p['associado_id']==a['id']),None)),
                "Forma": next((p['forma'] for p in pgs_rel if p['associado_id']==a['id']),"—"),
            } for a in pagos_rel])
            st.dataframe(df_pg, use_container_width=True, hide_index=True)
            csv_pg = df_pg.to_csv(index=False).encode("utf-8")
            st.download_button(f"⬇️ Exportar pagos {ano_rel}", csv_pg, f"pagos_{ano_rel}.csv", "text/csv")
        else:
            st.info(f"Nenhum pagamento registrado em {ano_rel}.")

# ═══ ABA 6 — HISTÓRICO ═══════════════════════════════════════════════════════
with aba6:
    st.subheader("🗂️ Histórico Completo de Pagamentos")
    ano_hist = st.selectbox("Ano:", list(range(ANO_ATUAL, 2019, -1)), key="ano_hist")
    pgs = db.table("assoc_pagamentos").select("*, assoc_associados(nome,cpf)").eq("ano_referencia",ano_hist).order("data_pagamento",desc=True).execute().data or []
    if pgs:
        df_h = pd.DataFrame([{
            "Nome":  (p.get("assoc_associados") or {}).get("nome","—"),
            "CPF":   fmt_cpf((p.get("assoc_associados") or {}).get("cpf","")),
            "Valor": f"R$ {p['valor']:.2f}",
            "Data":  fmt_data(p["data_pagamento"]),
            "Forma": p["forma"],
            "Obs":   p.get("observacao") or "—",
        } for p in pgs])
        st.dataframe(df_h, use_container_width=True, hide_index=True)
        st.metric("Total registrado", f"R$ {sum(p['valor'] for p in pgs):,.2f}")
        st.download_button(f"⬇️ Exportar {ano_hist}", df_h.to_csv(index=False).encode("utf-8"), f"historico_{ano_hist}.csv","text/csv")
    else:
        st.info(f"Nenhum registro em {ano_hist}.")
