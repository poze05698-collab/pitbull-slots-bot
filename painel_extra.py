from telebot import types
from database import cursor
from utils import eh_admin
from manutencao import esta_em_manutencao, definir_manutencao
from premium import cfg, set_cfg

def registrar(bot):
    @bot.message_handler(func=lambda m: m.text == '🛠️ Manutenção')
    def manut(m):
        if not eh_admin(m.from_user.id): return
        st='🔴 ATIVA' if esta_em_manutencao() else '🟢 DESATIVADA'
        kb=types.InlineKeyboardMarkup(); kb.row(types.InlineKeyboardButton('🔴 Ativar',callback_data='v3_maint_on'),types.InlineKeyboardButton('🟢 Desativar',callback_data='v3_maint_off'))
        bot.send_message(m.chat.id,f'🛠️ <b>MANUTENÇÃO</b>\n\nStatus: {st}\n\n💾 O banco não é apagado durante manutenção.',parse_mode='HTML',reply_markup=kb)
    @bot.message_handler(func=lambda m: m.text == '🤝 Parceiros' and eh_admin(m.from_user.id))
    def parceiros_admin(m):
        cursor.execute('SELECT id,nome,ativo,impressoes,cliques FROM parceiros ORDER BY id DESC LIMIT 20')
        rows=cursor.fetchall(); txt=['🤝 <b>PARCEIROS</b>\n']
        for pid,nome,ativo,imp,clq in rows: txt.append(f'#{pid} {nome} | {"🟢" if ativo else "🔴"} | 👁 {imp} | 🔗 {clq}')
        txt.append('\nAdicionar: /parceiro NOME | LINK | DESCRIÇÃO')
        bot.send_message(m.chat.id,'\n'.join(txt),parse_mode='HTML')
