import os, shutil, sqlite3, time, traceback
from telebot import types
from pathlib import Path
from database import conn, cursor
from utils import data_atual, eh_admin

DB_PATH = Path('database.db')
BACKUP_DIR = Path('backups')


def preparar():
    BACKUP_DIR.mkdir(exist_ok=True)
    if DB_PATH.exists():
        stamp = time.strftime('%Y%m%d_%H%M%S')
        destino = BACKUP_DIR / f'database_{stamp}.db'
        try:
            shutil.copy2(DB_PATH, destino)
            backups = sorted(BACKUP_DIR.glob('database_*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
            for antigo in backups[10:]:
                antigo.unlink(missing_ok=True)
        except Exception as e:
            print(f'ERRO AO CRIAR BACKUP: {e}')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sistema_erros (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, modulo TEXT, erro TEXT, usuario_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sistema_config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)''')
    cursor.execute("INSERT OR IGNORE INTO sistema_config(chave,valor) VALUES('manutencao','0')")
    cursor.execute("INSERT OR IGNORE INTO sistema_config(chave,valor) VALUES('ultima_migracao',?)", (data_atual(),))
    conn.commit()


def esta_em_manutencao():
    cursor.execute("SELECT valor FROM sistema_config WHERE chave='manutencao'")
    r=cursor.fetchone()
    return bool(r and r[0]=='1')


def definir_manutencao(ativo):
    cursor.execute("INSERT OR REPLACE INTO sistema_config(chave,valor) VALUES('manutencao',?)", ('1' if ativo else '0',))
    conn.commit()


def registrar_erro(modulo, erro, usuario_id=None):
    try:
        cursor.execute('INSERT INTO sistema_erros(data,modulo,erro,usuario_id) VALUES(?,?,?,?)', (data_atual(), modulo, str(erro)[:2000], usuario_id))
        conn.commit()
    except Exception:
        pass
    print(f'========== ERRO CONTROLADO [{modulo}] ==========')
    print(f'USUARIO_ID: {usuario_id}')
    print(f'ERRO: {erro}')
    traceback.print_exc()


def ultimo_backup():
    arquivos=sorted(BACKUP_DIR.glob('database_*.db'), key=lambda p:p.stat().st_mtime, reverse=True)
    return str(arquivos[0]) if arquivos else None


def registrar(bot):
    preparar()

    @bot.message_handler(func=lambda msg: msg.text == "🛠️ Manutenção" and eh_admin(msg.from_user.id))
    def manutencao_menu(message):
        status = "🟢 ATIVA" if esta_em_manutencao() else "🔴 DESATIVADA"
        bot.send_message(
            message.chat.id,
            f"🛠️ <b>MANUTENÇÃO</b>\n\nStatus: <b>{status}</b>\n\n"
            "Use os botões abaixo para controlar o modo.",
            parse_mode="HTML",
            reply_markup=__import__("telebot").types.InlineKeyboardMarkup()
        )
        kb = __import__("telebot").types.InlineKeyboardMarkup()
        kb.row(
            __import__("telebot").types.InlineKeyboardButton("🔴 Ativar", callback_data="manut_on"),
            __import__("telebot").types.InlineKeyboardButton("🟢 Desativar", callback_data="manut_off")
        )
        bot.send_message(
            message.chat.id,
            f"🛠️ <b>MANUTENÇÃO</b>\n\nStatus: <b>{status}</b>\n\nEscolha uma opção:",
            parse_mode="HTML",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda c: c.data in ("manut_on","manut_off") and eh_admin(c.from_user.id))
    def manutencao_callback(call):
        definir_manutencao(call.data == "manut_on")
        bot.answer_callback_query(call.id, "Modo de manutenção atualizado.")
        status = "🟢 ATIVA" if esta_em_manutencao() else "🔴 DESATIVADA"
        bot.send_message(call.message.chat.id, f"🛠️ Manutenção: <b>{status}</b>", parse_mode="HTML")

    # Este handler é registrado antes dos módulos de usuário e bloqueia
    # mensagens/callbacks de usuários comuns quando a manutenção está ativa.
    @bot.message_handler(func=lambda msg: esta_em_manutencao() and not eh_admin(msg.from_user.id))
    def bloquear_manutencao(message):
        bot.send_message(
            message.chat.id,
            "🛠️ <b>BOT EM MANUTENÇÃO</b>\n\n"
            "Estamos realizando uma atualização.\n"
            "Tente novamente em alguns minutos.",
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda c: esta_em_manutencao() and not eh_admin(c.from_user.id))
    def bloquear_callback_manutencao(call):
        bot.answer_callback_query(
            call.id,
            "🛠️ O bot está em manutenção. Tente novamente em alguns minutos.",
            show_alert=True
        )

    @bot.message_handler(commands=['backup'])
    def backup_cmd(message):
        if not eh_admin(message.from_user.id): return
        preparar()
        bot.send_message(message.chat.id, f'💾 <b>BACKUP REALIZADO</b>\n\nÚltimo backup: <code>{os.path.basename(ultimo_backup() or "não encontrado")}</code>', parse_mode='HTML')

    @bot.message_handler(commands=['manutencao'])
    def manutencao_cmd(message):
        if not eh_admin(message.from_user.id): return
        partes=(message.text or '').split()
        if len(partes)<2:
            status='ATIVA' if esta_em_manutencao() else 'DESATIVADA'
            bot.send_message(message.chat.id, f'🛠️ <b>MANUTENÇÃO: {status}</b>\n\nUse /manutencao on ou /manutencao off', parse_mode='HTML'); return
        ativo=partes[1].lower() in ('on','1','sim','ativar')
        definir_manutencao(ativo)
        bot.send_message(message.chat.id, '🛠️ Modo manutenção ATIVADO.' if ativo else '✅ Modo manutenção DESATIVADO.')

    @bot.message_handler(commands=['erros'])
    def erros_cmd(message):
        if not eh_admin(message.from_user.id): return
        cursor.execute('SELECT id,data,modulo,erro,usuario_id FROM sistema_erros ORDER BY id DESC LIMIT 10')
        rows=cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id,'✅ Nenhum erro registrado.')
            return
        linhas=['🚨 <b>ÚLTIMOS ERROS</b>']
        for rid,dt,mod,err,uid in rows:
            linhas.append(f'\n#{rid} | {dt}\n<b>{mod}</b> | usuário: {uid or "-"}\n<code>{err[:700]}</code>')
        bot.send_message(message.chat.id,'\n'.join(linhas),parse_mode='HTML')
