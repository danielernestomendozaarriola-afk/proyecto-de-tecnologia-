"""Lógica financiera conectada a MySQL (misma idea de GestorFinanciero, ahora persistente)."""
import os
from datetime import date
import mysql.connector

CATEGORIAS = ("alimentacion", "transporte", "educacion", "entretenimiento", "otros")


def get_conexion():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "Jutta2026"),
        database=os.getenv("DB_NAME", "control_gastos_personales"),
    )


def consultar(sql, params=(), modo="all"):
    """modo: 'all' (lista), 'one' (una fila) o 'write' (INSERT/UPDATE/DELETE -> (lastrowid, filas))."""
    con = get_conexion()
    try:
        cur = con.cursor(dictionary=True)
        cur.execute(sql, params)
        if modo == "write":
            con.commit()
            return cur.lastrowid, cur.rowcount
        return cur.fetchone() if modo == "one" else cur.fetchall()
    finally:
        con.close()


def _monto(valor):
    try:
        monto = round(float(valor), 2)
    except (TypeError, ValueError):
        raise ValueError("El monto debe ser un número.")
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")
    return monto


class GestorFinanciero:
    def __init__(self, id_usuario):
        self.id_usuario = id_usuario

    def agregar_ingreso(self, descripcion, monto, fecha=None):
        monto = _monto(monto)
        return consultar(
            "insert into ingresos (id_usuario, cantidad, fecha, descripcion) values (%s,%s,%s,%s)",
            (self.id_usuario, monto, fecha or date.today(), (descripcion or "Ingreso")[:100]), "write")[0]

    def agregar_gasto(self, descripcion, monto, categoria="otros", fecha=None):
        monto = _monto(monto)
        if categoria not in CATEGORIAS:
            raise ValueError("Categoría no válida.")
        if not descripcion:
            raise ValueError("Escribe una descripción.")
        return consultar(
            "insert into gastos (id_usuario, nombre_gasto, categoria, cantidad, fecha) values (%s,%s,%s,%s,%s)",
            (self.id_usuario, descripcion[:100], categoria, monto, fecha or date.today()), "write")[0]

    def eliminar_ingreso(self, id_ingreso):
        return consultar("delete from ingresos where id_ingreso=%s and id_usuario=%s",
                         (id_ingreso, self.id_usuario), "write")[1] > 0

    def eliminar_gasto(self, id_gasto):
        return consultar("delete from gastos where id_gasto=%s and id_usuario=%s",
                         (id_gasto, self.id_usuario), "write")[1] > 0

    def _total(self, tabla):
        r = consultar(f"select coalesce(sum(cantidad),0) as t from {tabla} where id_usuario=%s",
                      (self.id_usuario,), "one")
        return float(r["t"])

    def calcular_total_ingresos(self):
        return self._total("ingresos")

    def calcular_total_gastos(self):
        return self._total("gastos")

    def calcular_balance(self):
        ti, tg = self.calcular_total_ingresos(), self.calcular_total_gastos()
        return {"total_ingresos": ti, "total_gastos": tg, "balance_neto": round(ti - tg, 2)}

    def gastos_por_categoria(self):
        filas = consultar("select categoria, sum(cantidad) as total from gastos "
                          "where id_usuario=%s group by categoria", (self.id_usuario,))
        return {f["categoria"]: float(f["total"]) for f in filas}
    
    def resumen_mensual(self, meses=6):
        """Devuelve ingresos y gastos agrupados por mes."""
        meses = int(meses)

        if meses not in (6, 12):
            raise ValueError("El período debe ser de 6 o 12 meses.")

        hoy = date.today()

        # Calcular el primer mes del período solicitado.
        indice_actual = hoy.year * 12 + hoy.month - 1
        indice_inicio = indice_actual - (meses - 1)
        anio_inicio, mes_inicio = divmod(indice_inicio, 12)
        desde = date(anio_inicio, mes_inicio + 1, 1)

        filas = consultar(
            """
            SELECT DATE_FORMAT(fecha, '%Y-%m') AS mes,
                   tipo,
                   SUM(cantidad) AS total
            FROM (
                SELECT fecha, cantidad, 'ingreso' AS tipo
                FROM ingresos
                WHERE id_usuario = %s
                  AND fecha >= %s AND fecha <= %s

                UNION ALL

                SELECT fecha, cantidad, 'gasto' AS tipo
                FROM gastos
                WHERE id_usuario = %s
                  AND fecha >= %s AND fecha <= %s
            ) AS movimientos
            GROUP BY DATE_FORMAT(fecha, '%Y-%m'), tipo
            ORDER BY mes
            """,
            (self.id_usuario, desde, hoy,
             self.id_usuario, desde, hoy)
        )

        nombres_meses = [
            "Enero", "Febrero", "Marzo", "Abril",
            "Mayo", "Junio", "Julio", "Agosto",
            "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]

        # Crear todos los meses, incluso los que no tengan movimientos.
        resultado = {}

        for desplazamiento in range(meses):
            indice = indice_inicio + desplazamiento
            anio, mes_cero = divmod(indice, 12)
            numero_mes = mes_cero + 1
            clave = f"{anio}-{numero_mes:02d}"

            resultado[clave] = {
                "mes": clave,
                "etiqueta": f"{nombres_meses[mes_cero]} {anio}",
                "ingresos": 0.0,
                "gastos": 0.0
            }

        for fila in filas:
            clave = fila["mes"]

            if clave in resultado:
                resultado[clave][
                    "ingresos" if fila["tipo"] == "ingreso"
                    else "gastos"
                ] = float(fila["total"] or 0)

        return {
            "periodo": meses,
            "meses": list(resultado.values())
        }


    def listar_movimientos(self, limite=50):
        filas = consultar(
            "select 'ingreso' as tipo, id_ingreso as id, coalesce(descripcion,'Ingreso') as descripcion, "
            "null as categoria, cantidad, fecha from ingresos where id_usuario=%s "
            "union all "
            "select 'gasto', id_gasto, nombre_gasto, categoria, cantidad, fecha from gastos where id_usuario=%s "
            "order by fecha desc, id desc limit %s", (self.id_usuario, self.id_usuario, limite))
        for f in filas:
            f["cantidad"] = float(f["cantidad"])
            f["fecha"] = f["fecha"].isoformat()
        return filas
