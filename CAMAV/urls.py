"""
URL configuration for camav project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from gestionInterna import views
# CRUD views are defined in gestionInterna.views (integrated)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('createpedido/', views.createpedido, name='createpedido'),
    path('detalle_pedido/<int:pedido_id>/', views.detalle_pedido, name='detalle_pedido'),
    path('create_tarea/<int:pedido_id>/', views.create_tarea, name='create_tarea'),
    path('paneltareas/', views.paneltareas, name='paneltareas'),
    path('detalle_tarea/<int:tarea_id>/', views.detalle_tarea, name='detalle_tarea'),
    path('create_observacion/<int:tarea_id>/', views.create_observacion, name='create_observacion'),
    path('listapedidosrevisados/', views.listapedidosrevisados, name='listapedidosrevisados'),
    path('historial_amortiguador/<int:amortiguador_id>/', views.historial_amortiguador, name='historial_amortiguador'),
    path('tareas_en_reparacion/', views.tareas_en_reparacion, name='tareas_en_reparacion'),
    path('finalizar_reparacion/<int:tarea_id>/', views.finalizar_reparacion, name='finalizar_reparacion'),
    path('pedidos_terminados/', views.pedidos_terminados, name='pedidos_terminados'),
    path('emitir_comprobante/<int:pedido_id>/', views.emitir_comprobante, name='emitir_comprobante'),
    path("crear_operario/", views.crear_operario, name="operarios_create"),
        # Operarios: create/edit using same form (like fichaamortiguador)
        path('operario/create/', views.crear_operario, name='operario_create'),
        path('operario/<int:pk>/edit/', views.crear_operario, name='operario_edit'),
    path('operarios/', views.lista_operarios, name='estado_operarios'),
    path("operarios/eliminar/", views.eliminar_operarios, name="operarios_delete"),
    path("operarios/actualizar/", views.actualizar_operarios, name="operarios_update"),
        #MATERIALES
    path('materiales/', views.materiales_list, name='material_list'),
    path('material/<int:pk>/', views.material_detail, name='material_detail'),
    path('material/new/', views.material_create, name='material_create'),
    path('material/ajax/create/', views.material_create_ajax, name='material_create_ajax'),
    path('material/<int:pk>/edit/', views.material_update, name='material_update'),
    path('material/<int:pk>/delete/', views.material_delete, name='material_delete'),
    path('material/<int:pk>/stock/', views.stock_update, name='stock_update'),
    path('material/<int:pk>/movimientos/', views.movimientos_list, name='movimientos_list'),
    path('material/reporte/', views.material_reporte, name='material_reporte'),
    ##PEDIDOS
    path('pedidos/cerrar/', views.buscar_pedido_por_dni, name='buscar_pedido_por_dni'),
    path('pedidos/<int:pk>/cerrar/', views.cerrar_pedido, name='cerrar_pedido'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    # Ficha Amortiguador CRUD
    path('fichaamortiguador/', views.fichaamortiguador_list, name='fichaamortiguador_list'),
    path('fichaamortiguador/create/', views.fichaamortiguador_create, name='fichaamortiguador_create'),
    path('fichaamortiguador/<int:pk>/edit/', views.fichaamortiguador_edit, name='fichaamortiguador_edit'),
    path('fichaamortiguador/<int:pk>/delete/', views.fichaamortiguador_delete, name='fichaamortiguador_delete'),

    # Cliente CRUD
    path('cliente/', views.cliente_list, name='cliente_list'),
    path('cliente/create/', views.cliente_create, name='cliente_create'),
    path('cliente/<int:pk>/edit/', views.cliente_edit, name='cliente_edit'),
    path('cliente/<int:pk>/delete/', views.cliente_delete, name='cliente_delete'),
    path('cliente/<int:pk>/view/', views.cliente_view, name='cliente_view'),
]

