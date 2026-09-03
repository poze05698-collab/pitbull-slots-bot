from telebot import types
from html import escape
from datetime import datetime, timedelta

from database import conn, cursor
from utils import data_atual, dinheiro, tem_permissao_admin, criar_notificacao

# =====================================================
# MISSÕES ADMINISTRÁVEIS
# =====================================================
# As missões deixam de ficar fixas no código. O administrador
# cria, pausa, edita e exclui pelo próprio painel.
#
# Tipos disponíveis:
#   indicacoes_aprovadas -> somente indicações realmente aprovadas
#   ganhos               -> ganhos positivos registrados no histórico
#   saques_pagos         -> saques com status PAGO/APROVADO
#
# Recorrência:
#   unica, diaria, semanal, periodo
# =====================================================

ESTADOS = {}
ESTADO_TTL = 300

TIPOS = {
    "indicacoes_aprovadas": "👥 Indicações aprovadas",
    "ganhos": "💰 Ganhos acumulados",
    "saques_pagos": "💸 Saques pagos",
}

RECORRENCIAS = {
    "unica": "🏁 Única",
    "diaria": "📅 Diária",
    "semanal": "🗓️ Semanal",
    "periodo": "⏳ Período definido",
}


def preparar_banco():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS missoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            meta REAL NOT NULL,
            recompensa REAL DEFAULT 0,
            link_desbloqueado TEXT DEFAULT '',
            recorrencia TEXT NOT NULL DEFAULT 'unica',
            inicio TEXT DEFAULT '',
            fim TEXT DEFAULT '',
            ativa INTEGER DEFAULT 1,
            criada_em TEXT,
            atualizada_em TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS missoes_conclusoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            missao_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            periodo_chave TEXT NOT NULL,
            progresso REAL DEFAULT 0,
            recompensa REAL DEFAULT 0,
            concluida_em TEXT,
            UNIQUE(missao_id, usuario_id, periodo_chave),
            FOREIGN KEY(missao_id) REFERENCES missoes(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_missoes_ativas ON missoes(ativa)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_missoes_conclusoes_usuario ON missoes_conclusoes(usuario_id, missao_id)")
    conn.commit()


def _agora():
    return datetime.now()


def _parse_data(valor):
    valor = (valor or "").strip()
    if not valor:
        return None
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            pass
    return None


def _parse_data_banco(valor):
    valor = (valor or "").strip()
    if not valor:
        return None
    for formato in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            pass
    return None


def _periodo(missao):
    """Retorna (inicio, fim, chave) para calcular a missão no período atual."""
    mid, nome, tipo, meta, recompensa, link, recorrencia, inicio, fim, ativa, *_ = missao
    agora = _agora()

    if recorrencia == "diaria":
        inicio_p = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        fim_p = inicio_p + timedelta(days=1)
        chave = inicio_p.strftime("%Y-%m-%d")
        return inicio_p, fim_p, chave

    if recorrencia == "semanal":
        inicio_p = (agora - timedelta(days=agora.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        fim_p = inicio_p + timedelta(days=7)
        chave = inicio_p.strftime("%Y-W%W")
        return inicio_p, fim_p, chave

    if recorrencia == "periodo":
        inicio_p = _parse_data(inicio) or agora
        fim_p = _parse_data(fim)
        chave = f"periodo:{mid}"
        return inicio_p, fim_p, chave

    return None, None, "unica"


def _missao_esta_no_periodo(missao):
    recorrencia = missao[6]
    agora = _agora()
    if recorrencia != "periodo":
        return True
    inicio = _parse_data(missao[7])
    fim = _parse_data(missao[8])
    if inicio and agora < inicio:
        return False
    if fim and agora >= fim:
        return False
    return True


def _progresso(missao, usuario_id):
    inicio, fim, _ = _periodo(missao)
    tipo = missao[2]

    def dentro_periodo(texto_data):
        if not inicio and not fim:
            return True
        dt = _parse_data_banco(texto_data)
        if not dt:
            return False
        if inicio and dt < inicio:
            return False
        if fim and dt >= fim:
            return False
        return True

    if tipo == "indicacoes_aprovadas":
        cursor.execute(
            "SELECT data_aprovacao FROM indicacoes WHERE indicador_id=? AND status='APROVADO'",
            (usuario_id,)
        )
        return float(sum(1 for (data,) in cursor.fetchall() if dentro_periodo(data)))

    if tipo == "ganhos":
        cursor.execute(
            "SELECT valor, data FROM historico WHERE usuario_id=? AND valor>0 AND tipo!='MISSAO'",
            (usuario_id,)
        )
        return float(sum(float(valor or 0) for valor, data in cursor.fetchall() if dentro_periodo(data)))

    if tipo == "saques_pagos":
        cursor.execute(
            "SELECT data_aprovacao FROM saques WHERE usuario_id=? AND status IN ('PAGO','APROVADO')",
            (usuario_id,)
        )
        return float(sum(1 for (data,) in cursor.fetchall() if dentro_periodo(data)))

    return 0.0


def _concluida(missao_id, usuario_id, periodo_chave):
    cursor.execute(
        "SELECT 1 FROM missoes_conclusoes WHERE missao_id=? AND usuario_id=? AND periodo_chave=?",
        (missao_id, usuario_id, periodo_chave)
    )
    return cursor.fetchone() is not None


def _esc(valor):
    return escape(str(valor or ""))


def atualizar_missoes_usuario(usuario_id):
    """Confere todas as missões ativas e paga cada conclusão uma única vez."""
    preparar_banco()
    cursor.execute("""
        SELECT id, nome, tipo, meta, recompensa, link_desbloqueado,
               recorrencia, inicio, fim, ativa, criada_em, atualizada_em
        FROM missoes
        WHERE ativa=1
        ORDER BY id DESC
    """)
    missoes = cursor.fetchall()
    concluidas = []

    for missao in missoes:
        if not _missao_esta_no_periodo(missao):
            continue

        inicio, fim, periodo_chave = _periodo(missao)
        progresso = _progresso(missao, usuario_id)
        meta = float(missao[3])

        if progresso < meta:
            continue
        if _concluida(missao[0], usuario_id, periodo_chave):
            continue

        recompensa = max(0.0, float(missao[4] or 0))

        try:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("""
                INSERT INTO missoes_conclusoes
                (missao_id, usuario_id, periodo_chave, progresso, recompensa, concluida_em)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                missao[0], usuario_id, periodo_chave, progresso,
                recompensa, data_atual()
            ))
            if cursor.rowcount != 1:
                conn.rollback()
                continue

            if recompensa > 0:
                cursor.execute(
                    "UPDATE usuarios SET saldo=COALESCE(saldo,0)+? WHERE id=?",
                    (recompensa, usuario_id)
                )
                cursor.execute("""
                    INSERT INTO historico(usuario_id, tipo, descricao, valor, data)
                    VALUES (?, 'MISSAO', ?, ?, ?)
                """, (
                    usuario_id,
                    f"Missão concluída: {missao[1]}",
                    recompensa,
                    data_atual()
                ))

            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            continue

        concluidas.append(missao)

        texto = (
            f"🎯 <b>MISSÃO CONCLUÍDA!</b>\n\n"
            f"🏆 <b>{_esc(missao[1])}</b>\n\n"
            f"📈 Meta atingida: <b>{progresso:g}/{meta:g}</b>\n"
            f"💰 Recompensa: <b>{dinheiro(recompensa)}</b>"
        )
        link = (missao[5] or "").strip()
        if link:
            texto += "\n\n🔓 <b>LINK DESBLOQUEADO:</b>\n" + _esc(link)

        try:
            mensagem_notificacao = f"{missao[1]} — recompensa: {dinheiro(recompensa)}"
            if (missao[5] or "").strip():
                mensagem_notificacao += f" — link desbloqueado: {missao[5]}"
            criar_notificacao(
                usuario_id,
                "🎯 Missão concluída",
                mensagem_notificacao
            )
        except Exception:
            pass

        # A mensagem direta é feita pelo handler que chamou esta função
        # quando necessário; retornar a missão evita envio duplicado.

    return concluidas


def _mostrar_missoes_usuario(bot, chat_id, usuario_id):
    preparar_banco()
    concluidas = atualizar_missoes_usuario(usuario_id)
    for missao in concluidas:
        inicio, fim, periodo_chave = _periodo(missao)
        progresso = _progresso(missao, usuario_id)
        texto = (
            f"🎯 <b>MISSÃO CONCLUÍDA!</b>\n\n"
            f"🏆 <b>{_esc(missao[1])}</b>\n"
            f"📈 {progresso:g}/{float(missao[3]):g}\n"
            f"💰 Recompensa: <b>{dinheiro(missao[4])}</b>"
        )
        if (missao[5] or "").strip():
            texto += f"\n\n🔓 <b>LINK DESBLOQUEADO:</b>\n{_esc(missao[5])}"
        bot.send_message(chat_id, texto, parse_mode="HTML")

    cursor.execute("""
        SELECT id, nome, tipo, meta, recompensa, link_desbloqueado,
               recorrencia, inicio, fim, ativa, criada_em, atualizada_em
        FROM missoes
        WHERE ativa=1
        ORDER BY id DESC
    """)
    missoes = cursor.fetchall()

    if not missoes:
        bot.send_message(
            chat_id,
            "🎯 <b>MISSÕES</b>\n\nNo momento não há missões ativas.",
            parse_mode="HTML"
        )
        return

    linhas = ["🎯 <b>MISSÕES ATIVAS</b>", ""]
    for missao in missoes:
        if not _missao_esta_no_periodo(missao):
            continue
        progresso = _progresso(missao, usuario_id)
        meta = float(missao[3])
        _, _, periodo_chave = _periodo(missao)
        feita = _concluida(missao[0], usuario_id, periodo_chave)
        marca = "✅" if feita else "⏳"
        linhas.append(
            f"{marca} <b>{_esc(missao[1])}</b>\n"
            f"📈 {progresso:g}/{meta:g}\n"
            f"💰 Recompensa: {dinheiro(missao[4])}"
        )
        if missao[5]:
            linhas.append("🔓 Link ao concluir")
        linhas.append("")

    bot.send_message(chat_id, "\n".join(linhas), parse_mode="HTML")


def _tem_permissao(uid):
    try:
        return tem_permissao_admin(uid, "gamificacao")
    except Exception:
        return False


def _painel_admin(bot, chat_id, mensagem=None):
    preparar_banco()
    cursor.execute("SELECT COUNT(*) FROM missoes WHERE ativa=1")
    ativas = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM missoes")
    total = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM missoes_conclusoes")
    conclusoes = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COALESCE(SUM(recompensa),0) FROM missoes_conclusoes")
    pago = float(cursor.fetchone()[0] or 0)

    texto = (
        "🎯 <b>GERENCIADOR DE MISSÕES</b>\n\n"
        f"🟢 Ativas: <b>{ativas}</b>\n"
        f"📋 Total criadas: <b>{total}</b>\n"
        f"🏆 Conclusões: <b>{conclusoes}</b>\n"
        f"💰 Recompensas pagas: <b>{dinheiro(pago)}</b>"
    )
    if mensagem:
        texto += "\n\n" + mensagem

    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("➕ Criar missão", callback_data="mis_admin_criar"))
    kb.row(types.InlineKeyboardButton("📋 Ver missões", callback_data="mis_admin_lista"))
    kb.row(types.InlineKeyboardButton("📊 Estatísticas", callback_data="mis_admin_stats"))
    bot.send_message(chat_id, texto, parse_mode="HTML", reply_markup=kb)


def _lista_admin(bot, chat_id):
    cursor.execute("""
        SELECT id, nome, tipo, meta, recompensa, link_desbloqueado,
               recorrencia, inicio, fim, ativa, criada_em, atualizada_em
        FROM missoes ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    if not rows:
        _painel_admin(bot, chat_id, "📋 Nenhuma missão criada ainda.")
        return

    for m in rows:
        status = "🟢 ATIVA" if m[9] else "⏸️ PAUSADA"
        periodo = RECORRENCIAS.get(m[6], m[6])
        texto = (
            f"🎯 <b>#{m[0]} — {_esc(m[1])}</b>\n\n"
            f"{status}\n"
            f"📌 Tipo: {_esc(TIPOS.get(m[2], m[2]))}\n"
            f"🎯 Meta: <b>{float(m[3]):g}</b>\n"
            f"💰 Recompensa: <b>{dinheiro(m[4])}</b>\n"
            f"🔁 Periodicidade: {_esc(periodo)}"
        )
        if m[6] == "periodo":
            texto += f"\n📅 {m[7] or '-'} até {m[8] or '-'}"
        if m[5]:
            texto += f"\n🔓 Link: {_esc(m[5])}"

        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("✏️ Editar", callback_data=f"mis_edit:{m[0]}"),
            types.InlineKeyboardButton("▶️ Ativar" if not m[9] else "⏸️ Pausar", callback_data=f"mis_toggle:{m[0]}")
        )
        kb.row(
            types.InlineKeyboardButton("📊 Resultados", callback_data=f"mis_stats:{m[0]}"),
            types.InlineKeyboardButton("🗑️ Excluir", callback_data=f"mis_delete:{m[0]}")
        )
        bot.send_message(chat_id, texto, parse_mode="HTML", reply_markup=kb)

    bot.send_message(chat_id, "⬅️ Volte ao <b>Gerenciador de Missões</b> para criar ou consultar novamente.", parse_mode="HTML")


def _pedir_link(bot, chat_id, uid):
    ESTADOS[uid]["etapa"] = "link"
    bot.send_message(
        chat_id,
        "🔓 <b>LINK AO CONCLUIR</b>\n\n"
        "Envie o link que será liberado quando a missão for concluída.\n"
        "Se não quiser link, envie <code>/pular</code>.",
        parse_mode="HTML"
    )


def registrar(bot):
    preparar_banco()

    # ---------------- USUÁRIO ----------------
    @bot.message_handler(func=lambda m: m.text == "🎯 Missões")
    def missoes_usuario(message):
        uid = message.from_user.id
        _mostrar_missoes_usuario(bot, message.chat.id, uid)

    # ---------------- ADMIN ----------------
    @bot.message_handler(func=lambda m: m.text == "🎯 Gerenciar Missões")
    def gerenciar_missoes(message):
        if not _tem_permissao(message.from_user.id):
            bot.send_message(message.chat.id, "❌ Você não possui permissão para gerenciar missões.")
            return
        _painel_admin(bot, message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data == "mis_admin_criar")
    def admin_criar(call):
        if not _tem_permissao(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        ESTADOS[call.from_user.id] = {"acao": "criar", "etapa": "nome", "criado_em": _agora().timestamp()}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "➕ <b>NOVA MISSÃO</b>\n\nEnvie o <b>nome</b> da missão.\n\nExemplo: <i>Convide 5 pessoas para se cadastrar</i>", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "mis_admin_lista")
    def admin_lista(call):
        if not _tem_permissao(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        _lista_admin(bot, call.message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data == "mis_admin_stats")
    def admin_stats(call):
        if not _tem_permissao(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        preparar_banco()
        cursor.execute("SELECT COUNT(*) FROM missoes_conclusoes")
        total = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(DISTINCT usuario_id) FROM missoes_conclusoes")
        usuarios = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(SUM(recompensa),0) FROM missoes_conclusoes")
        pago = float(cursor.fetchone()[0] or 0)
        cursor.execute("SELECT COUNT(*) FROM missoes WHERE ativa=1")
        ativas = cursor.fetchone()[0] or 0
        _painel_admin(bot, call.message.chat.id, f"📊 <b>RESULTADO GERAL</b>\n\n👥 Usuários que concluíram: <b>{usuarios}</b>\n🏆 Conclusões: <b>{total}</b>\n💰 Total pago: <b>{dinheiro(pago)}</b>\n🟢 Missões ativas: <b>{ativas}</b>")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mis_type:"))
    def escolher_tipo(call):
        uid = call.from_user.id
        if not _tem_permissao(uid) or uid not in ESTADOS:
            bot.answer_callback_query(call.id, "Sessão expirada.", show_alert=True)
            return
        tipo = call.data.split(":", 1)[1]
        if tipo not in TIPOS:
            return
        ESTADOS[uid]["tipo"] = tipo
        ESTADOS[uid]["etapa"] = "meta"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🎯 Envie a <b>meta numérica</b>.\n\nExemplo: <code>5</code>", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mis_rec:"))
    def escolher_recorrencia(call):
        uid = call.from_user.id
        estado = ESTADOS.get(uid)
        if not _tem_permissao(uid) or not estado:
            bot.answer_callback_query(call.id, "Sessão expirada.", show_alert=True)
            return
        rec = call.data.split(":", 1)[1]
        if rec not in RECORRENCIAS:
            return
        estado["recorrencia"] = rec
        bot.answer_callback_query(call.id)
        if rec == "periodo":
            estado["etapa"] = "inicio"
            bot.send_message(call.message.chat.id, "📅 Envie a <b>data/hora de início</b> no formato:\n<code>2026-09-05 00:00</code>", parse_mode="HTML")
        else:
            _pedir_link(bot, call.message.chat.id, uid)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mis_edit:"))
    def editar_missao(call):
        uid = call.from_user.id
        if not _tem_permissao(uid):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        mid = int(call.data.split(":", 1)[1])
        ESTADOS[uid] = {"acao": "editar", "missao_id": mid, "etapa": "campo", "criado_em": _agora().timestamp()}
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("✏️ Nome", callback_data=f"mis_campo:{mid}:nome"), types.InlineKeyboardButton("🎯 Meta", callback_data=f"mis_campo:{mid}:meta"))
        kb.row(types.InlineKeyboardButton("💰 Recompensa", callback_data=f"mis_campo:{mid}:recompensa"), types.InlineKeyboardButton("🔓 Link", callback_data=f"mis_campo:{mid}:link"))
        kb.row(types.InlineKeyboardButton("⬅️ Cancelar", callback_data="mis_cancelar"))
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✏️ <b>O QUE DESEJA ALTERAR?</b>", parse_mode="HTML", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mis_campo:"))
    def editar_campo(call):
        uid = call.from_user.id
        estado = ESTADOS.get(uid)
        if not _tem_permissao(uid) or not estado:
            bot.answer_callback_query(call.id, "Sessão expirada.", show_alert=True)
            return
        _, mid, campo = call.data.split(":", 2)
        estado.update({"missao_id": int(mid), "campo": campo, "etapa": "editar_valor"})
        bot.answer_callback_query(call.id)
        prompts = {
            "nome": "Envie o novo <b>nome</b>.",
            "meta": "Envie a nova <b>meta numérica</b>.",
            "recompensa": "Envie a nova <b>recompensa em R$</b>. Exemplo: <code>5.00</code>",
            "link": "Envie o novo <b>link</b> ou <code>/pular</code> para remover.",
        }
        bot.send_message(call.message.chat.id, "✏️ " + prompts[campo], parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mis_toggle:"))
    def alternar_missao(call):
        if not _tem_permissao(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        mid = int(call.data.split(":", 1)[1])
        cursor.execute("UPDATE missoes SET ativa=CASE WHEN ativa=1 THEN 0 ELSE 1 END, atualizada_em=? WHERE id=?", (data_atual(), mid))
        conn.commit()
        bot.answer_callback_query(call.id, "Status atualizado.")
        _lista_admin(bot, call.message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mis_delete:"))
    def excluir_missao(call):
        if not _tem_permissao(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        mid = int(call.data.split(":", 1)[1])
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("✅ Sim, excluir", callback_data=f"mis_delete_yes:{mid}"), types.InlineKeyboardButton("❌ Cancelar", callback_data="mis_cancelar"))
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"⚠️ Excluir a missão <b>#{mid}</b>? O histórico de conclusões também será removido.", parse_mode="HTML", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mis_delete_yes:"))
    def excluir_missao_confirmar(call):
        if not _tem_permissao(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        mid = int(call.data.split(":", 1)[1])
        cursor.execute("DELETE FROM missoes_conclusoes WHERE missao_id=?", (mid,))
        cursor.execute("DELETE FROM missoes WHERE id=?", (mid,))
        conn.commit()
        bot.answer_callback_query(call.id, "Missão excluída.")
        _painel_admin(bot, call.message.chat.id, f"🗑️ Missão <b>#{mid}</b> excluída.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("mis_stats:"))
    def estatistica_missao(call):
        if not _tem_permissao(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        mid = int(call.data.split(":", 1)[1])
        cursor.execute("SELECT nome, meta, recompensa, recorrencia FROM missoes WHERE id=?", (mid,))
        m = cursor.fetchone()
        if not m:
            bot.answer_callback_query(call.id, "Missão não encontrada.", show_alert=True)
            return
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT usuario_id), COALESCE(SUM(recompensa),0) FROM missoes_conclusoes WHERE missao_id=?", (mid,))
        total, usuarios, pago = cursor.fetchone()
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"📊 <b>RESULTADOS — #{mid}</b>\n\n🏆 Conclusões: <b>{total}</b>\n👥 Usuários: <b>{usuarios}</b>\n💰 Pago: <b>{dinheiro(pago)}</b>\n🎯 Meta: <b>{float(m[1]):g}</b>\n🔁 {escape(RECORRENCIAS.get(m[3], m[3]))}", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "mis_cancelar")
    def cancelar_missao(call):
        ESTADOS.pop(call.from_user.id, None)
        bot.answer_callback_query(call.id, "Cancelado.")
        _painel_admin(bot, call.message.chat.id)

    @bot.message_handler(func=lambda m: m.from_user.id in ESTADOS and _tem_permissao(m.from_user.id))
    def receber_estado_missao(message):
        uid = message.from_user.id
        estado = ESTADOS.get(uid)
        if not estado:
            return
        if _agora().timestamp() - estado.get("criado_em", 0) > ESTADO_TTL:
            ESTADOS.pop(uid, None)
            bot.send_message(message.chat.id, "⏱️ A sessão de criação/edição expirou. Abra o gerenciador novamente.")
            return

        texto = (message.text or "").strip()
        etapa = estado.get("etapa")

        if estado.get("acao") == "editar" and etapa == "editar_valor":
            campo = estado.get("campo")
            mid = estado.get("missao_id")
            if campo == "nome":
                if not texto or len(texto) > 100:
                    bot.send_message(message.chat.id, "❌ Nome inválido. Use até 100 caracteres.")
                    return
                valor = texto
            elif campo == "meta":
                try:
                    valor = float(texto.replace(",", "."))
                    if valor <= 0:
                        raise ValueError
                except ValueError:
                    bot.send_message(message.chat.id, "❌ Meta inválida. Envie um número maior que zero.")
                    return
            elif campo == "recompensa":
                try:
                    valor = round(float(texto.replace(",", ".")), 2)
                    if valor < 0:
                        raise ValueError
                except ValueError:
                    bot.send_message(message.chat.id, "❌ Recompensa inválida.")
                    return
            else:
                valor = "" if texto.lower() in ("/pular", "nenhum", "-", "nao") else texto
                if valor and not valor.startswith(("http://", "https://")):
                    bot.send_message(message.chat.id, "❌ O link precisa começar com http:// ou https://")
                    return

            coluna = {"nome": "nome", "meta": "meta", "recompensa": "recompensa", "link": "link_desbloqueado"}[campo]
            cursor.execute(f"UPDATE missoes SET {coluna}=?, atualizada_em=? WHERE id=?", (valor, data_atual(), mid))
            conn.commit()
            ESTADOS.pop(uid, None)
            _painel_admin(bot, message.chat.id, f"✅ Missão <b>#{mid}</b> atualizada.")
            return

        if estado.get("acao") != "criar":
            return

        if etapa == "nome":
            if not texto or len(texto) > 100:
                bot.send_message(message.chat.id, "❌ Nome inválido. Use entre 1 e 100 caracteres.")
                return
            estado["nome"] = texto
            estado["etapa"] = "tipo"
            kb = types.InlineKeyboardMarkup()
            for chave, nome in TIPOS.items():
                kb.add(types.InlineKeyboardButton(nome, callback_data=f"mis_type:{chave}"))
            bot.send_message(message.chat.id, "📌 <b>ESCOLHA O TIPO</b>", parse_mode="HTML", reply_markup=kb)
            return

        if etapa == "meta":
            try:
                meta = float(texto.replace(",", "."))
                if meta <= 0:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "❌ Meta inválida. Envie um número maior que zero.")
                return
            estado["meta"] = meta
            estado["etapa"] = "recompensa"
            bot.send_message(message.chat.id, "💰 Envie a <b>recompensa</b> em R$.\n\nExemplo: <code>5.00</code>\nSe não houver recompensa, envie <code>0</code>.", parse_mode="HTML")
            return

        if etapa == "recompensa":
            try:
                recompensa = round(float(texto.replace(",", ".")), 2)
                if recompensa < 0:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "❌ Recompensa inválida.")
                return
            estado["recompensa"] = recompensa
            estado["etapa"] = "recorrencia"
            kb = types.InlineKeyboardMarkup()
            for chave, nome in RECORRENCIAS.items():
                kb.add(types.InlineKeyboardButton(nome, callback_data=f"mis_rec:{chave}"))
            bot.send_message(message.chat.id, "🔁 <b>COMO ESSA MISSÃO FUNCIONA?</b>", parse_mode="HTML", reply_markup=kb)
            return

        if etapa == "inicio":
            dt = _parse_data(texto)
            if not dt:
                bot.send_message(message.chat.id, "❌ Data inválida. Use <code>2026-09-05 00:00</code>.", parse_mode="HTML")
                return
            estado["inicio"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            estado["etapa"] = "fim"
            bot.send_message(message.chat.id, "📅 Agora envie a <b>data/hora de término</b> no mesmo formato.", parse_mode="HTML")
            return

        if etapa == "fim":
            dt = _parse_data(texto)
            inicio = _parse_data(estado.get("inicio"))
            if not dt or not inicio or dt <= inicio:
                bot.send_message(message.chat.id, "❌ Término inválido. Deve ser depois do início.")
                return
            estado["fim"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            _pedir_link(bot, message.chat.id, uid)
            return

        if etapa == "link":
            link = "" if texto.lower() in ("/pular", "nenhum", "-", "nao") else texto
            if link and not link.startswith(("http://", "https://")):
                bot.send_message(message.chat.id, "❌ Link inválido. Ele precisa começar com http:// ou https://")
                return
            estado["link"] = link

            cursor.execute("""
                INSERT INTO missoes
                (nome, tipo, meta, recompensa, link_desbloqueado, recorrencia, inicio, fim, ativa, criada_em, atualizada_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                estado["nome"], estado["tipo"], estado["meta"], estado["recompensa"],
                estado.get("link", ""), estado["recorrencia"],
                estado.get("inicio", ""), estado.get("fim", ""),
                data_atual(), data_atual()
            ))
            mid = cursor.lastrowid
            conn.commit()
            ESTADOS.pop(uid, None)

            _painel_admin(
                bot,
                message.chat.id,
                f"✅ <b>Missão #{mid} criada com sucesso!</b>\n\n"
                f"🏆 {_esc(estado['nome'])}\n"
                f"🎯 Meta: <b>{estado['meta']:g}</b>\n"
                f"💰 Recompensa: <b>{dinheiro(estado['recompensa'])}</b>\n"
                f"🔁 {_esc(RECORRENCIAS[estado['recorrencia']])}"
            )
            return
