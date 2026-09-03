from database import cursor, conn
from utils import data_atual

# ==========================================
# VERIFICAR BANIMENTO
# ==========================================

def usuario_banido(usuario_id):

    cursor.execute(
        """
        SELECT banido
        FROM usuarios
        WHERE id=?
        """,
        (usuario_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0] == 1

    return False


# ==========================================
# REGISTRAR FRAUDE
# ==========================================

def registrar_fraude(usuario_id, indicador_id, motivo, acao):

    cursor.execute(
        """
        INSERT INTO fraudes
        (
            usuario_id,
            indicador_id,
            motivo,
            acao,
            data
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            usuario_id,
            indicador_id,
            motivo,
            acao,
            data_atual()
        )
    )

    conn.commit()


# ==========================================
# VALIDAR INDICAÇÃO
# ==========================================

def validar_indicacao(indicador_id, indicado_id):

    # Auto indicação
    if indicador_id == indicado_id:

        registrar_fraude(
            indicado_id,
            indicador_id,
            "Auto indicação",
            "Bloqueado"
        )

        return False, "Você não pode indicar a si mesmo."

    # Usuário banido
    if usuario_banido(indicado_id):

        registrar_fraude(
            indicado_id,
            indicador_id,
            "Usuário banido",
            "Bloqueado"
        )

        return False, "Este usuário está bloqueado."

    # Já foi indicado anteriormente
    cursor.execute(
        """
        SELECT id
        FROM indicacoes
        WHERE indicado_id=?
        """,
        (indicado_id,)
    )

    if cursor.fetchone():

        registrar_fraude(
            indicado_id,
            indicador_id,
            "Indicação duplicada",
            "Ignorado"
        )

        return False, "Este usuário já foi indicado."

    return True, "OK"


# ==========================================
# LISTAR FRAUDES
# ==========================================

def listar_fraudes():

    cursor.execute(
        """
        SELECT
            id,
            usuario_id,
            indicador_id,
            motivo,
            acao,
            data
        FROM fraudes
        ORDER BY id DESC
        """
    )

    return cursor.fetchall()

# ==========================================
# BANIR USUÁRIO
# ==========================================

def banir_usuario(usuario_id):

    cursor.execute(
        """
        UPDATE usuarios
        SET banido=1
        WHERE id=?
        """,
        (usuario_id,)
    )

    conn.commit()

    return True


# ==========================================
# DESBANIR USUÁRIO
# ==========================================

def desbanir_usuario(usuario_id):

    cursor.execute(
        """
        UPDATE usuarios
        SET banido=0
        WHERE id=?
        """,
        (usuario_id,)
    )

    conn.commit()

    return True


def analisar_risco_saque(usuario_id, valor=0):
    """Calcula um risco simples e explicável para ajudar o admin a revisar saques."""
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0.0

    cursor.execute("SELECT confianca FROM gamificacao WHERE usuario_id=?", (usuario_id,))
    row = cursor.fetchone()
    confianca = int(row[0]) if row and row[0] is not None else 50

    cursor.execute("SELECT COUNT(*) FROM indicacoes WHERE indicador_id=? AND status='APROVADO'", (usuario_id,))
    aprovadas = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM indicacoes WHERE indicador_id=? AND status='REJEITADO'", (usuario_id,))
    rejeitadas = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM fraudes WHERE usuario_id=? OR indicador_id=?", (usuario_id, usuario_id))
    fraudes = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM saques WHERE usuario_id=? AND status IN ('PAGO','APROVADO')", (usuario_id,))
    saques_pagos = cursor.fetchone()[0] or 0

    pontos = 0
    motivos = []
    if confianca < 40:
        pontos += 35; motivos.append("confiança baixa")
    elif confianca < 60:
        pontos += 15; motivos.append("confiança média")
    if rejeitadas >= 3:
        pontos += 20; motivos.append("muitas indicações rejeitadas")
    elif rejeitadas >= 1:
        pontos += 8; motivos.append("há indicação rejeitada")
    if fraudes:
        pontos += min(40, fraudes * 20); motivos.append("ocorrência antifraude")
    if aprovadas == 0:
        pontos += 15; motivos.append("nenhuma indicação aprovada")
    if valor >= 100:
        pontos += 10; motivos.append("saque de valor elevado")
    if saques_pagos >= 3 and fraudes == 0:
        pontos = max(0, pontos - 10)

    risco = "BAIXO" if pontos < 25 else "MÉDIO" if pontos < 55 else "ALTO"
    emoji = "🟢" if risco == "BAIXO" else "🟡" if risco == "MÉDIO" else "🔴"
    return {"score": min(100, pontos), "risco": risco, "emoji": emoji, "motivos": motivos, "confianca": confianca, "aprovadas": aprovadas, "rejeitadas": rejeitadas, "fraudes": fraudes}
