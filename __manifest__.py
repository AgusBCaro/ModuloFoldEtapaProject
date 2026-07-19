{
    'name': 'Auto-Fold Etapas por Mes',
    'version': '16.0.1.0',
    'category': 'Project',
    'summary': 'Dobla automáticamente las etapas de meses que no sean el actual ni el anterior. Avisa al responsable si hay tareas pendientes.',
    'author': 'Tu Nombre',
    'depends': ['project'],
    'data': [
    ],
    'assets': {
        'web.assets_backend': [
            'ModuloFoldEtapaProject/static/src/js/project_month_fold.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
