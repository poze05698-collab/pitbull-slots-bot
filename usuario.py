from telebot import types
import os

from database import conn, cursor

from teclado import menu_principal

from utils import (
    data_atual,
    dinheiro,
    saldo_usuario,
    saldo_pendente,
    saque_pendente,
    buscar_pix,
    registrar_historico,
    notificacoes_usuario,
    marcar_notificacoes_lidas
)

from config import (
    VALOR_INDICACAO,
    VALOR_MINIMO_SAQUE
)

from antifraude import usuario_banido

from indicacoes import (
    gerar_link,
    salvar_link_convite,
    desativar_convites,
    indicacoes_usuario
)


from config import GRUPO_ID
from telebot.apihelper import ApiTelegramException

# ==========================================
# CADASTRAR USUÁRIO
# ==========================================

def cadastrar_usuario(message):

    user_id = message.from_user.id
    nome = message.from_user.first_name
    username = message.from_user.username

    cursor.execute(
        "SELECT id FROM usuarios WHERE id=?",
        (user_id,)
    )

    usuario = cursor.fetchone()

    if usuario is None:

        cursor.execute(
            """
            INSERT INTO usuarios
            (
                id,
                nome,
                username,
                saldo,
                saldo_pendente,
                saque_pendente,
                pix,
                banido,
                data_cadastro,
                ultimo_acesso
            )

            VALUES

            (?, ?, ?, 0, 0, 0, '', 0, ?, ?)

            """,

            (

                user_id,

                nome,

                username,

                data_atual(),

                data_atual()

            )

        )

        conn.commit()

        registrar_historico(

            user_id,

            "CADASTRO",

            "Usuário cadastrado"

        )

    else:

        cursor.execute(

            """
            UPDATE usuarios

            SET

            nome=?,

            username=?,

            ultimo_acesso=?

            WHERE id=?

            """,

            (

                nome,

                username,

                data_atual(),

                user_id

            )

        )

        conn.commit()

# ==========================================
# PERFIL
# ==========================================

def perfil_usuario(user_id):

    cursor.execute(
        """
        SELECT

        nome,

        username,

        pix,

        data_cadastro

        FROM usuarios

        WHERE id=?

        """,

        (user_id,)

    )

    return cursor.fetchone()

# ==========================================
# REGISTRAR
# ==========================================

def registrar(bot):

    # ==========================================
    # PERFIL
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "👤 Perfil")
    def perfil(message):

        if usuario_banido(message.from_user.id):

            bot.send_message(
                message.chat.id,
                "❌ Você está bloqueado."
            )

            return

        dados = perfil_usuario(
            message.from_user.id
        )

        # Proteção extra: nunca tenta acessar dados[0] se o usuário
        # não existir no banco. Isso evita TypeError em casos de dados
        # antigos ou atualização que tenha chegado fora de ordem.
        if dados is None:
            try:
                cadastrar_usuario(message)
                dados = perfil_usuario(message.from_user.id)
            except Exception as erro:
                print(f"ERRO AO GARANTIR CADASTRO NO PERFIL: {erro}")
                bot.send_message(
                    message.chat.id,
                    "❌ Não foi possível carregar seu perfil agora. Tente novamente."
                )
                return

        texto = f"""
👤 <b>SEU PERFIL</b>

🆔 ID:

<code>{message.from_user.id}</code>

👤 Nome:

{dados[0]}

📱 Username:

@{dados[1] if dados[1] else 'Sem username'}

💰 Saldo:

{dinheiro(saldo_usuario(message.from_user.id))}

⏳ Saldo pendente:

{dinheiro(saldo_pendente(message.from_user.id))}

💸 Saque pendente:

{dinheiro(saque_pendente(message.from_user.id))}

💳 PIX:

{dados[2] if dados[2] else 'Não cadastrada'}

📅 Cadastro:

{dados[3]}
"""

        bot.send_message(
            message.chat.id,
            texto,
            parse_mode="HTML"
        )

    # ==========================================
    # SALDO
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💰 Saldo")
    def saldo(message):

        if usuario_banido(message.from_user.id):

            bot.send_message(
                message.chat.id,
                "❌ Você está bloqueado."
            )

            return

        disponivel = saldo_usuario(message.from_user.id)
        pendente = saldo_pendente(message.from_user.id)
        saque = saque_pendente(message.from_user.id)

        bot.send_message(

            message.chat.id,

            f"""
💰 <b>SEU SALDO</b>

━━━━━━━━━━━━━━

💵 Disponível:

{dinheiro(disponivel)}

━━━━━━━━━━━━━━

⏳ Pendente:

{dinheiro(pendente)}

━━━━━━━━━━━━━━

💸 Em saque:

{dinheiro(saque)}
""",

            parse_mode="HTML"

        )


    # ==========================================
    # HISTÓRICO
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "📜 Histórico")
    def historico(message):

        cursor.execute(
            """
            SELECT
                tipo,
                descricao,
                valor,
                data
            FROM historico
            WHERE usuario_id=?
            ORDER BY id DESC
            LIMIT 15
            """,
            (message.from_user.id,)
        )

        registros = cursor.fetchall()

        if not registros:

            bot.send_message(
                message.chat.id,
                "📭 Você ainda não possui histórico."
            )

            return

        texto = "📜 <b>ÚLTIMAS MOVIMENTAÇÕES</b>\n\n"

        for tipo, descricao, valor, data in registros:

            texto += (
                f"📌 <b>{tipo}</b>\n"
                f"{descricao}\n"
                f"💰 {dinheiro(valor)}\n"
                f"📅 {data}\n\n"
            )

        bot.send_message(
            message.chat.id,
            texto,
            parse_mode="HTML"
        )

    # ==========================================
    # REGRAS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "📖 Regras")
    def regras(message):

        bot.send_message(

            message.chat.id,

            f"""
📖 <b>REGRAS</b>

• Convide amigos utilizando seu link.

• O amigo deve entrar no grupo.

• A indicação ficará pendente.

• O administrador analisará a indicação.

• Após aprovada, o saldo ficará disponível.

• Valor por indicação:
{dinheiro(VALOR_INDICACAO)}

• Saque mínimo:
{dinheiro(VALOR_MINIMO_SAQUE)}

Fraudes resultam em banimento.
""",

            parse_mode="HTML"

        )


    # ==========================================
    # INFORMAÇÕES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "📚 Como Usar")
    def como_usar(message):
        if usuario_banido(message.from_user.id):
            bot.send_message(message.chat.id, "❌ Você está bloqueado.")
            return

        bot.send_message(
            message.chat.id,
            """📚 <b>COMO USAR O PIT BONUS BOT</b>

"""
            """👤 <b>PERFIL</b>
"""
            """Mostra seus dados cadastrados e informações da sua conta.

"""
            """💰 <b>SALDO</b>
"""
            """Mostra seu saldo disponível e valores pendentes, quando houver.

"""
            """🔗 <b>MEU LINK</b>
"""
            """Gera/mostra seu link pessoal de indicação. Compartilhe o link para convidar novos usuários.

"""
            """👥 <b>MINHAS INDICAÇÕES</b>
"""
            """Mostra as pessoas que entraram pelo seu convite, o status da indicação, entrada no grupo e recompensa.

"""
            """💳 <b>PIX</b>
"""
            """Cadastre ou atualize sua chave Pix para receber saques. Confira a chave antes de solicitar um pagamento.

"""
            """💸 <b>SOLICITAR SAQUE</b>
"""
            """Solicita o pagamento do saldo disponível quando você atingir o valor mínimo configurado e tiver uma chave Pix cadastrada. O saque fica sujeito ao processamento da equipe.

"""
            """📜 <b>HISTÓRICO</b>
"""
            """Consulta registros das movimentações e ações da sua conta.

"""
            """🔔 <b>NOTIFICAÇÕES</b>
"""
            """Exibe avisos enviados pelo sistema e pela equipe.

"""
            """🏆 <b>RANKING</b>
"""
            """Mostra a classificação dos usuários conforme os critérios do sistema.

"""
            """🏅 <b>MEU NÍVEL</b>
"""
            """Mostra seu nível, XP e progresso de gamificação.

"""
            """🎯 <b>MISSÕES</b>
"""
            """Confira missões disponíveis e recompensas quando forem concluídas.

"""
            """👥 <b>EQUIPE</b>
"""
            """Permite consultar/criar sua equipe e acompanhar a participação dos membros conforme as regras do sistema.

"""
            """🏅 <b>CONQUISTAS</b>
"""
            """Mostra conquistas que você já desbloqueou e seu progresso.

"""
            """🔥 <b>SEQUÊNCIA</b>
"""
            """Mostra sua sequência de atividade e o progresso relacionado a ela.

"""
            """🛡️ <b>CONFIANÇA</b>
"""
            """Exibe o indicador de confiança calculado pelo sistema.

"""
            """🎁 <b>EVENTO</b>
"""
            """Quando houver um evento ativo, mostra as condições e benefícios disponíveis.

"""
            """💎 <b>VIP</b>
"""
            """Área de benefícios VIP. Quando a compra online estiver disponível, o pagamento Pix é criado pelo Mercado Pago e, após a confirmação, o sistema libera o código para resgate.

"""
            """🎟️ <b>CÓDIGO PROMOCIONAL</b>
"""
            """Use códigos fornecidos pela equipe para receber o benefício correspondente, quando disponíveis. Cada código segue as regras de uso definidas pelo administrador.

"""
            """🪙 <b>MOEDAS</b>
"""
            """Consulta suas moedas da economia interna do bot.

"""
            """🎰 <b>ROLETA</b>
"""
            """Utiliza a roleta quando você tiver acesso e tentativas disponíveis. Os resultados seguem as regras configuradas no sistema.

"""
            """🎁 <b>CAIXA SURPRESA</b>
"""
            """Permite abrir caixas quando houver disponibilidade, seguindo os limites e recompensas configurados.

"""
            """🏪 <b>LOJA</b>
"""
            """Consulta os itens/recompensas disponíveis para compra com a economia interna.

"""
            """🎫 <b>RASPADINHA</b>
"""
            """Usa uma raspadinha quando você tiver uma tentativa disponível. A recompensa depende do resultado e das regras atuais.

"""
            """🤝 <b>PARCEIROS</b>
"""
            """Exibe parceiros e campanhas disponibilizados pela equipe.

"""
            """⚔️ <b>CLÃ</b>
"""
            """Permite participar do sistema de clãs, conforme as regras e disponibilidade.

"""
            """🎫 <b>SUPORTE</b>
"""
            """Abre um atendimento <b>100% humano</b>. Escolha a categoria e descreva o problema. Um administrador da equipe poderá responder pelo ticket.

"""
            """📖 <b>REGRAS</b>
"""
            """Mostra as regras oficiais que devem ser seguidas para utilizar o bot.

"""
            """ℹ️ <b>INFORMAÇÕES</b>
"""
            """Mostra informações gerais e orientações do sistema.

"""
            """🏠 <b>MENU</b>
"""
            """Use <b>⬅️ Menu</b> para voltar ao menu principal a qualquer momento.

"""
            """⚠️ <b>IMPORTANTE</b>
"""
"""O grupo oficial pode ser obrigatório para liberar as funções. Não tente usar contas ou métodos para burlar as regras. Indicações e recompensas passam pelas validações automáticas do sistema e podem ser analisadas pela equipe.

"""
            """💬 <b>PRECISA DE AJUDA?</b>
"""
"""Abra <b>🎫 Suporte</b>, escolha a categoria e envie todos os detalhes do problema. Quanto mais informações você enviar, mais fácil será para a equipe ajudar.
""",
            parse_mode="HTML",
            reply_markup=menu_principal()
        )

    @bot.message_handler(func=lambda m: m.text == "ℹ️ Informações")
    def informacoes(message):

        bot.send_message(

            message.chat.id,

            """
ℹ️ <b>INFORMAÇÕES</b>

Este bot recompensa usuários que convidam novos membros para o grupo.

Caso tenha dúvidas, utilize o menu:

🎫 Suporte

Nossa equipe responderá o mais rápido possível.
""",

            parse_mode="HTML"

        )

    # ==========================================
    # MEU LINK
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🔗 Meu Link")
    def meu_link(message):

        if usuario_banido(message.from_user.id):

            bot.send_message(
                message.chat.id,
                "❌ Você está bloqueado."
            )

            return

        try:

            link = gerar_link(message.from_user.id)

            texto_link = f"""
🔗 <b>SEU LINK DE INDICAÇÃO</b>

Convide seus amigos usando o link abaixo:

<code>{link}</code>

📌 <b>COMO FUNCIONA</b>

1️⃣ Envie seu link para um amigo.

2️⃣ Seu amigo deve abrir o bot pelo seu link.

3️⃣ Clicar em /start.

4️⃣ Entrar no grupo oficial.

5️⃣ Clicar em <b>✅ Já entrei no grupo</b>.

6️⃣ Após a validação, a indicação será processada conforme as regras do sistema.

💰 <b>Compartilhe seu link e convide mais pessoas!</b>
"""

            foto_meu_link = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "assets",
                "meu_link.jpg"
            )

            try:
                with open(foto_meu_link, "rb") as foto:
                    bot.send_photo(
                        message.chat.id,
                        foto,
                        caption=texto_link,
                        parse_mode="HTML"
                    )
            except (FileNotFoundError, OSError) as erro_foto:
                print(f"⚠️ FOTO DE MEU LINK NÃO ENCONTRADA: {erro_foto}")
                bot.send_message(
                    message.chat.id,
                    texto_link,
                    parse_mode="HTML"
                )

        except Exception as erro:

            bot.send_message(

                message.chat.id,

                f"❌ Erro ao gerar o link.\n\n{erro}"

            )    # ==========================================
    # MINHAS INDICAÇÕES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "👥 Minhas Indicações")
    def minhas_indicacoes(message):

        if usuario_banido(message.from_user.id):

            bot.send_message(
                message.chat.id,
                "❌ Você está bloqueado."
            )

            return

        lista = indicacoes_usuario(message.from_user.id)

        if not lista:

            bot.send_message(
                message.chat.id,
                "👥 Você ainda não possui indicações."
            )

            return

        texto = "👥 <b>SUAS INDICAÇÕES</b>\n\n"

        for indicado, valor, status, grupo, data in lista:

            grupo_texto = "✅ Sim" if grupo else "❌ Não"

            texto += f"""
━━━━━━━━━━━━━━

👤 ID:
<code>{indicado}</code>

💰 Valor:
{dinheiro(valor)}

📌 Status:
{status}

👥 Entrou no grupo:
{grupo_texto}

📅 Data:
{data}

"""

        bot.send_message(
            message.chat.id,
            texto,
            parse_mode="HTML"
        )


    # ==========================================
    # MENU
    # ==========================================

    @bot.message_handler(
        func=lambda m: m.text == "⬅️ Menu" or m.text == "/menu"
    )
    def menu(message):

        bot.send_message(
            message.chat.id,
            "🏠 Menu Principal",
            reply_markup=menu_principal()
        )


    # =====================================================
    # NOTIFICAÇÕES
    # =====================================================

    @bot.message_handler(func=lambda m: m.text == "🔔 Notificações")
    def notificacoes(message):

        if usuario_banido(message.from_user.id):
            bot.send_message(
                message.chat.id,
                "❌ Você está bloqueado."
            )
            return

        lista = notificacoes_usuario(
            message.from_user.id
        )

        if not lista:
            bot.send_message(
                message.chat.id,
                "🔔 Você não possui novas notificações."
            )
            return

        partes = []

        for _, titulo, mensagem, lida, data in lista:
            marcador = "🔵" if not lida else "⚪"
            partes.append(
                f"""
{marcador} <b>{titulo}</b>
📅 {data}

{mensagem}
"""
            )

        marcar_notificacoes_lidas(
            message.from_user.id
        )

        bot.send_message(
            message.chat.id,
            "🔔 <b>NOTIFICAÇÕES</b>\n" + "\n━━━━━━━━━━━━━━\n".join(partes),
            parse_mode="HTML"
        )

    # =====================================================
    # RANKING DO USUÁRIO
    # =====================================================

    @bot.message_handler(func=lambda m: m.text == "🏆 Ranking")
    def ranking_usuario(message):

        if usuario_banido(message.from_user.id):
            bot.send_message(
                message.chat.id,
                "❌ Você está bloqueado."
            )
            return

        cursor.execute(
            """
            SELECT
                u.id,
                u.nome,
                COUNT(i.id) AS total
            FROM usuarios u
            LEFT JOIN indicacoes i
                ON i.indicador_id=u.id
                AND i.status='APROVADO'
            GROUP BY u.id
            HAVING total > 0
            ORDER BY total DESC
            LIMIT 10
            """
        )

        ranking = cursor.fetchall()

        if not ranking:
            bot.send_message(
                message.chat.id,
                "🏆 Ainda não existem indicações aprovadas."
            )
            return

        posicao = None
        for pos, linha in enumerate(ranking, 1):
            if linha[0] == message.from_user.id:
                posicao = pos
                break

        linhas = []

        for pos, (_, nome, total) in enumerate(ranking, 1):
            medalha = {1: "🥇", 2: "🥈", 3: "🥉"}.get(
                pos,
                f"{pos}️⃣"
            )
            linhas.append(
                f"{medalha} {nome or 'Usuário'} — {total}"
            )

        texto_posicao = (
            f"\n📍 Sua posição: <b>#{posicao}</b>"
            if posicao
            else "\n📍 Você ainda não está entre os 10 primeiros."
        )

        bot.send_message(
            message.chat.id,
            "🏆 <b>RANKING DE INDICADORES</b>\n\n"
            + "\n".join(linhas)
            + texto_posicao,
            parse_mode="HTML"
        )
