from telebot import types

from database import conn, cursor
from utils import data_atual, dinheiro, adicionar_saldo, registrar_historico
from antifraude import usuario_banido

# =====================================================
# GAMIFICAÇÃO / RECOMPENSAS AVANÇADAS
# =====================================================

NIVEIS = [
    (1, 0, "🥉 Bronze"),
    (2, 5, "🥈 Prata"),
    (3, 15, "🥇 Ouro"),
    (4, 35, "💎 Diamante"),
    (5, 75, "👑 Elite"),
]

CONQUISTAS = {
    "primeira_indicacao": ("🏅 Primeira indicação", "Faça sua primeira indicação aprovada", 2),
    "dez_indicacoes": ("🏅 10 indicações", "Tenha 10 indicações aprovadas", 5),
    "cinquenta_indicacoes": ("🏅 50 indicações", "Tenha 50 indicações aprovadas", 10),
    "primeiro_saque": ("🏅 Primeiro saque", "Faça seu primeiro saque", 3),
    "cem_reais": ("🏅 R$ 100 ganhos", "Ganhe pelo menos R$ 100", 15),
    "sete_dias": ("🔥 7 dias", "Mantenha uma sequência de 7 dias", 10),
}

MISSOES = {
    "convide_3": ("Convide 3 pessoas", 3, 3, 2.0),
    "aprovadas_5": ("Tenha 5 indicações aprovadas", 5, 5, 3.0),
    "aprovadas_10": ("Tenha 10 indicações aprovadas", 10, 8, 5.0),
    "ganhe_50": ("Alcance R$ 50 em ganhos", 50, 10, 5.0),
}


def preparar_banco():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gamificacao (
        usuario_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        nivel INTEGER DEFAULT 1,
        streak INTEGER DEFAULT 0,
        ultimo_dia TEXT,
        confianca INTEGER DEFAULT 50,
        equipe_id INTEGER,
        equipe_codigo TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conquistas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        chave TEXT NOT NULL,
        data TEXT,
        UNIQUE(usuario_id, chave)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS equipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        codigo TEXT UNIQUE NOT NULL,
        lider_id INTEGER NOT NULL,
        data_criacao TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eventos_recompensa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        multiplicador REAL DEFAULT 1.0,
        bonus_fixo REAL DEFAULT 0,
        inicio TEXT,
        fim TEXT,
        ativo INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS missoes_concluidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        chave TEXT NOT NULL,
        data TEXT,
        UNIQUE(usuario_id, chave)
    )
    """)

    cursor.execute("SELECT id FROM usuarios")
    ids = cursor.fetchall()
    for (uid,) in ids:
        cursor.execute(
            "INSERT OR IGNORE INTO gamificacao (usuario_id) VALUES (?)",
            (uid,)
        )

    conn.commit()


def garantir_usuario(usuario_id):
    cursor.execute(
        "INSERT OR IGNORE INTO gamificacao (usuario_id) VALUES (?)",
        (usuario_id,)
    )
    conn.commit()


def nivel_por_xp(xp):
    nivel = 1
    nome = NIVEIS[0][2]
    for n, minimo, titulo in NIVEIS:
        if xp >= minimo:
            nivel = n
            nome = titulo
    return nivel, nome


def registrar_atividade(usuario_id):
    """Atualiza streak e concede pequeno XP por atividade diária."""
    garantir_usuario(usuario_id)
    hoje = __import__('datetime').datetime.now().date()
    hoje_texto = hoje.isoformat()

    cursor.execute(
        "SELECT xp, nivel, streak, ultimo_dia FROM gamificacao WHERE usuario_id=?",
        (usuario_id,)
    )
    row = cursor.fetchone()
    if not row:
        return

    xp, nivel_atual, streak, ultimo = row
    if ultimo == hoje_texto:
        return

    if ultimo:
        try:
            anterior = __import__('datetime').date.fromisoformat(ultimo)
            delta = (hoje - anterior).days
        except Exception:
            delta = 99
        streak = streak + 1 if delta == 1 else 1
    else:
        streak = 1

    xp += 1
    novo_nivel, _ = nivel_por_xp(xp)

    cursor.execute(
        "UPDATE gamificacao SET xp=?, nivel=?, streak=?, ultimo_dia=? WHERE usuario_id=?",
        (xp, novo_nivel, streak, hoje_texto, usuario_id)
    )
    conn.commit()
    verificar_conquistas(usuario_id)


def adicionar_xp(usuario_id, quantidade, motivo=""):
    """Adiciona XP de forma centralizada e atualiza o nível."""
    try:
        quantidade = int(quantidade)
    except Exception:
        quantidade = 0
    if quantidade <= 0:
        return xp_usuario(usuario_id)
    garantir_usuario(usuario_id)
    cursor.execute("SELECT xp FROM gamificacao WHERE usuario_id=?", (usuario_id,))
    atual = int(cursor.fetchone()[0] or 0)
    novo_xp = atual + quantidade
    novo_nivel, _ = nivel_por_xp(novo_xp)
    cursor.execute("UPDATE gamificacao SET xp=?, nivel=? WHERE usuario_id=?", (novo_xp, novo_nivel, usuario_id))
    conn.commit()
    return xp_usuario(usuario_id)


def xp_usuario(usuario_id):
    garantir_usuario(usuario_id)
    cursor.execute(
        "SELECT xp, nivel, streak, confianca FROM gamificacao WHERE usuario_id=?",
        (usuario_id,)
    )
    row = cursor.fetchone()
    return row or (0, 1, 0, 50)


def indicacoes_aprovadas(usuario_id):
    cursor.execute(
        "SELECT COUNT(*) FROM indicacoes WHERE indicador_id=? AND status='APROVADO'",
        (usuario_id,)
    )
    return cursor.fetchone()[0] or 0


def ganhos_totais(usuario_id):
    cursor.execute(
        "SELECT COALESCE(SUM(valor),0) FROM historico WHERE usuario_id=? AND valor>0",
        (usuario_id,)
    )
    return float(cursor.fetchone()[0] or 0)


def atualizar_progresso(usuario_id):
    garantir_usuario(usuario_id)
    aprovadas = indicacoes_aprovadas(usuario_id)
    ganhos = ganhos_totais(usuario_id)

    # XP por marcos
    xp_extra = 0
    if aprovadas >= 1:
        xp_extra += 2
    if aprovadas >= 10:
        xp_extra += 3
    if aprovadas >= 50:
        xp_extra += 5

    if xp_extra:
        cursor.execute("SELECT xp FROM gamificacao WHERE usuario_id=?", (usuario_id,))
        atual = cursor.fetchone()[0]
        # Não repetir XP de marcos: as conquistas cuidam da parte de premiação.

    verificar_conquistas(usuario_id)


def premio_conquista(usuario_id, chave):
    dados = CONQUISTAS[chave]
    xp_premio = dados[2]
    cursor.execute("SELECT xp FROM gamificacao WHERE usuario_id=?", (usuario_id,))
    xp = cursor.fetchone()[0]
    novo_xp = xp + xp_premio
    novo_nivel, _ = nivel_por_xp(novo_xp)
    cursor.execute(
        "UPDATE gamificacao SET xp=?, nivel=? WHERE usuario_id=?",
        (novo_xp, novo_nivel, usuario_id)
    )
    conn.commit()


def verificar_conquistas(usuario_id):
    garantir_usuario(usuario_id)
    aprovadas = indicacoes_aprovadas(usuario_id)
    ganhos = ganhos_totais(usuario_id)
    _, _, streak, _ = xp_usuario(usuario_id)

    condicoes = {
        "primeira_indicacao": aprovadas >= 1,
        "dez_indicacoes": aprovadas >= 10,
        "cinquenta_indicacoes": aprovadas >= 50,
        "cem_reais": ganhos >= 100,
        "sete_dias": streak >= 7,
    }

    cursor.execute(
        "SELECT COUNT(*) FROM saques WHERE usuario_id=? AND status IN ('PAGO','APROVADO')",
        (usuario_id,)
    )
    condicoes["primeiro_saque"] = (cursor.fetchone()[0] or 0) >= 1

    for chave, ok in condicoes.items():
        if not ok:
            continue
        cursor.execute(
            "SELECT 1 FROM conquistas WHERE usuario_id=? AND chave=?",
            (usuario_id, chave)
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            "INSERT INTO conquistas (usuario_id, chave, data) VALUES (?, ?, ?)",
            (usuario_id, chave, data_atual())
        )
        premio_conquista(usuario_id, chave)
        try:
            # Import local para evitar ciclo de imports.
            from utils import criar_notificacao
            criar_notificacao(
                usuario_id,
                "CONQUISTA",
                f"Você desbloqueou: {CONQUISTAS[chave][0]}"
            )
        except Exception:
            pass

    conn.commit()


def confianca_usuario(usuario_id):
    garantir_usuario(usuario_id)
    cursor.execute("SELECT confianca FROM gamificacao WHERE usuario_id=?", (usuario_id,))
    return int(cursor.fetchone()[0] or 50)


def recalcular_confianca(usuario_id):
    aprovadas = indicacoes_aprovadas(usuario_id)
    cursor.execute("SELECT COUNT(*) FROM indicacoes WHERE indicador_id=? AND status='REJEITADO'", (usuario_id,))
    rejeitadas = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM fraudes WHERE usuario_id=?", (usuario_id,))
    fraudes = cursor.fetchone()[0] or 0

    score = 50 + min(aprovadas * 2, 40) - min(rejeitadas * 4, 25) - min(fraudes * 15, 50)
    score = max(0, min(100, score))
    garantir_usuario(usuario_id)
    cursor.execute("UPDATE gamificacao SET confianca=? WHERE usuario_id=?", (score, usuario_id))
    conn.commit()
    return score


def equipe_usuario(usuario_id):
    garantir_usuario(usuario_id)
    cursor.execute("SELECT equipe_id, equipe_codigo FROM gamificacao WHERE usuario_id=?", (usuario_id,))
    return cursor.fetchone()


def criar_equipe(usuario_id, nome):
    garantir_usuario(usuario_id)
    if equipe_usuario(usuario_id)[0]:
        return False, "Você já pertence a uma equipe."
    codigo = f"TEAM-{usuario_id % 100000:05d}"
    cursor.execute("SELECT 1 FROM equipes WHERE codigo=?", (codigo,))
    if cursor.fetchone():
        codigo = f"TEAM-{usuario_id}-{__import__('time').time_ns() % 10000}"
    cursor.execute(
        "INSERT INTO equipes (nome, codigo, lider_id, data_criacao) VALUES (?, ?, ?, ?)",
        (nome[:40], codigo, usuario_id, data_atual())
    )
    eid = cursor.lastrowid
    cursor.execute(
        "UPDATE gamificacao SET equipe_id=?, equipe_codigo=? WHERE usuario_id=?",
        (eid, codigo, usuario_id)
    )
    conn.commit()
    return True, codigo


def entrar_equipe(usuario_id, codigo):
    garantir_usuario(usuario_id)
    atual = equipe_usuario(usuario_id)
    if atual and atual[0]:
        return False, "Você já pertence a uma equipe."
    cursor.execute("SELECT id, nome FROM equipes WHERE codigo=?", (codigo.strip().upper(),))
    equipe = cursor.fetchone()
    if not equipe:
        return False, "Código de equipe não encontrado."
    cursor.execute(
        "UPDATE gamificacao SET equipe_id=?, equipe_codigo=? WHERE usuario_id=?",
        (equipe[0], codigo.strip().upper(), usuario_id)
    )
    conn.commit()
    return True, equipe[1]


def info_equipe(usuario_id):
    equipe = equipe_usuario(usuario_id)
    if not equipe or not equipe[0]:
        return None
    cursor.execute("SELECT id, nome, codigo, lider_id FROM equipes WHERE id=?", (equipe[0],))
    dados = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM gamificacao WHERE equipe_id=?", (equipe[0],))
    membros = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*)
        FROM indicacoes i
        JOIN gamificacao g ON g.usuario_id=i.indicador_id
        WHERE g.equipe_id=? AND i.status='APROVADO'
    """, (equipe[0],))
    indicacoes = cursor.fetchone()[0]
    return dados + (membros, indicacoes)


def missao_status(usuario_id):
    aprovadas = indicacoes_aprovadas(usuario_id)
    ganhos = ganhos_totais(usuario_id)
    valores = {
        "convide_3": aprovadas,
        "aprovadas_5": aprovadas,
        "aprovadas_10": aprovadas,
        "ganhe_50": ganhos,
    }
    resultado = []
    for chave, (nome, meta, xp, bonus) in MISSOES.items():
        progresso = min(float(valores[chave]), float(meta))
        cursor.execute("SELECT 1 FROM missoes_concluidas WHERE usuario_id=? AND chave=?", (usuario_id, chave))
        concluida = cursor.fetchone() is not None
        if progresso >= meta and not concluida:
            cursor.execute("INSERT OR IGNORE INTO missoes_concluidas (usuario_id, chave, data) VALUES (?, ?, ?)", (usuario_id, chave, data_atual()))
            cursor.execute("SELECT xp FROM gamificacao WHERE usuario_id=?", (usuario_id,))
            xp_atual = cursor.fetchone()[0]
            novo_xp = xp_atual + xp
            novo_nivel, _ = nivel_por_xp(novo_xp)
            cursor.execute("UPDATE gamificacao SET xp=?, nivel=? WHERE usuario_id=?", (novo_xp, novo_nivel, usuario_id))
            adicionar_saldo(usuario_id, bonus)
            registrar_historico(usuario_id, "MISSAO", f"Missão concluída: {nome}", bonus)
            try:
                from utils import criar_notificacao
                criar_notificacao(usuario_id, "MISSAO", f"🎯 Missão concluída: {nome}. Bônus: {dinheiro(bonus)}")
            except Exception:
                pass
            concluida = True
        resultado.append((chave, nome, progresso, meta, xp, bonus, concluida))
    conn.commit()
    return resultado


def ranking_geral(limite=20):
    cursor.execute("""
        SELECT g.usuario_id, u.nome, COUNT(i.id) AS total
        FROM gamificacao g
        JOIN usuarios u ON u.id=g.usuario_id
        LEFT JOIN indicacoes i ON i.indicador_id=g.usuario_id AND i.status='APROVADO'
        WHERE u.banido=0
        GROUP BY g.usuario_id, u.nome
        ORDER BY total DESC, g.xp DESC
        LIMIT ?
    """, (limite,))
    return cursor.fetchall()


def ranking_periodo(periodo="geral", limite=20):
    """Ranking de indicações aprovadas no período informado."""
    from datetime import datetime, timedelta
    agora = datetime.now()
    if periodo == "hoje":
        inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        inicio = (agora - timedelta(days=agora.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "mes":
        inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        inicio = None

    if inicio is None:
        return ranking_geral(limite)

    cursor.execute("""
        SELECT u.id, u.nome, COUNT(i.id) AS total
        FROM usuarios u
        JOIN indicacoes i ON i.indicador_id=u.id AND i.status='APROVADO'
        WHERE u.banido=0 AND i.data_aprovacao >= ?
        GROUP BY u.id, u.nome
        ORDER BY total DESC, u.id ASC
        LIMIT ?
    """, (inicio.strftime("%d/%m/%Y %H:%M:%S"), limite))
    return cursor.fetchall()


def evento_ativo():
    cursor.execute("""
        SELECT id, nome, multiplicador, bonus_fixo, inicio, fim
        FROM eventos_recompensa
        WHERE ativo=1
        ORDER BY id DESC LIMIT 1
    """)
    return cursor.fetchone()


def recompensa_dinamica(valor):
    evento = evento_ativo()
    if not evento:
        return float(valor), None
    novo = float(valor) * float(evento[2]) + float(evento[3])
    return round(novo, 2), evento[1]


def iniciar_evento(nome, multiplicador=1.0, bonus_fixo=0.0, inicio="", fim=""):
    cursor.execute("UPDATE eventos_recompensa SET ativo=0 WHERE ativo=1")
    cursor.execute(
        "INSERT INTO eventos_recompensa (nome, multiplicador, bonus_fixo, inicio, fim, ativo) VALUES (?, ?, ?, ?, ?, 1)",
        (nome, float(multiplicador), float(bonus_fixo), inicio or data_atual(), fim or "")
    )
    conn.commit()


def parar_evento():
    cursor.execute("UPDATE eventos_recompensa SET ativo=0 WHERE ativo=1")
    conn.commit()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gamificacao_usuario ON gamificacao(usuario_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_missoes_usuario_chave ON missoes_concluidas(usuario_id, chave)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conquistas_usuario ON conquistas(usuario_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_ativo ON eventos_recompensa(ativo)")
    conn.commit()


def registrar(bot):
    preparar_banco()
    estados_equipe = {}

    @bot.message_handler(func=lambda m: m.text == "🏅 Meu Nível")
    def meu_nivel(message):
        uid = message.from_user.id
        if usuario_banido(uid):
            bot.send_message(uid, "❌ Você está bloqueado.")
            return
        registrar_atividade(uid)
        xp, nivel, streak, confianca = xp_usuario(uid)
        _, nome_nivel = nivel_por_xp(xp)
        prox = next((minimo for n, minimo, _ in NIVEIS if n > nivel), None)
        faltam = max(0, prox - xp) if prox is not None else 0
        verificar_conquistas(uid)
        cursor.execute("SELECT COUNT(*) FROM conquistas WHERE usuario_id=?", (uid,))
        conquistas = cursor.fetchone()[0]
        bot.send_message(uid, f"""
🏅 <b>SEU PROGRESSO</b>

{nome_nivel}
⭐ XP: <b>{xp}</b>
🔥 Sequência: <b>{streak} dia(s)</b>
🛡️ Confiança: <b>{confianca}%</b>
🏆 Conquistas: <b>{conquistas}</b>

{('🎯 Faltam ' + str(faltam) + ' XP para o próximo nível.' if prox else '👑 Você alcançou o nível máximo!')}
""", parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🎯 Missões")
    def minhas_missoes(message):
        uid = message.from_user.id
        if usuario_banido(uid):
            bot.send_message(uid, "❌ Você está bloqueado.")
            return
        registrar_atividade(uid)
        linhas = ["🎯 <b>MISSÕES</b>\n"]
        for _, nome, progresso, meta, xp, bonus, concluida in missao_status(uid):
            marca = "✅" if concluida else "⏳"
            linhas.append(f"{marca} <b>{nome}</b>\n📈 {progresso:g}/{meta:g}\n⭐ +{xp} XP  |  💰 +{dinheiro(bonus)}\n")
        bot.send_message(uid, "\n".join(linhas), parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "👥 Equipe")
    def minha_equipe(message):
        uid = message.from_user.id
        info = info_equipe(uid)
        markup = types.InlineKeyboardMarkup()
        if info:
            bot.send_message(uid, f"""
🤝 <b>SUA EQUIPE</b>

👥 {info[1]}
🔑 Código: <code>{info[2]}</code>
👑 Líder: <code>{info[3]}</code>
👤 Membros: <b>{info[4]}</b>
🎁 Indicações aprovadas: <b>{info[5]}</b>
""", parse_mode="HTML")
            return
        markup.row(
            types.InlineKeyboardButton("➕ Criar equipe", callback_data="team_create"),
            types.InlineKeyboardButton("🔑 Entrar com código", callback_data="team_join")
        )
        bot.send_message(uid, "🤝 <b>EQUIPE</b>\n\nVocê ainda não pertence a uma equipe.", parse_mode="HTML", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data in ("team_create", "team_join"))
    def equipe_acao(call):
        uid = call.from_user.id
        if info_equipe(uid):
            bot.answer_callback_query(call.id, "Você já está em uma equipe.", show_alert=True)
            return
        estados_equipe[uid] = call.data
        bot.answer_callback_query(call.id)
        if call.data == "team_create":
            bot.send_message(uid, "✍️ Digite o nome da sua equipe:")
        else:
            bot.send_message(uid, "🔑 Digite o código da equipe que deseja entrar:")

    @bot.message_handler(func=lambda m: m.from_user.id in estados_equipe)
    def receber_equipe(message):
        uid = message.from_user.id
        acao = estados_equipe.pop(uid)
        valor = (message.text or "").strip()
        if acao == "team_create":
            ok, retorno = criar_equipe(uid, valor)
            texto = f"✅ Equipe criada!\n\n🔑 Código: <code>{retorno}</code>" if ok else f"❌ {retorno}"
        else:
            ok, retorno = entrar_equipe(uid, valor)
            texto = f"✅ Você entrou na equipe <b>{retorno}</b>!" if ok else f"❌ {retorno}"
        bot.send_message(uid, texto, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🏆 Ranking")
    def ranking_usuario(message):
        from utils import eh_admin
        if eh_admin(message.from_user.id):
            return
        uid = message.from_user.id
        ranking = ranking_geral(20)
        if not ranking:
            bot.send_message(uid, "🏆 Ainda não há dados suficientes para o ranking.")
            return
        posicao = next((i for i, row in enumerate(ranking, 1) if row[0] == uid), None)
        texto = "🏆 <b>RANKING DE INDICAÇÕES</b>\n\n"
        for pos, (rid, nome, total) in enumerate(ranking, 1):
            emoji = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else f"{pos}️⃣"
            texto += f"{emoji} {nome} — <b>{total}</b>\n"
        if posicao:
            texto += f"\n📍 Sua posição: <b>#{posicao}</b>"
        bot.send_message(uid, texto, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🛡️ Confiança")
    def minha_confianca(message):
        uid = message.from_user.id
        score = recalcular_confianca(uid)
        nivel = "🟢 Alta" if score >= 80 else "🟡 Média" if score >= 50 else "🔴 Baixa"
        bot.send_message(uid, f"🛡️ <b>ÍNDICE DE CONFIANÇA</b>\n\nScore: <b>{score}/100</b>\nStatus: {nivel}\n\nO score é calculado pelo histórico de indicações, saques e ocorrências antifraude.", parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🏅 Conquistas")
    def minhas_conquistas(message):
        uid = message.from_user.id
        verificar_conquistas(uid)
        cursor.execute("SELECT chave FROM conquistas WHERE usuario_id=? ORDER BY id", (uid,))
        feitas = {r[0] for r in cursor.fetchall()}
        texto = "🏅 <b>CONQUISTAS</b>\n\n"
        for chave, (nome, descricao, xp) in CONQUISTAS.items():
            texto += f"{'✅' if chave in feitas else '🔒'} <b>{nome}</b>\n{descricao} • +{xp} XP\n\n"
        bot.send_message(uid, texto, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🔥 Sequência")
    def minha_streak(message):
        uid = message.from_user.id
        registrar_atividade(uid)
        _, _, streak, _ = xp_usuario(uid)
        bot.send_message(uid, f"🔥 <b>SUA SEQUÊNCIA</b>\n\nDias consecutivos: <b>{streak}</b>\n\nContinue acessando o bot diariamente para manter sua sequência.", parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🎁 Evento")
    def evento_usuario(message):
        evento = evento_ativo()
        if not evento:
            bot.send_message(message.chat.id, "🎁 Não há evento ativo no momento.")
            return
        bot.send_message(message.chat.id, f"🔥 <b>EVENTO ATIVO</b>\n\n🎯 {evento[1]}\n💰 Multiplicador: <b>x{evento[2]}</b>\n🎁 Bônus fixo: <b>{dinheiro(evento[3])}</b>", parse_mode="HTML")

    # Comandos administrativos simples para eventos.
    @bot.message_handler(commands=["evento"])
    def admin_evento(message):
        from utils import eh_admin
        if not eh_admin(message.from_user.id):
            return
        partes = (message.text or "").split()
        if len(partes) < 2:
            bot.send_message(message.chat.id, "Uso: /evento NOME | opcional: /evento NOME MULTIPLICADOR BONUS")
            return
        nome = partes[1].replace("_", " ")
        mult = float(partes[2]) if len(partes) > 2 else 1.0
        bonus = float(partes[3]) if len(partes) > 3 else 0.0
        iniciar_evento(nome, mult, bonus)
        bot.send_message(message.chat.id, f"🔥 Evento <b>{nome}</b> ativado. Multiplicador x{mult} + {dinheiro(bonus)}.", parse_mode="HTML")

    @bot.message_handler(commands=["evento_off"])
    def admin_evento_off(message):
        from utils import eh_admin
        if not eh_admin(message.from_user.id):
            return
        parar_evento()
        bot.send_message(message.chat.id, "✅ Evento encerrado.")
