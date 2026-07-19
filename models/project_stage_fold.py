from odoo import models, api
from datetime import date
#HOla
# Meses en español indexados por número de mes
MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

# Criterio de tareas pendientes: kanban_state == 'normal' (En progreso)


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

        Adicionalmente, si un mes que debería doblarse contiene algún proyecto
        con tareas pendientes (en progreso o canceladas), ese mes NO se doblará
        (se dejará con fold = False).
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

            if nombre in meses_abiertos:
                # El mes actual y anterior siempre están abiertos (no se doblan)
                debe_doblar = False
            else:
                # Si el mes no es el actual ni el anterior, debería doblarse.
                # Pero si contiene algún proyecto con tareas pendientes (en progreso), NO se dobla.
                proyectos_en_etapa = self.env['project.project'].search([('stage_id', '=', etapa.id)])
                tiene_tareas_pendientes = False
                for proj in proyectos_en_etapa:
                    tareas_pendientes = self.env['project.task'].search_count([
                        ('project_id', '=', proj.id),
                        ('kanban_state', '=', 'normal'),
                    ])
                    if tareas_pendientes > 0:
                        tiene_tareas_pendientes = True
                        break

                if tiene_tareas_pendientes:
                    debe_doblar = False  # No se dobla porque tiene tareas pendientes
                else:
                    debe_doblar = True

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
    def read_group(self, *args, **kwargs):
        """
        Sobrescribe read_group para disparar el auto-fold en el backend
        cada vez que Odoo agrupe los proyectos por su etapa (stage_id).
        Usa *args y **kwargs para evitar errores de firma con parámetros
        propios de Odoo o de otros módulos.
        """
        groupby = kwargs.get('groupby') or (args[2] if len(args) > 2 else None)
        if groupby and any(g.split(':')[0] == 'stage_id' for g in groupby):
            self.env['project.project.stage'].auto_fold_month_stages()
        return super(ProjectProject, self).read_group(*args, **kwargs)

    @api.model
    def web_read_group(self, *args, **kwargs):
        """
        Sobrescribe web_read_group (usado por vistas kanban/listas) para disparar el auto-fold.
        Usa *args y **kwargs para evitar errores de firma con parámetros
        como 'expand_orderby' propios de Odoo 16.
        """
        groupby = kwargs.get('groupby') or (args[2] if len(args) > 2 else None)
        if groupby and any(g.split(':')[0] == 'stage_id' for g in groupby):
            self.env['project.project.stage'].auto_fold_month_stages()
        return super(ProjectProject, self).web_read_group(*args, **kwargs)

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

            # ¿Es un mes que debería estar doblado? (los que no son el actual ni el anterior)
            if nombre_lower in meses_no_doblar:
                continue

            nombre_mes_display = nombres_meses_display[nombre_lower]

            # 4. Buscar proyectos en esta etapa donde el responsable sea el usuario actual
            proyectos = self.search([
                ('stage_id', '=', etapa.id),
                ('user_id', '=', uid),
            ])

            for proyecto in proyectos:
                # Verificar si el proyecto tiene tareas en estado 'En progreso' (kanban_state == 'normal')
                dominio_tareas_pendientes = [
                    ('project_id', '=', proyecto.id),
                    ('kanban_state', '=', 'normal'),
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
