/** @odoo-module **/

/**
 * ModuloFoldEtapaProject — project_month_fold.js
 *
 * Intercepta la carga de la vista Kanban de project.project para:
 *  1. Disparar auto-fold de etapas por mes (vía RPC al modelo Python).
 *  2. Mostrar notificaciones sticky de advertencia al responsable del proyecto
 *     cuando un mes que debería estar doblado tiene tareas pendientes.
 *
 * Compatible con Odoo 16 (OWL + KanbanController patch).
 */

import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";

patch(KanbanController.prototype, "project_month_fold_warnings", {
    /**
     * Extendemos setup() del KanbanController.
     * Solo actúa cuando el modelo activo es 'project.project'.
     */
    setup() {
        // Llamar al setup original primero
        this._super(...arguments);

        // Verificar que estamos en la vista Kanban de proyectos
        if (this.model?.config?.resModel !== "project.project") {
            return;
        }

        // Servicios de Odoo 16
        const notification = useService("notification");
        const orm = useService("orm");

        onMounted(async () => {
            try {
                /**
                 * Llama al método Python get_month_pending_warnings().
                 * Este método también ejecuta el auto-fold de etapas internamente.
                 *
                 * Retorna: Array de { mes: string, proyecto: string }
                 */
                const warnings = await orm.call(
                    "project.project",
                    "get_month_pending_warnings",
                    [],
                    {}
                );

                if (!warnings || warnings.length === 0) {
                    return;
                }

                // Mostrar una notificación sticky por cada advertencia
                for (const w of warnings) {
                    notification.add(
                        `El mes ${w.mes} no puede ser doblado ya que el proyecto "${w.proyecto}" tiene tareas pendientes`,
                        {
                            title: "⚠️ Advertencia de Cierre de Mes",
                            type: "warning",
                            // sticky: true → el usuario debe cerrarla manualmente
                            sticky: true,
                        }
                    );
                }
            } catch (error) {
                // Logueamos el error sin interrumpir la experiencia del usuario
                console.error(
                    "[ModuloFoldEtapaProject] Error al verificar advertencias de mes:",
                    error
                );
            }
        });
    },
});
