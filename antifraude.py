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
