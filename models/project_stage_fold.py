from odoo import models, api
from datetime import date

# Meses en español indexados por número de mes
MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

# Nombres de etapas de tareas que se consideran "pendientes"
# Una tarea está pendiente si está en cualquiera de estos estados (comparación case-insensitive)
ETAPAS_PENDIENTES = ['en progreso', 'cancelada']


class ProjectProjectStage(models.Model):
    """
    Hereda project.project.stage para agregar la lógica de auto-fold
    de etapas según el mes actual y el mes anterior.
    """
    _inherit = 'project.project.stage'

    @api.model
    def auto_fold_month_stages(self):
        """
        Dobla automáticamente todas las etapas cuyos nombres coincidan con
        un mes en español, excepto el mes actual y el mes anterior.

        Ejemplo (si hoy es Julio 2026):
          - Julio  → fold = False  (mes actual)
          - Junio  → fold = False  (mes anterior)
          - Resto  → fold = True
        """
        hoy = date.today()
        mes_actual = hoy.month
        mes_anterior = mes_actual - 1 if mes_actual > 1 else 12

        # Conjuntos de nombres de meses que deben permanecer abiertos (lowercase)
        meses_abiertos = {
            MESES_ES[mes_actual].lower(),
            MESES_ES[mes_anterior].lower(),
        }

        # Todos los nombres de meses válidos (lowercase) para identificar etapas de mes
        todos_los_meses = {v.lower() for v in MESES_ES.values()}

        etapas = self.search([])
        for etapa in etapas:
            nombre = etapa.name.strip().lower()

            # Solo procesamos etapas cuyo nombre sea exactamente un mes
            if nombre not in todos_los_meses:
                continue

            debe_doblar = nombre not in meses_abiertos

            # Solo escribir si el valor cambió, para evitar writes innecesarios
            if etapa.fold != debe_doblar:
                etapa.sudo().write({'fold': debe_doblar})


class ProjectProject(models.Model):
    """
    Hereda project.project para agregar el método que:
      1. Dispara el auto-fold de etapas.
      2. Devuelve advertencias al responsable sobre proyectos con tareas
         pendientes en meses que deberían estar doblados.
    """
    _inherit = 'project.project'

    @api.model
    def get_month_pending_warnings(self):
        """
        Método llamado desde el frontend al cargar la vista Kanban de proyectos.

        Pasos:
          1. Ejecuta auto_fold_month_stages() para actualizar el estado fold de las etapas.
          2. Determina qué etapas de meses deberían estar dobladas.
          3. Para cada etapa doblada, busca proyectos donde el usuario actual
             sea el responsable (user_id) Y que tengan tareas en etapas 'En Progreso'
             o 'Cancelada'.
          4. Por cada coincidencia, arma un mensaje de advertencia.

        Retorna:
          list[dict]: Lista de {'mes': str, 'proyecto': str} para mostrar al usuario.
        """
        # 1. Auto-fold de etapas
        self.env['project.project.stage'].auto_fold_month_stages()

        # 2. Calcular meses que no deben doblarse
        hoy = date.today()
        mes_actual = hoy.month
        mes_anterior = mes_actual - 1 if mes_actual > 1 else 12

        meses_no_doblar = {
            MESES_ES[mes_actual].lower(),
            MESES_ES[mes_anterior].lower(),
        }

        # Mapa de nombre lowercase → nombre con capitalización correcta para mostrar
        nombres_meses_display = {v.lower(): v for v in MESES_ES.values()}
        uid = self.env.uid
        advertencias = []

        # 3. Recorrer etapas que representan meses y que deben estar dobladas
        etapas = self.env['project.project.stage'].search([])
        for etapa in etapas:
            nombre_lower = etapa.name.strip().lower()

            # ¿Es una etapa de mes?
            if nombre_lower not in nombres_meses_display:
                continue

            # ¿Es un mes que debería estar doblado?
            if nombre_lower in meses_no_doblar:
                continue

            nombre_mes_display = nombres_meses_display[nombre_lower]

            # 4. Buscar proyectos en esta etapa donde el responsable sea el usuario actual
            proyectos = self.search([
                ('stage_id', '=', etapa.id),
                ('user_id', '=', uid),
            ])

            for proyecto in proyectos:
                # Verificar si el proyecto tiene tareas con etapa 'En Progreso' o 'Cancelada'
                dominio_tareas_pendientes = [
                    ('project_id', '=', proyecto.id),
                    '|',
                    ('stage_id.name', '=ilike', 'en progreso'),
                    ('stage_id.name', '=ilike', 'cancelada'),
                ]

                tiene_pendientes = bool(
                    self.env['project.task'].search(dominio_tareas_pendientes, limit=1)
                )

                if tiene_pendientes:
                    advertencias.append({
                        'mes': nombre_mes_display,
                        'proyecto': proyecto.name,
                    })

        return advertencias
