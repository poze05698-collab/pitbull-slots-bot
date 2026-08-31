import os, shutil, sqlite3, time, traceback
from telebot import types
from pathlib import Path
from database import conn, cursor
from utils import data_atual, eh_admin

DB_PATH = Path('database.db')
BACKUP_DIR = Path('backups')

_manutencao_cache = False
_manutencao_cache_ts = 0.0


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
    global _manutencao_cache, _manutencao_cache_ts
    agora = time.time()
    if agora - _manutencao_cache_ts < 1.0:
        return _manutencao_cache

    cursor.execute("SELECT valor FROM sistema_config WHERE chave='manutencao'")
    r = cursor.fetchone()
    _manutencao_cache = bool(r and r[0] == '1')
    _manutencao_cache_ts = agora
    return _manutencao_cache


def definir_manutencao(ativo):
    global _manutencao_cache, _manutencao_cache_ts
    valor = bool(ativo)
    cursor.execute(
        "INSERT OR REPLACE INTO sistema_config(chave,valor) VALUES('manutencao',?)",
        ('1' if valor else '0',)
    )
    conn.commit()
    _manutencao_cache = valor
    _manutencao_cache_ts = time.time()


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
