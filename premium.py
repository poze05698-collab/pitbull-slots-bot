"""Recursos premium e administrativos adicionais.
Tudo é persistido no SQLite existente e usa IF NOT EXISTS/INSERT OR IGNORE
para não apagar dados antigos.
"""
import random
import json
from datetime import datetime, date
from telebot import types
from database import conn, cursor
from utils import data_atual, dinheiro, eh_admin, saldo_usuario, adicionar_saldo, registrar_historico, registrar_movimentacao, criar_notificacao
from manutencao import esta_em_manutencao, definir_manutencao, preparar, ultimo_backup
from vip import beneficios_vip


def preparar_premium():
    # Índices para acelerar consultas sem alterar registros existentes.
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_indicacoes_status ON indicacoes(status)",
        "CREATE INDEX IF NOT EXISTS idx_indicacoes_indicado ON indicacoes(indicado_id)",
        "CREATE INDEX IF NOT EXISTS idx_indicacoes_indicador ON indicacoes(indicador_id)",
        "CREATE INDEX IF NOT EXISTS idx_saques_status ON saques(status)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)",
        "CREATE INDEX IF NOT EXISTS idx_notificacoes_usuario ON notificacoes(usuario_id, lida)",
        "CREATE INDEX IF NOT EXISTS idx_movimentacoes_usuario ON movimentacoes(usuario_id, id)",
    ]
    for sql in indices:
        cursor.execute(sql)

    cursor.execute("""CREATE TABLE IF NOT EXISTS parceiros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        descricao TEXT DEFAULT '',
        link TEXT NOT NULL,
        imagem TEXT DEFAULT '',
        ativo INTEGER DEFAULT 1,
        impressoes INTEGER DEFAULT 0,
        cliques INTEGER DEFAULT 0,
        data TEXT NOT NULL
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS raspadinhas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        premio_tipo TEXT NOT NULL,
        premio_valor REAL DEFAULT 0,
        data TEXT NOT NULL
    )""")
    # Migração segura: versões antigas limitavam 1 raspadinha por usuário/dia.
    # A nova regra permite 2/dia para VIP. Os registros antigos são preservados.
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='raspadinhas'")
    _schema = cursor.fetchone()
    if _schema and 'UNIQUE(usuario_id, data)' in (_schema[0] or ''):
        cursor.execute("""CREATE TABLE IF NOT EXISTS raspadinhas_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            premio_tipo TEXT NOT NULL,
            premio_valor REAL DEFAULT 0,
            data TEXT NOT NULL
        )""")
        cursor.execute("INSERT INTO raspadinhas_v2(id,usuario_id,premio_tipo,premio_valor,data) SELECT id,usuario_id,premio_tipo,premio_valor,data FROM raspadinhas")
        cursor.execute("DROP TABLE raspadinhas")
        cursor.execute("ALTER TABLE raspadinhas_v2 RENAME TO raspadinhas")
    cursor.execute("""CREATE TABLE IF NOT EXISTS sistema_config_v3 (
        chave TEXT PRIMARY KEY,
        valor TEXT NOT NULL
    )""")
    defaults = {
        'raspadinha_ativa': '1',
        'raspadinha_premio_min': '0.10',
        'raspadinha_premio_max': '1.00',
        'raspadinha_diaria': '1',
        'raspadinha_premios': json.dumps([
            {'tipo':'NADA','valor':0,'peso':35},
            {'tipo':'COINS','valor':10,'peso':25},
            {'tipo':'COINS','valor':25,'peso':15},
            {'tipo':'GEMAS','valor':1,'peso':12},
            {'tipo':'SALDO','valor':0.10,'peso':8},
            {'tipo':'SALDO','valor':0.25,'peso':4},
            {'tipo':'SALDO','valor':0.50,'peso':1}
        ], separators=(',',':')),
        'roleta_premios': json.dumps([
            {'tipo':'NADA','valor':0,'peso':35},
            {'tipo':'COINS','valor':10,'peso':30},
            {'tipo':'COINS','valor':25,'peso':18},
            {'tipo':'GEMAS','valor':1,'peso':12},
            {'tipo':'GEMAS','valor':2,'peso':4},
            {'tipo':'SALDO','valor':0.10,'peso':1}
        ], separators=(',',':')),
        'manutencao_mensagem': '🛠️ O bot está temporariamente em manutenção. Tente novamente em alguns minutos.',
        'velocidade_modo': 'normal',
    }
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO sistema_config_v3(chave,valor) VALUES(?,?)", (k, v))
    conn.commit()


def cfg(k, default=''):
    cursor.execute("SELECT valor FROM sistema_config_v3 WHERE chave=?", (k,))
    r = cursor.fetchone()
    return r[0] if r else default


def set_cfg(k, v):
    cursor.execute("INSERT OR REPLACE INTO sistema_config_v3(chave,valor) VALUES(?,?)", (k, str(v)))
    conn.commit()


def carregar_premios_config(chave, padrao):
    try:
        dados = json.loads(cfg(chave, ''))
        validos = []
        for item in dados:
            tipo = str(item.get('tipo','')).upper()
            valor = float(item.get('valor',0))
            peso = float(item.get('peso',0))
            if tipo not in ('NADA','COINS','GEMAS','SALDO') or valor < 0 or peso <= 0:
                continue
            if tipo in ('COINS','GEMAS'):
                valor = int(valor)
            validos.append((tipo, valor, peso))
        if validos:
            return validos
    except Exception:
        pass
    return padrao


def sortear_premio(chave, padrao):
    premios = carregar_premios_config(chave, padrao)
    tipos = [(x[0], x[1]) for x in premios]
    pesos = [x[2] for x in premios]
    return random.choices(tipos, weights=pesos, k=1)[0]


def formatar_premios(premios):
    linhas=[]
    for tipo,valor,peso in premios:
        nome = {'NADA':'Nada','COINS':'Coins','GEMAS':'Gemas','SALDO':'Saldo'}[tipo]
        valor_txt = '-' if tipo == 'NADA' else (dinheiro(valor) if tipo == 'SALDO' else str(int(valor)))
        linhas.append(f'{nome}: {valor_txt} | peso {peso:g}')
    return '\n'.join(linhas)


def menu_premium_admin():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('🤝 Parceiros', callback_data='v3_parceiros'))
    kb.row(types.InlineKeyboardButton('🎰 Roleta', callback_data='v3_roleta'), types.InlineKeyboardButton('🪙 Raspadinha', callback_data='v3_raspadinha'))
    kb.row(types.InlineKeyboardButton('🛠️ Manutenção', callback_data='v3_manutencao'))
    kb.row(types.InlineKeyboardButton('⚙️ Configurações', callback_data='v3_config'))
    return kb


def registrar(bot):
    preparar_premium()
    estados = {}

    @bot.message_handler(func=lambda m: m.text == '🎫 Raspadinha')
    def raspadinha(m):
        uid = m.from_user.id
        if esta_em_manutencao() and not eh_admin(uid):
            bot.send_message(uid, cfg('manutencao_mensagem'))
            return
        if cfg('raspadinha_ativa', '1') != '1':
            bot.send_message(uid, '🎫 A raspadinha está temporariamente desativada.')
            return
        hoje = date.today().isoformat()
        cursor.execute('SELECT COUNT(*) FROM raspadinhas WHERE usuario_id=? AND data=?', (uid, hoje))
        usados = cursor.fetchone()[0]
        limite = beneficios_vip(uid)['raspadinha']
        if usados >= limite:
            bot.send_message(uid, f'🎫 Você já usou suas {limite} raspadinha(s) de hoje. Volte amanhã!')
            return
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton('🪙 RASPAR AGORA', callback_data='v3_raspar'))
        bot.send_message(uid, f'🎫 <b>RASPADINHA</b>\n\nVocê ainda tem <b>{limite-usados}</b> cartela(s) hoje.\n\nBoa sorte! 🍀', parse_mode='HTML', reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_raspar')
    def raspar(c):
        uid = c.from_user.id
        hoje = date.today().isoformat()
        limite = beneficios_vip(uid)['raspadinha']
        cursor.execute('SELECT COUNT(*) FROM raspadinhas WHERE usuario_id=? AND data=?', (uid, hoje))
        usados = cursor.fetchone()[0]
        if usados >= limite:
            bot.answer_callback_query(c.id, 'Você já usou todas as raspadinhas de hoje.', show_alert=True)
            return
        tipo, premio = sortear_premio(
            'raspadinha_premios',
            [('NADA',0,35),('COINS',10,25),('COINS',25,15),('GEMAS',1,12),('SALDO',0.10,8),('SALDO',0.25,4),('SALDO',0.50,1)]
        )
        cursor.execute('INSERT INTO raspadinhas(usuario_id,premio_tipo,premio_valor,data) VALUES(?,?,?,?)', (uid, tipo, premio, hoje))
        if tipo == 'SALDO':
            adicionar_saldo(uid, premio)
            registrar_historico(uid, 'RASPADINHA', 'Prêmio da raspadinha diária', premio)
            registrar_movimentacao(uid, 'RASPADINHA', premio, 'Prêmio da raspadinha diária')
            msg = f'💰 +{dinheiro(premio)}'
        elif tipo == 'COINS':
            from avancado import add_coins
            add_coins(uid, int(premio))
            msg = f'🪙 +{int(premio)} Coins'
        elif tipo == 'GEMAS':
            from avancado import add_gemas
            add_gemas(uid, int(premio))
            msg = f'💎 +{int(premio)} Gemas'
        else:
            msg = '😢 Não ganhou prêmio desta vez.'
        conn.commit()
        restantes = limite - usados - 1
        bot.answer_callback_query(c.id, 'Cartela raspada!')
        bot.edit_message_text(f'🎉 <b>RESULTADO DA RASPADINHA</b>\n\n{msg}\n\n🎫 Cartelas restantes hoje: <b>{restantes}</b>', c.message.chat.id, c.message.message_id, parse_mode='HTML')

    @bot.message_handler(func=lambda m: m.text == '🤝 Parceiros')
    def parceiros_user(m):
        cursor.execute('SELECT id,nome,descricao,link FROM parceiros WHERE ativo=1 ORDER BY id DESC LIMIT 10')
        rows = cursor.fetchall()
        if not rows:
            bot.send_message(m.chat.id, '🤝 No momento não há parceiros ativos.')
            return
        kb = types.InlineKeyboardMarkup()
        texto = ['🤝 <b>PARCEIROS</b>\n', 'Confira ofertas e projetos de parceiros oficiais do bot:\n']
        for pid, nome, desc, link in rows:
            cursor.execute('UPDATE parceiros SET impressoes=impressoes+1 WHERE id=?', (pid,))
            texto.append(f'• <b>{nome}</b> — {desc or "Confira a parceria"}')
            kb.add(types.InlineKeyboardButton(f'🔗 {nome}', url=link))
        conn.commit()
        bot.send_message(m.chat.id, '\n'.join(texto), parse_mode='HTML', reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith('v3_parceiro_click:'))
    def parceiro_click(c):
        try:
            pid = int(c.data.split(':')[1])
            cursor.execute('UPDATE parceiros SET cliques=cliques+1 WHERE id=?', (pid,))
            conn.commit()
        except Exception:
            pass

    @bot.message_handler(func=lambda m: m.text == '⚙️ Configurações Avançadas')
    def config_adv(m):
        if not eh_admin(m.from_user.id): return
        bot.send_message(m.chat.id, '⚙️ <b>CONFIGURAÇÕES AVANÇADAS</b>', parse_mode='HTML', reply_markup=menu_premium_admin())

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_manutencao')
    def painel_manut(c):
        if not eh_admin(c.from_user.id): return
        status = '🟢 ONLINE' if not esta_em_manutencao() else '🔴 MANUTENÇÃO'
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton('🔴 Ativar', callback_data='v3_maint_on'), types.InlineKeyboardButton('🟢 Desativar', callback_data='v3_maint_off'))
        bot.edit_message_text(f'🛠️ <b>MANUTENÇÃO</b>\n\nStatus: {status}\n\nDurante manutenção, usuários recebem uma mensagem simples e o banco permanece intacto.', c.message.chat.id, c.message.message_id, parse_mode='HTML', reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data in ('v3_maint_on','v3_maint_off'))
    def altera_manut(c):
        if not eh_admin(c.from_user.id): return
        definir_manutencao(c.data == 'v3_maint_on')
        bot.answer_callback_query(c.id, 'Manutenção atualizada.')
        status = '🔴 ATIVA' if c.data == 'v3_maint_on' else '🟢 DESATIVADA'
        bot.edit_message_text(f'🛠️ <b>MANUTENÇÃO</b>\n\nStatus: {status}', c.message.chat.id, c.message.message_id, parse_mode='HTML')

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_roleta')
    def painel_roleta(c):
        if not eh_admin(c.from_user.id): return
        premios = carregar_premios_config('roleta_premios', [('NADA',0,35),('COINS',10,30),('COINS',25,18),('GEMAS',1,12),('GEMAS',2,4),('SALDO',0.10,1)])
        kb=types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton('💰 Alterar prêmios', callback_data='v3_roleta_edit'))
        bot.edit_message_text(
            '🎰 <b>PRÊMIOS DA ROLETA</b>\\n\\n' + formatar_premios(premios) +
            '\\n\\n💡 Peso maior = maior chance.\\nO saldo em reais está propositalmente com pesos baixos.',
            c.message.chat.id, c.message.message_id, parse_mode='HTML', reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_roleta_edit')
    def roleta_edit(c):
        if not eh_admin(c.from_user.id): return
        estados[c.from_user.id]='roleta_valores'
        bot.answer_callback_query(c.id)
        bot.send_message(
            c.from_user.id,
            '🎰 <b>ALTERAR PRÊMIOS DA ROLETA</b>\\n\\n'
            'Envie cada prêmio no formato <code>TIPO:VALOR:PESO</code>, separado por ponto e vírgula.\\n\\n'
            'Exemplo:\\n'
            '<code>NADA:0:35;COINS:10:30;COINS:25:18;GEMAS:1:12;GEMAS:2:4;SALDO:0.10:1</code>\\n\\n'
            'TIPOS: NADA, COINS, GEMAS, SALDO\\n'
            'Quanto maior o PESO, maior a chance.',
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda m: estados.get(m.from_user.id) == 'roleta_valores')
    def roleta_edit_text(m):
        if not eh_admin(m.from_user.id): return
        estados.pop(m.from_user.id,None)
        try:
            itens=[]
            for bloco in (m.text or '').split(';'):
                tipo,valor,peso=[x.strip() for x in bloco.split(':')]
                tipo=tipo.upper(); valor=float(valor); peso=float(peso)
                if tipo not in ('NADA','COINS','GEMAS','SALDO') or valor < 0 or peso <= 0:
                    raise ValueError
                if tipo in ('COINS','GEMAS'): valor=int(valor)
                itens.append({'tipo':tipo,'valor':valor,'peso':peso})
            if not itens or len(itens)>15: raise ValueError
            set_cfg('roleta_premios', json.dumps(itens,separators=(',',':')))
            bot.send_message(m.chat.id,'✅ Prêmios da roleta atualizados pelo painel.')
        except Exception:
            bot.send_message(m.chat.id,'❌ Formato inválido. Use: TIPO:VALOR:PESO;TIPO:VALOR:PESO')

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_raspadinha')
    def painel_rasp(c):
        if not eh_admin(c.from_user.id): return
        status = '🟢 ATIVA' if cfg('raspadinha_ativa','1') == '1' else '🔴 DESATIVADA'
        kb=types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton('🔴 Desativar' if status=='🟢 ATIVA' else '🟢 Ativar', callback_data='v3_rasp_toggle'))
        kb.row(types.InlineKeyboardButton('💰 Alterar prêmios', callback_data='v3_rasp_edit'))
        premios = carregar_premios_config('raspadinha_premios', [('NADA',0,35),('COINS',10,25),('COINS',25,15),('GEMAS',1,12),('SALDO',0.10,8),('SALDO',0.25,4),('SALDO',0.50,1)])
        bot.edit_message_text('🎫 <b>RASPADINHA</b>\n\nStatus: ' + status + '\n\n' + formatar_premios(premios) + '\n\n💡 Peso maior = maior chance. Saldo real usa pesos baixos.', c.message.chat.id, c.message.message_id, parse_mode='HTML', reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_rasp_toggle')
    def rasp_toggle(c):
        if not eh_admin(c.from_user.id): return
        atual=cfg('raspadinha_ativa','1')=='1'
        set_cfg('raspadinha_ativa','0' if atual else '1')
        bot.answer_callback_query(c.id, 'Raspadinha atualizada.')
        raspadinha_admin_refresh(c)

    def raspadinha_admin_refresh(c):
        status='🟢 ATIVA' if cfg('raspadinha_ativa','1')=='1' else '🔴 DESATIVADA'
        kb=types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton('🔴 Desativar' if status=='🟢 ATIVA' else '🟢 Ativar', callback_data='v3_rasp_toggle'))
        kb.row(types.InlineKeyboardButton('💰 Alterar prêmios', callback_data='v3_rasp_edit'))
        premios = carregar_premios_config('raspadinha_premios', [('NADA',0,35),('COINS',10,25),('COINS',25,15),('GEMAS',1,12),('SALDO',0.10,8),('SALDO',0.25,4),('SALDO',0.50,1)])
        bot.edit_message_text('🎫 <b>RASPADINHA</b>\n\nStatus: ' + status + '\n\n' + formatar_premios(premios) + '\n\n💡 Peso maior = maior chance. Saldo real usa pesos baixos.', c.message.chat.id, c.message.message_id, parse_mode='HTML', reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_rasp_edit')
    def rasp_edit(c):
        if not eh_admin(c.from_user.id): return
        estados[c.from_user.id]='rasp_valores'
        bot.answer_callback_query(c.id)
        bot.send_message(
            c.from_user.id,
            '🎫 <b>ALTERAR PRÊMIOS DA RASPADINHA</b>\n\n'
            'Envie cada prêmio no formato <code>TIPO:VALOR:PESO</code>, separado por ponto e vírgula.\n\n'
            'Exemplo:\n'
            '<code>NADA:0:35;COINS:10:25;COINS:25:15;GEMAS:1:12;SALDO:0.10:8;SALDO:0.25:4;SALDO:0.50:1</code>\n\n'
            'TIPOS: NADA, COINS, GEMAS, SALDO\n'
            'Quanto maior o PESO, maior a chance.',
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda m: estados.get(m.from_user.id) == 'rasp_valores')
    def rasp_edit_text(m):
        if not eh_admin(m.from_user.id): return
        estados.pop(m.from_user.id,None)
        try:
            itens=[]
            for bloco in (m.text or '').split(';'):
                tipo,valor,peso=[x.strip() for x in bloco.split(':')]
                tipo=tipo.upper(); valor=float(valor); peso=float(peso)
                if tipo not in ('NADA','COINS','GEMAS','SALDO') or valor < 0 or peso <= 0:
                    raise ValueError
                if tipo in ('COINS','GEMAS'): valor=int(valor)
                itens.append({'tipo':tipo,'valor':valor,'peso':peso})
            if not itens or len(itens)>15: raise ValueError
            set_cfg('raspadinha_premios', json.dumps(itens,separators=(',',':')))
            bot.send_message(m.chat.id,'✅ Prêmios da raspadinha atualizados pelo painel.')
        except Exception:
            bot.send_message(m.chat.id,'❌ Formato inválido. Use: TIPO:VALOR:PESO;TIPO:VALOR:PESO')

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_config')
    def painel_config(c):
        if not eh_admin(c.from_user.id): return
        bot.edit_message_text('⚙️ <b>CONFIGURAÇÕES</b>\n\nUse o painel principal para as configurações já existentes.\n\nComandos adicionais:\n/raspadinha on|off\n/raspadinha_valores MIN MAX', c.message.chat.id, c.message.message_id, parse_mode='HTML')

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_parceiros')
    def painel_parceiros(c):
        if not eh_admin(c.from_user.id): return
        cursor.execute('SELECT id,nome,ativo,impressoes,cliques,link FROM parceiros ORDER BY id DESC LIMIT 20')
        rows = cursor.fetchall()
        texto = ['🤝 <b>PARCEIROS</b>\n']
        for pid,nome,ativo,imp,clq,link in rows:
            texto.append(f'#{pid} <b>{nome}</b> | {"🟢" if ativo else "🔴"} | 👁 {imp} | 🔗 {clq}\n{link}')
        texto.append('\n➕ Adicione pelo botão abaixo ou use /parceiro NOME | LINK | DESCRIÇÃO')
        kb=types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton('➕ Adicionar parceiro', callback_data='v3_parceiro_add'))
        bot.edit_message_text('\n'.join(texto), c.message.chat.id, c.message.message_id, parse_mode='HTML', reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == 'v3_parceiro_add')
    def parceiro_add_start(c):
        if not eh_admin(c.from_user.id): return
        estados[c.from_user.id] = 'parceiro'
        bot.answer_callback_query(c.id)
        bot.send_message(c.from_user.id, '🤝 <b>NOVO PARCEIRO</b>\n\nEnvie em uma única mensagem:\n<code>NOME | LINK | DESCRIÇÃO</code>', parse_mode='HTML')

    @bot.message_handler(func=lambda m: estados.get(m.from_user.id) == 'parceiro')
    def parceiro_add_text(m):
        if not eh_admin(m.from_user.id): return
        estados.pop(m.from_user.id, None)
        partes=[x.strip() for x in (m.text or '').split('|',2)]
        if len(partes)<2 or not partes[0] or not partes[1].startswith(('http://','https://')):
            bot.send_message(m.chat.id,'❌ Formato inválido. Use: NOME | LINK | DESCRIÇÃO')
            return
        desc=partes[2] if len(partes)>2 else ''
        cursor.execute('INSERT INTO parceiros(nome,descricao,link,data) VALUES(?,?,?,?)',(partes[0][:80],desc[:200],partes[1][:500],data_atual()))
        conn.commit()
        bot.send_message(m.chat.id,f'✅ Parceiro <b>{partes[0]}</b> cadastrado pelo painel.',parse_mode='HTML')

    @bot.message_handler(commands=['parceiro'])
    def parceiro_admin(m):
        if not eh_admin(m.from_user.id): return
        raw = (m.text or '').split(maxsplit=1)
        if len(raw) < 2 or '|' not in raw[1]:
            bot.send_message(m.chat.id, 'Uso: /parceiro NOME | LINK | DESCRIÇÃO')
            return
        partes = [x.strip() for x in raw[1].split('|',2)]
        if len(partes) < 2 or not partes[0] or not partes[1].startswith(('http://','https://')):
            bot.send_message(m.chat.id, '❌ Nome e link válido são obrigatórios.')
            return
        desc = partes[2] if len(partes)>2 else ''
        cursor.execute('INSERT INTO parceiros(nome,descricao,link,data) VALUES(?,?,?,?)',(partes[0][:80],desc[:200],partes[1][:500],data_atual()))
        conn.commit()
        bot.send_message(m.chat.id, f'✅ Parceiro <b>{partes[0]}</b> adicionado.', parse_mode='HTML')

    @bot.message_handler(commands=['parceiro_off'])
    def parceiro_off(m):
        if not eh_admin(m.from_user.id): return
        try: pid=int((m.text or '').split()[1])
        except Exception:
            bot.send_message(m.chat.id,'Uso: /parceiro_off ID'); return
        cursor.execute('UPDATE parceiros SET ativo=0 WHERE id=?',(pid,)); conn.commit(); bot.send_message(m.chat.id,'✅ Parceiro desativado.')

    @bot.message_handler(commands=['raspadinha'])
    def rasp_config(m):
        if not eh_admin(m.from_user.id): return
        p=(m.text or '').split()
        if len(p)!=2 or p[1].lower() not in ('on','off'):
            bot.send_message(m.chat.id, 'Uso: /raspadinha on ou /raspadinha off'); return
        set_cfg('raspadinha_ativa','1' if p[1].lower()=='on' else '0')
        bot.send_message(m.chat.id, '🎫 Raspadinha ativada.' if p[1].lower()=='on' else '🎫 Raspadinha desativada.')

    @bot.message_handler(commands=['raspadinha_valores'])
    def rasp_valores(m):
        if not eh_admin(m.from_user.id): return
        p=(m.text or '').split()
        try:
            a=float(p[1].replace(',','.')); b=float(p[2].replace(',','.'))
            if a<0 or b<a: raise ValueError
        except Exception:
            bot.send_message(m.chat.id,'Uso: /raspadinha_valores MIN MAX'); return
        set_cfg('raspadinha_premio_min',a); set_cfg('raspadinha_premio_max',b)
        bot.send_message(m.chat.id,f'✅ Faixa atualizada: {dinheiro(a)} até {dinheiro(b)}')
