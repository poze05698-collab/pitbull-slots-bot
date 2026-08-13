import random, time
from telebot import types
from database import conn, cursor
from utils import data_atual, dinheiro, adicionar_saldo, registrar_historico, eh_admin
from antifraude import usuario_banido
from vip import enviar_area_vip, beneficios_vip

VIP = [(0,'🥉 Normal'),(50,'🥈 VIP Bronze'),(150,'🥇 VIP Prata'),(350,'💎 VIP Ouro'),(750,'👑 VIP Elite')]
LOJA = {
 '1':('🎟️ Cupom VIP',50,0,'CUPOM'),
 '2':('🎁 Bônus R$ 2',100,2,'SALDO'),
 '3':('💎 Gema rara',150,0,'GEMA'),
 '4':('⚡ Bônus R$ 5',250,5,'SALDO'),
}


def preparar_banco():
    cursor.execute('''CREATE TABLE IF NOT EXISTS economia_avancada (usuario_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0, gemas INTEGER DEFAULT 0, vip_xp INTEGER DEFAULT 0, vip_nivel INTEGER DEFAULT 1, giros_dia INTEGER DEFAULT 0, ultimo_giro TEXT, caixas INTEGER DEFAULT 0, FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, item TEXT, quantidade INTEGER DEFAULT 1, data TEXT, UNIQUE(usuario_id,item))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS campanhas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, descricao TEXT, recompensa REAL DEFAULT 0, xp INTEGER DEFAULT 0, inicio TEXT, fim TEXT, ativo INTEGER DEFAULT 1)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS clãs (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, codigo TEXT UNIQUE, lider_id INTEGER, nivel INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, data TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS clan_membros (clan_id INTEGER, usuario_id INTEGER UNIQUE, data TEXT, PRIMARY KEY(clan_id,usuario_id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS relatorios (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, data TEXT, conteudo TEXT)''')
    cursor.execute('SELECT id FROM usuarios')
    for (uid,) in cursor.fetchall(): cursor.execute('INSERT OR IGNORE INTO economia_avancada(usuario_id) VALUES(?)',(uid,))
    conn.commit()


def garantir(uid):
    cursor.execute('INSERT OR IGNORE INTO economia_avancada(usuario_id) VALUES(?)',(uid,)); conn.commit()


def coins(uid): garantir(uid); cursor.execute('SELECT coins FROM economia_avancada WHERE usuario_id=?',(uid,)); return int(cursor.fetchone()[0])
def gemas(uid): garantir(uid); cursor.execute('SELECT gemas FROM economia_avancada WHERE usuario_id=?',(uid,)); return int(cursor.fetchone()[0])
def add_coins(uid,n): garantir(uid); cursor.execute('UPDATE economia_avancada SET coins=coins+? WHERE usuario_id=?',(int(n),uid)); conn.commit()
def add_gemas(uid,n): garantir(uid); cursor.execute('UPDATE economia_avancada SET gemas=gemas+? WHERE usuario_id=?',(int(n),uid)); conn.commit()

def dar_vip_xp(uid, quantidade=1):
    garantir(uid)
    cursor.execute('UPDATE economia_avancada SET vip_xp=vip_xp+? WHERE usuario_id=?',(int(quantidade),uid))
    conn.commit()
    return vip(uid)


def vip(uid):
    garantir(uid); cursor.execute('SELECT vip_xp,vip_nivel FROM economia_avancada WHERE usuario_id=?',(uid,)); xp,n=cursor.fetchone()
    novo=1
    for i,req,_ in VIP:
        if xp>=req: novo=i
    if novo!=n: cursor.execute('UPDATE economia_avancada SET vip_nivel=? WHERE usuario_id=?',(novo,uid)); conn.commit()
    return xp,novo,VIP[novo-1][2]


def registrar(bot):
    preparar_banco()
    estados={}
    
    @bot.message_handler(func=lambda m:m.text=='💎 VIP' and not eh_admin(m.from_user.id))
    def vip_cmd(m):
        enviar_area_vip(bot, m.chat.id)

    @bot.message_handler(func=lambda m:m.text=='🪙 Moedas')
    def moedas_cmd(m):
        garantir(m.from_user.id)
        bot.send_message(m.chat.id,f'🪙 <b>CARTEIRA VIRTUAL</b>\n\n🪙 Coins: <b>{coins(m.from_user.id)}</b>\n💎 Gemas: <b>{gemas(m.from_user.id)}</b>')

    @bot.message_handler(func=lambda m:m.text=='🎰 Roleta')
    def roleta(m):
        uid=m.from_user.id; garantir(uid); hoje=time.strftime('%Y-%m-%d'); cursor.execute('SELECT giros_dia,ultimo_giro FROM economia_avancada WHERE usuario_id=?',(uid,)); giros,last=cursor.fetchone()
        if last!=hoje: giros=0
        limite=beneficios_vip(uid)['roleta']
        if giros>=limite: bot.send_message(uid,f'🎰 Você já usou seus {limite} giros de hoje. Volte amanhã!'); return
        markup=types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton('🎰 GIRAR',callback_data='av_girar'))
        bot.send_message(uid,f'🎰 <b>ROLETA DIÁRIA</b>\n\nVocê tem <b>{limite-giros}</b> giro(s) disponível(is) hoje.',parse_mode='HTML',reply_markup=markup)

    @bot.callback_query_handler(func=lambda c:c.data=='av_girar')
    def girar(c):
        uid=c.from_user.id; garantir(uid); hoje=time.strftime('%Y-%m-%d'); cursor.execute('SELECT giros_dia,ultimo_giro FROM economia_avancada WHERE usuario_id=?',(uid,)); g,last=cursor.fetchone()
        limite=beneficios_vip(uid)['roleta']
        if last==hoje and g>=limite: bot.answer_callback_query(c.id,'Você já usou todos os giros de hoje.',show_alert=True); return
        premios=[('coins',10),('coins',25),('coins',50),('gemas',1),('saldo',1),('nada',0)]
        if beneficios_vip(uid)['ativo']:
            premios += [('coins',50),('gemas',2),('saldo',2),('saldo',3)]
        tipo,valor=random.choice(premios)
        novo_giros=(g if last==hoje else 0)+1
        cursor.execute('UPDATE economia_avancada SET giros_dia=?,ultimo_giro=? WHERE usuario_id=?',(novo_giros,hoje,uid)); conn.commit()
        if tipo=='coins': add_coins(uid,valor); texto=f'🪙 +{valor} coins'
        elif tipo=='gemas': add_gemas(uid,valor); texto=f'💎 +{valor} gema'
        elif tipo=='saldo': adicionar_saldo(uid,valor); registrar_historico(uid,'ROLETA','Prêmio da roleta',valor); texto=f'💰 +{dinheiro(valor)}'
        else: texto='😢 Não ganhou prêmio desta vez.'
        bot.answer_callback_query(c.id,'🎉 Resultado!',show_alert=False); bot.send_message(uid,f'🎰 <b>RESULTADO</b>\n\n{texto}',parse_mode='HTML')

    @bot.message_handler(func=lambda m:m.text=='🎁 Caixa Surpresa')
    def caixa(m):
        uid=m.from_user.id; garantir(uid); cursor.execute('SELECT caixas FROM economia_avancada WHERE usuario_id=?',(uid,)); q=cursor.fetchone()[0]
        if q<=0: bot.send_message(uid,'🎁 Você não possui caixas surpresa. Complete missões e campanhas para receber.'); return
        markup=types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton('🎁 ABRIR CAIXA',callback_data='av_caixa'))
        bot.send_message(uid,f'🎁 Você possui <b>{q}</b> caixa(s).',parse_mode='HTML',reply_markup=markup)

    @bot.callback_query_handler(func=lambda c:c.data=='av_caixa')
    def abrir_caixa(c):
        uid=c.from_user.id; garantir(uid); cursor.execute('SELECT caixas FROM economia_avancada WHERE usuario_id=?',(uid,)); q=cursor.fetchone()[0]
        if q<=0: bot.answer_callback_query(c.id,'Sem caixas.',show_alert=True); return
        cursor.execute('UPDATE economia_avancada SET caixas=caixas-1 WHERE usuario_id=?',(uid,)); conn.commit()
        premio=random.choice([('coins',50),('coins',100),('gemas',2),('saldo',3)])
        t,v=premio
        if t=='coins': add_coins(uid,v); msg=f'🪙 +{v} coins'
        elif t=='gemas': add_gemas(uid,v); msg=f'💎 +{v} gemas'
        else: adicionar_saldo(uid,v); registrar_historico(uid,'CAIXA','Prêmio de caixa surpresa',v); msg=f'💰 +{dinheiro(v)}'
        bot.send_message(uid,f'🎁 <b>CAIXA ABERTA!</b>\n\nVocê ganhou:\n{msg}',parse_mode='HTML')

    @bot.message_handler(func=lambda m:m.text=='🏪 Loja')
    def loja(m):
        linhas=['🏪 <b>LOJA DE RECOMPENSAS</b>\n']
        markup=types.InlineKeyboardMarkup()
        for k,(nome,custo,valor,tipo) in LOJA.items():
            linhas.append(f'{k}. {nome} — 🪙 {custo} coins')
            markup.add(types.InlineKeyboardButton(f'🛒 Comprar {k}',callback_data=f'av_compra_{k}'))
        linhas.append(f'\n🪙 Seu saldo: <b>{coins(m.from_user.id)}</b>')
        bot.send_message(m.chat.id,'\n'.join(linhas),parse_mode='HTML',reply_markup=markup)

    @bot.callback_query_handler(func=lambda c:c.data.startswith('av_compra_'))
    def compra(c):
        uid=c.from_user.id; k=c.data.split('_')[-1]
        if k not in LOJA: return
        nome,custo,valor,tipo=LOJA[k]; saldo=coins(uid)
        if saldo<custo: bot.answer_callback_query(c.id,'Coins insuficientes.',show_alert=True); return
        add_coins(uid,-custo)
        if tipo=='SALDO': adicionar_saldo(uid,valor); registrar_historico(uid,'LOJA',f'Compra: {nome}',valor)
        elif tipo=='GEMA': add_gemas(uid,1)
        else:
            cursor.execute('INSERT INTO inventario(usuario_id,item,quantidade,data) VALUES(?,?,1,?) ON CONFLICT(usuario_id,item) DO UPDATE SET quantidade=quantidade+1',(uid,nome,data_atual())); conn.commit()
        bot.answer_callback_query(c.id,'Compra realizada!'); bot.send_message(uid,f'🛒 <b>Compra concluída!</b>\n\n{nome}',parse_mode='HTML')

    @bot.message_handler(func=lambda m:m.text=='⚔️ Clã')
    def clan(m):
        uid=m.from_user.id; cursor.execute('SELECT c.id,c.nome,c.codigo,c.lider_id,c.nivel,c.xp FROM clãs c JOIN clan_membros cm ON cm.clan_id=c.id WHERE cm.usuario_id=?',(uid,)); r=cursor.fetchone()
        if r: bot.send_message(uid,f'⚔️ <b>SEU CLÃ</b>\n\n{r[1]}\n🔑 {r[2]}\n🏅 Nível: {r[4]}\n⭐ XP: {r[5]}'); return
        markup=types.InlineKeyboardMarkup(); markup.row(types.InlineKeyboardButton('➕ Criar clã',callback_data='clan_create'),types.InlineKeyboardButton('🔑 Entrar',callback_data='clan_join'))
        bot.send_message(uid,'⚔️ <b>CLÃ</b>\n\nVocê ainda não pertence a um clã.',parse_mode='HTML',reply_markup=markup)

    @bot.callback_query_handler(func=lambda c:c.data in ('clan_create','clan_join'))
    def clan_action(c): estados[c.from_user.id]=c.data; bot.answer_callback_query(c.id); bot.send_message(c.from_user.id,'✍️ Digite o nome do clã:' if c.data=='clan_create' else '🔑 Digite o código do clã:')

    @bot.message_handler(func=lambda m:m.from_user.id in estados)
    def clan_text(m):
        uid=m.from_user.id; acao=estados.pop(uid); v=(m.text or '').strip()
        if acao=='clan_create':
            codigo=f'CLAN-{uid%100000:05d}'; cursor.execute('SELECT 1 FROM clãs WHERE codigo=?',(codigo,));
            if cursor.fetchone(): codigo=f'CLAN-{uid}-{random.randint(1000,9999)}'
            cursor.execute('INSERT INTO clãs(nome,codigo,lider_id,data) VALUES(?,?,?,?)',(v[:40],codigo,uid,data_atual())); cid=cursor.lastrowid; cursor.execute('INSERT INTO clan_membros(clan_id,usuario_id,data) VALUES(?,?,?)',(cid,uid,data_atual())); conn.commit(); bot.send_message(uid,f'⚔️ Clã criado!\n\n🔑 Código: <code>{codigo}</code>',parse_mode='HTML')
        else:
            cursor.execute('SELECT id,nome FROM clãs WHERE codigo=?',(v.upper(),)); r=cursor.fetchone()
            if not r: bot.send_message(uid,'❌ Código não encontrado.'); return
            try: cursor.execute('INSERT INTO clan_membros(clan_id,usuario_id,data) VALUES(?,?,?)',(r[0],uid,data_atual())); conn.commit(); bot.send_message(uid,f'⚔️ Você entrou no clã <b>{r[1]}</b>!',parse_mode='HTML')
            except Exception: bot.send_message(uid,'❌ Você já pertence a um clã ou não foi possível entrar.')

    @bot.message_handler(commands=['campanha'])
    def campanha_admin(m):
        if not eh_admin(m.from_user.id): return
        partes=(m.text or '').split(maxsplit=3)
        if len(partes)<4: bot.send_message(m.chat.id,'Uso: /campanha NOME RECOMPENSA DESCRICAO'); return
        nome,rec,desc=partes[1],float(partes[2].replace(',','.')),partes[3]
        cursor.execute('INSERT INTO campanhas(nome,descricao,recompensa,inicio,ativo) VALUES(?,?,?,?,1)',(nome,desc,rec,data_atual())); conn.commit(); bot.send_message(m.chat.id,f'📢 Campanha <b>{nome}</b> criada.',parse_mode='HTML')


    @bot.message_handler(commands=['economia'])
    def economia_admin(m):
        if not eh_admin(m.from_user.id): return
        partes=(m.text or '').split()
        if len(partes) < 4 or partes[1] not in ('coins','gemas','caixas'):
            bot.send_message(m.chat.id,'Uso: /economia coins|gemas|caixas ID VALOR')
            return
        try: uid=int(partes[2]); valor=int(partes[3])
        except ValueError:
            bot.send_message(m.chat.id,'❌ ID ou valor inválido.'); return
        if valor <= 0: bot.send_message(m.chat.id,'❌ O valor deve ser maior que zero.'); return
        garantir(uid)
        if partes[1]=='coins': add_coins(uid,valor)
        elif partes[1]=='gemas': add_gemas(uid,valor)
        else:
            cursor.execute('UPDATE economia_avancada SET caixas=caixas+? WHERE usuario_id=?',(valor,uid)); conn.commit()
        bot.send_message(m.chat.id,'✅ Recompensa virtual adicionada.')

    @bot.message_handler(commands=['campanhas'])
    def campanhas_admin(m):
        if not eh_admin(m.from_user.id): return
        cursor.execute('SELECT id,nome,recompensa,inicio,fim,ativo FROM campanhas ORDER BY id DESC LIMIT 20')
        rows=cursor.fetchall()
        if not rows:
            bot.send_message(m.chat.id,'📭 Nenhuma campanha cadastrada.'); return
        linhas=['📢 <b>CAMPANHAS</b>']
        for r in rows:
            linhas.append(f'\n#{r[0]} <b>{r[1]}</b> | 💰 {dinheiro(r[2])} | {"🟢" if r[5] else "🔴"}')
        bot.send_message(m.chat.id,'\n'.join(linhas),parse_mode='HTML')

    @bot.message_handler(commands=['relatorio'])
    def relatorio(m):
        if not eh_admin(m.from_user.id): return
        cursor.execute('SELECT COUNT(*) FROM usuarios'); users=cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM indicacoes WHERE status='APROVADO'"); apps=cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(valor),0) FROM historico WHERE valor>0"); ganhos=cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM saques WHERE status='PENDENTE'"); saques=cursor.fetchone()[0]
        bot.send_message(m.chat.id,f'📊 <b>RELATÓRIO</b>\n\n👥 Usuários: {users}\n🎁 Indicações aprovadas: {apps}\n💰 Recompensas registradas: {dinheiro(ganhos)}\n💸 Saques pendentes: {saques}',parse_mode='HTML')
