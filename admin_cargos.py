from telebot import types
from config import ADMIN_ID
from database import cursor, conn
from utils import eh_admin, cargo_admin, nome_cargo_admin, CARGOS_ADMIN, data_atual

ESTADOS = {}

def _somente_master(uid):
    return int(uid) == int(ADMIN_ID)

def menu_admin_por_cargo(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True, row_width=2)
    cargo = cargo_admin(user_id)
    perms = CARGOS_ADMIN.get(cargo, {}).get("permissoes", set()) if cargo != "master" else set(CARGOS_ADMIN["gerente"]["permissoes"]) | {"admin_cargos"}
    itens = [
        ("📊 Dashboard","dashboard"),("🎁 Indicações","indicacoes"),("💸 Saques","saques"),("💰 Adicionar Saldo","saldo"),
        ("👥 Usuários","usuarios"),("🏆 Ranking","ranking"),("📢 Anunciar","anuncio"),("📊 Estatísticas","dashboard"),
        ("🧠 Gamificação","gamificacao"),("🔥 Evento","evento"),("💎 Configurar VIP","vip"),("🛠️ Manutenção","manutencao"),
        ("🎫 Tickets","tickets"),("🎟️ Códigos","codigos"),("🤝 Parceiros","parceiros"),("🚫 Banimentos","banimentos"),("⚙️ Configurações","configuracoes")
    ]
    for label, perm in itens:
        if perm in perms:
            kb.add(types.KeyboardButton(label))
    if cargo == "master":
        kb.add(types.KeyboardButton("👑 Administradores"))
    kb.add(types.KeyboardButton("⬅️ Menu"))
    return kb

def registrar(bot):
    @bot.message_handler(func=lambda m: m.text == "👑 Administradores" and _somente_master(m.from_user.id))
    def painel_admins(message):
        cursor.execute("SELECT id,nome,username,cargo,ativo,data_cadastro FROM administradores ORDER BY ativo DESC, id")
        rows=cursor.fetchall()
        texto=["👑 <b>GERENCIAMENTO DE ADMINISTRADORES</b>", "", f"👑 Master: <code>{ADMIN_ID}</code>", ""]
        if rows:
            for uid,nome,username,cargo,ativo,data in rows:
                status="🟢 Ativo" if ativo else "🔴 Inativo"
                texto.append(f"{nome_cargo_admin(cargo)} — <code>{uid}</code> — {status}")
        else:
            texto.append("Nenhum administrador adicional cadastrado.")
        kb=types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("➕ Cadastrar Admin", callback_data="adm_add"))
        if rows:
            kb.row(types.InlineKeyboardButton("🔄 Atualizar Cargo", callback_data="adm_role"), types.InlineKeyboardButton("🚫 Ativar/Desativar", callback_data="adm_toggle"))
        bot.send_message(message.chat.id,"\n".join(texto),parse_mode="HTML",reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "adm_add")
    def adm_add(call):
        if not _somente_master(call.from_user.id): return bot.answer_callback_query(call.id,"Somente o Master.",show_alert=True)
        ESTADOS[call.from_user.id]={"acao":"add"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,"➕ <b>NOVO ADMINISTRADOR</b>\n\nEnvie no formato:\n<code>ID CARGO</code>\n\nCargos disponíveis:\n" + "\n".join(f"• <code>{k}</code> — {v['nome']}" for k,v in CARGOS_ADMIN.items()),parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "adm_role")
    def adm_role(call):
        if not _somente_master(call.from_user.id): return bot.answer_callback_query(call.id,"Somente o Master.",show_alert=True)
        ESTADOS[call.from_user.id]={"acao":"role"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,"✏️ Envie: <code>ID CARGO</code>\nExemplo: <code>123456789 financeiro</code>",parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "adm_toggle")
    def adm_toggle(call):
        if not _somente_master(call.from_user.id): return bot.answer_callback_query(call.id,"Somente o Master.",show_alert=True)
        ESTADOS[call.from_user.id]={"acao":"toggle"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,"🚦 Envie o ID do administrador para ativar/desativar: <code>123456789</code>",parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.from_user.id in ESTADOS and _somente_master(m.from_user.id))
    def adm_estado(message):
        estado=ESTADOS.get(message.from_user.id)
        partes=(message.text or "").strip().split()
        try:
            uid=int(partes[0])
        except Exception:
            bot.send_message(message.chat.id,"❌ ID inválido."); return
        if uid == int(ADMIN_ID):
            bot.send_message(message.chat.id,"❌ O Master não pode ser alterado."); ESTADOS.pop(message.from_user.id,None); return
        acao=estado["acao"]
        if acao in ("add","role"):
            if len(partes)<2 or partes[1].lower() not in CARGOS_ADMIN:
                bot.send_message(message.chat.id,"❌ Cargo inválido. Use: gerente, financeiro, suporte ou moderador."); return
            cargo=partes[1].lower()
            cursor.execute("SELECT nome,username FROM usuarios WHERE id=?",(uid,)); user=cursor.fetchone()
            nome=(user[0] if user else None) or f"Admin {uid}"; username=user[1] if user else None
            cursor.execute("""INSERT INTO administradores(id,nome,username,cargo,ativo,adicionado_por,data_cadastro,ultimo_acesso) VALUES(?,?,?,?,1,?,?,?) ON CONFLICT(id) DO UPDATE SET cargo=excluded.cargo,ativo=1,nome=excluded.nome,username=excluded.username""",(uid,nome,username,cargo,message.from_user.id,data_atual(),data_atual()))
            conn.commit(); ESTADOS.pop(message.from_user.id,None)
            bot.send_message(message.chat.id,f"✅ Administrador <code>{uid}</code> definido como <b>{nome_cargo_admin(cargo)}</b>.",parse_mode="HTML")
        elif acao=="toggle":
            cursor.execute("SELECT ativo FROM administradores WHERE id=?",(uid,)); row=cursor.fetchone()
            if not row: bot.send_message(message.chat.id,"❌ Administrador não encontrado."); return
            novo=0 if row[0] else 1
            cursor.execute("UPDATE administradores SET ativo=? WHERE id=?",(novo,uid)); conn.commit(); ESTADOS.pop(message.from_user.id,None)
            bot.send_message(message.chat.id,"✅ Administrador " + ("ativado." if novo else "desativado."))
