from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from collections import defaultdict
from openpyxl import Workbook
import io
import json
from django.http import FileResponse,JsonResponse
from reportlab.pdfgen import canvas
from django.urls import reverse
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count,Q ,F
from django.http import HttpResponse
from .models import Cliente , Pedido, Operario, Amortiguador, Fichaamortiguador, Tarea, Observacion, Material, MaterialFichaAmortiguador, MaterialTarea, Notificacion, MovimientoStock
from .forms import MaterialForm, StockUpdateForm, BuscarPedidoForm, CerrarPedidoForm
from django.utils import timezone

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    return render(request, 'login.html')

def home(request):
    return render(request, 'home.html')

def createpedido(request):
        context = {}
        if request.method == 'POST':
            accion = request.POST.get('accion')
            dni = request.POST.get('dni')
            context['dni'] = dni
            if accion == 'buscar_cliente':
                try:
                    cliente = Cliente.objects.get(dni=dni)
                    context['cliente'] = cliente
                except Cliente.DoesNotExist:
                    context['cliente_no_encontrado'] = True
                return render(request, 'createpedido.html', context)
            elif accion == 'crear_cliente_pedido':
                cliente = Cliente.objects.create( 
                    nombre=request.POST.get('nombre'),
                    apellido=request.POST.get('apellido'),
                    dni=request.POST.get('dni'),
                    telefono=request.POST.get('telefono'),
                    correo=request.POST.get('correo')
                )
                pedido = Pedido.objects.create(
                    estado='pendiente',
                    cliente=cliente
                )
                return redirect('detalle_pedido', pedido_id=pedido.id)
            elif accion == 'crear_pedido':
                try:
                    id_cliente = request.POST.get('cliente_id')
                    cliente = Cliente.objects.get(id=id_cliente)
                    pedido = Pedido.objects.create(
                        estado='pendiente',
                        cliente=cliente
                    )
                    return redirect('detalle_pedido', pedido_id=pedido.id)
                except Cliente.DoesNotExist:
                    context['error'] = "No se puede crear el pedido. Cliente no encontrado."

        return render(request, 'createpedido.html', context)
    
def detalle_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    tareas = Tarea.objects.filter(pedido=pedido)
    
    
    mensaje_exito = None
    if tareas.exists() and all(t.estado in ['terminada', 'por reparar'] for t in tareas):
        mensaje_exito = '¡Todas las tareas están finalizadas o por reparar!'
        pedido.estado = 'por reparar'
        pedido.save()
    if tareas.exists() and all(t.estado in 'terminada' for t in tareas):
        pedido.estado = 'terminado'
        pedido.save()
        mensaje_exito = '¡El pedido ha sido finalizado, avisale al cliente!'
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'crear_tarea':
            return redirect('create_tarea', pedido_id=pedido.id)
        elif accion == 'finalizar_pedido':
            fecha_limite = request.POST.get('fecha_limite')
            try:
                for tarea in tareas:
                    tarea.fechaLimite = fecha_limite
                    tarea.save()
                pedido.fechaSalidaEstimada = fecha_limite
                pedido.save()
                return redirect('home')

            except ValueError:
                mensaje_exito = 'Fecha inválida. Por favor, ingrese una fecha válida.'

    return render(request, 'detalle_pedido.html', {'pedido': pedido, 'tareas': tareas, 'mensaje_exito': mensaje_exito})


def create_tarea(request, pedido_id):
    operarios = Operario.objects.all()
    fichas = Fichaamortiguador.objects.all()
    pedido = get_object_or_404(Pedido, id=pedido_id)
    context = { 'operarios': operarios, 'fichas': fichas, 'pedido': pedido }
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'buscar':
            try:
                amortiguador = Amortiguador.objects.get(nroSerieamortiguador=request.POST.get('nroSerieamortiguador'))
                context['amortiguador'] = amortiguador
            except Amortiguador.DoesNotExist:
                context['no_amortiguador'] = True
                context['nroSerieamortiguador'] = request.POST.get('nroSerieamortiguador')
        elif accion == 'crear_amortiguador_tarea':
            ficha = get_object_or_404(Fichaamortiguador, id = request.POST.get('ficha_amortiguador'))
            amortiguador = Amortiguador.objects.create(
                fichaamortiguador = ficha,
                nroSerieamortiguador = request.POST.get('nroSerieamortiguador'),
                tipo = request.POST.get('tipo_amortiguador')
            )
            operario = get_object_or_404(Operario,id = request.POST.get('operario'))
            tarea = Tarea.objects.create(
                prioridad = request.POST.get('prioridad'),
                amortiguador = amortiguador,
                operario = operario,
                pedido = pedido,
                estado = 'pendiente'
            ) 
            return redirect('detalle_pedido', pedido_id=pedido.id)
        elif accion =='crear_tarea':
            operario = get_object_or_404(Operario,id = request.POST.get('operario'))
            amortiguador = get_object_or_404(Amortiguador, id = request.POST.get('id_amortiguador'))
            tarea = Tarea.objects.create(
                prioridad = request.POST.get('prioridad'),
                amortiguador = amortiguador,
                operario = operario,
                pedido = pedido,
                estado = 'pendiente'
            ) 
            return redirect('detalle_pedido', pedido_id=pedido.id)

    return render(request, 'create_tarea.html', context)

def paneltareas(request):
    operarios = Operario.objects.all()
    context = { 'operarios': operarios }
    if request.method == 'POST':
        accion = request.POST.get('accion')
        estadoselect = request.POST.get('estado')
        context['estadoselect'] = estadoselect
        priority = request.POST.get('prioridad')
        context['priority'] = priority
        if accion == 'elegiroperario':
            operario_id = request.POST.get('operario')
            operario = get_object_or_404(Operario, id=operario_id)
            tareas = Tarea.objects.filter(operario=operario, estado=estadoselect, prioridad=priority)
            if estadoselect == 'por reparar':
                # Para cada tarea 'por reparar' comprobamos si hay stock suficiente
                tareas_info = []
                for t in tareas:
                    missing = []
                    # Primero, si ya hay MaterialTarea asociado, usamos sus cantidades recomendadas
                    mts = MaterialTarea.objects.filter(tarea=t)
                    if mts.exists():
                        for mt in mts:
                            mat = mt.material
                            req = int(mt.stockrecomendado or 0)
                            avail = max(0, int(mat.stockActual or 0) - int(mat.stockreservado or 0))
                            if avail < req:
                                missing.append({'material': mat, 'required': req, 'available': avail})
                    tareas_info.append({'tarea': t, 'has_stock': len(missing) == 0, 'missing': missing})
                    # Crear una notificación si falta stock y no existe una abierta
                    if len(missing) > 0:
                        # evitar duplicados: notificacion abierta para la misma tarea
                        existing = Notificacion.objects.filter(tarea=t, resolved=False)
                        if not existing.exists():
                            import json
                            Notificacion.objects.create(tarea=t, materiales=json.dumps([
                                {'material_id': m['material'].id, 'material_tipo': m['material'].tipo, 'required': m['required'], 'available': m['available']} for m in missing
                            ]))
                context['tareas_info'] = tareas_info
            # pasar notificaciones pendientes al contexto
            notifs = Notificacion.objects.filter(resolved=False).order_by('-fecha_solicitud')
            import json
            notif_list = []
            for n in notifs:
                try:
                    mat_list = json.loads(n.materiales)
                except Exception:
                    mat_list = []
                notif_list.append({'notificacion': n, 'materiales': mat_list})
            context['notificaciones'] = notif_list
            context['tareas'] = tareas
            context['operario'] = operario
    return render(request, 'paneltareas.html', context)

def detalle_tarea(request, tarea_id):
    tarea= get_object_or_404(Tarea, id=tarea_id)
    context = {'tarea': tarea}
    observaciones = Observacion.objects.filter(tarea=tarea)
    context['observaciones'] = observaciones
    materialxamortiguador = MaterialFichaAmortiguador.objects.filter(fichaamortiguador=tarea.amortiguador.fichaamortiguador)
    materialxtarea = MaterialTarea.objects.filter(tarea=tarea)
    context['materialxtarea'] = materialxtarea
    context['materialxamortiguador'] = materialxamortiguador
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'terminarobservacioncontrol':
            tarea.estado = 'revisada'
            tarea.save()
            context['class'] = 'alert alert-success'
            context['message'] = 'Has finalizado las observaciones de control de calidad.'
            tareas = Tarea.objects.filter(pedido= tarea.pedido)
            if all(t.estado == 'revisada' for t in tareas):
                pedido = tarea.pedido
                pedido.estado = 'revisado'
                pedido.save()
            return redirect('home')
        elif accion == 'confirmarreparacion':
            confirmarreparacion = request.POST.get('confirmarreparacion')
            if confirmarreparacion == 'control':
                tarea.tipoTarea = 'control'
                tarea.estado = 'terminada'
                tarea.save()
                return redirect('detalle_pedido', pedido_id=tarea.pedido.id)
            elif confirmarreparacion == 'reparacion':
                tarea.tipoTarea = 'reparacion'
                tarea.estado = 'por reparar'
                tarea.save()
                # volver a la vista de detalle para recargar desde la base de datos
                return redirect('detalle_tarea', tarea_id=tarea.id)
        elif accion == 'reservar_materiales':
            for mt in materialxtarea:
                mat = mt.material
                incremento = int(mt.stockrecomendado or 0)
                mat.stockreservado = int(mat.stockreservado or 0) + incremento
                mat.save()
            tarea.estado = 'en reparacion'
            tarea.save()
            return redirect('home')

        elif accion == 'agregarmaterialtarea':
            material_ids = request.POST.getlist('material_id[]')
            cantidades = request.POST.getlist('cantidadrecomendada[]')
            for material_id, cantidad in zip(material_ids, cantidades):
                try:
                    material = Material.objects.get(id=material_id)
                    cantidad_int = int(cantidad)
                    if cantidad_int >= 1:
                        MaterialTarea.objects.create(
                            tarea=tarea,
                            material=material,
                            stockrecomendado=cantidad_int
                        )
                except (Material.DoesNotExist, ValueError):
                    continue
            return redirect('detalle_pedido', pedido_id=tarea.pedido.id)
            
    return render(request, 'detalle_tarea.html', context)


def create_observacion(request, tarea_id):
    tarea = get_object_or_404(Tarea, id=tarea_id)
    context = {'tarea': tarea}
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'observacion_control_calidad':
            tarea = get_object_or_404(Tarea, id=request.POST.get('tarea_id'))
            tipoobservacion = request.POST.get('tipoobservacion')
            obs_data = {
                'tarea': tarea,
                'amortiguador': tarea.amortiguador,
                'tipoobservacion': tipoobservacion,
                'infoobservacion': request.POST.get('infoobservacion'),
                'fechaobservacion': datetime.date.today(),
                'horaobservacion': datetime.datetime.now().time(),
            }
            if tipoobservacion == 'controldiagrama':
                obs_data['valordiagrama'] = request.POST.get('valordiagrama')
            Observacion.objects.create(**obs_data)
            # Después de crear la observación, volvemos al detalle de la tarea
            return redirect('detalle_tarea', tarea_id=tarea.id)

    return render(request, 'create_observacion.html', context)

def listapedidosrevisados(request):
    pedidos = Pedido.objects.filter(estado='revisado')
    return render(request, 'listapedidosrevisados.html', {'pedidos': pedidos})

def historial_amortiguador(request, tarea_id):

    tarea = get_object_or_404(Tarea, id=tarea_id)
    amortiguador = tarea.amortiguador
    observaciones = Observacion.objects.filter(amortiguador=amortiguador).order_by('-fechaobservacion', '-horaobservacion')
    return render(request, 'historial_amortiguador.html', {'amortiguador': amortiguador, 'observaciones': observaciones, 'id_pedido': tarea.pedido.id})

## CUU 1.5 ##
def tareas_en_reparacion(request):
    # Filtrar tareas en reparación, opcionalmente por operario si hay login
    tareas = Tarea.objects.filter(estado='en reparacion')
    context = {'tareas': tareas}
    return render(request, 'tareas_en_reparacion.html', context)

## CUU 1.5 ##
def finalizar_reparacion(request, tarea_id):
    tarea = get_object_or_404(Tarea, id=tarea_id)
    mensaje = None
    if request.method == 'POST':
        orden_trabajo = request.POST.get('orden_trabajo')
        observacion = request.POST.get('observacion')
        # Registrar observación
        Observacion.objects.create(
            tarea=tarea,
            amortiguador=tarea.amortiguador,
            tipoobservacion='fin reparacion',
            infoobservacion=observacion,
            fechaobservacion=datetime.date.today(),
            horaobservacion=datetime.datetime.now().time(),
        )
        # Cambiar estado de la tarea
        tarea.estado = 'terminada'
        tarea.save()
        # Notificar al encargado (crear notificación)
        Notificacion.objects.create(
            tarea=tarea,
            materiales=f"Finalización: Tarea {tarea.id} finalizada. Orden de trabajo: {orden_trabajo}",
            resolved=False
        )
        # Validar si todas las tareas del pedido están terminadas
        pedido = tarea.pedido
        tareas_pedido = Tarea.objects.filter(pedido=pedido)
        if all(t.estado == 'terminada' for t in tareas_pedido):
            pedido.estado = 'terminado'
            pedido.save()
            Notificacion.objects.create(
                tarea=None,
                materiales=f"Finalización: Pedido {pedido.id} finalizado. Todas las tareas terminadas.",
                resolved=False
            )
        return redirect('tareas_en_reparacion')
    return render(request, 'finalizar_reparacion.html', {'tarea': tarea, 'mensaje': mensaje})


## OPERARIOS ##

def eliminar_operarios(request):
    if request.method == "POST":
        ids = request.POST.getlist('selected_ids')  
        if ids:
            Operario.objects.filter(id__in=ids).delete()

    return redirect('estado_operarios') 


def actualizar_operarios(request):
    if request.method == "POST":
        op_id = request.POST.get('id')
        field = request.POST.get('field')
        value = request.POST.get('value', '').strip()

        allowed = {'legajo', 'nombre', 'apellido'}
        if field not in allowed:
            return JsonResponse({'ok': False, 'error': 'Campo no permitido'}, status=400)

        operario = get_object_or_404(Operario, pk=op_id)

        # (Opcional) Validaciones mínimas
        if field in {'nombre', 'apellido'} and not value:
            return JsonResponse({'ok': False, 'error': 'El valor no puede estar vacío'}, status=400)

        setattr(operario, field, value)
        operario.save(update_fields=[field])

        return JsonResponse({'ok': True, 'value': getattr(operario, field)})

def crear_operario(request):
    if request.method == "POST":
        legajo = request.POST.get("legajo")
        nombre = request.POST.get("nombre")
        apellido = request.POST.get("apellido")
        password = request.POST.get("password")
        estado = request.POST.get("estado", "Libre")  # por defecto Libre

        # Crear el nuevo operario en la base de datos
        Operario.objects.create(
            legajo=legajo,
            nombre=nombre,
            apellido=apellido,
            password=password,
            estado=estado
        )

        # Redirigir al listado de operarios
        return redirect("estado_operarios")

    # Si es GET, mostrar el formulario
    return render(request, "crear_operario.html")

def lista_operarios(request):
    query = request.GET.get("q", "")

    operarios_qs = Operario.objects.all()
    if query:
        operarios_qs = operarios_qs.filter(
            Q(nombre__icontains=query) |
            Q(apellido__icontains=query) |
            Q(legajo__icontains=query)
        )
    
    for op in operarios_qs:
        tarea = (
            Tarea.objects
                 .filter(operario=op, estado__iexact="en reparacion")
                 .order_by('-pk')
                 .only('pk')
                 .first()
        )
        op.estado = str(tarea.pk) if tarea else "Libre"
        op.save(update_fields=['estado'])

    
    pendientes_qs = (
        Tarea.objects
             .filter(estado__iexact="pendiente")
             .values('operario_id')
             .annotate(c=Count('id'))
    )
    pendientes_map = {row['operario_id']: row['c'] for row in pendientes_qs}

    
    operarios = list(operarios_qs.values())
    for o in operarios:
        o.pop('password', None)
        o['pendientes_count'] = pendientes_map.get(o['id'], 0)

    return render(request, 'estado_operario.html', {'operarios': operarios})




## CUU 1.6 ##
def pedidos_terminados(request):
    pedidos = Pedido.objects.filter(estado='terminado')
    return render(request, 'pedidos_terminados.html', {'pedidos': pedidos})

## CUU 1.6 ##
def emitir_comprobante(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    tareas = Tarea.objects.filter(pedido=pedido)
    mensaje = None
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'emitir':
            # Generar PDF con reportlab
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer)
            p.setFont("Helvetica-Bold", 16)
            p.drawString(100, 800, f"Comprobante de Pedido #{pedido.id}")
            p.setFont("Helvetica", 12)
            p.drawString(100, 780, f"Cliente: {pedido.cliente.nombre} {pedido.cliente.apellido}")
            p.drawString(100, 760, f"DNI: {pedido.cliente.dni}")
            p.drawString(100, 740, f"Fecha ingreso: {pedido.fechaingreso}")
            p.drawString(100, 720, f"Estado: {pedido.estado}")
            y = 700
            p.drawString(100, y, "Tareas:")
            for tarea in tareas:
                y -= 20
                p.drawString(120, y, f"Amortiguador: {tarea.amortiguador.nroSerieamortiguador} - Estado: {tarea.estado} - Operario: {tarea.operario.nombre} {tarea.operario.apellido}")
            p.showPage()
            p.save()
            buffer.seek(0)
            # Cambiar estado del pedido
            pedido.estado = 'listo para retirar'
            pedido.save()
            return FileResponse(buffer, as_attachment=True, filename=f'comprobante_pedido_{pedido.id}.pdf')
        elif accion == 'enviar':
            # Generar PDF
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer)
            p.setFont("Helvetica-Bold", 16)
            p.drawString(100, 800, f"Comprobante de Pedido #{pedido.id}")
            p.setFont("Helvetica", 12)
            p.drawString(100, 780, f"Cliente: {pedido.cliente.nombre} {pedido.cliente.apellido}")
            p.drawString(100, 760, f"DNI: {pedido.cliente.dni}")
            p.drawString(100, 740, f"Fecha ingreso: {pedido.fechaingreso}")
            p.drawString(100, 720, f"Estado: {pedido.estado}")
            y = 700
            p.drawString(100, y, "Tareas:")
            for tarea in tareas:
                y -= 20
                p.drawString(120, y, f"Amortiguador: {tarea.amortiguador.nroSerieamortiguador} - Estado: {tarea.estado} - Operario: {tarea.operario.nombre} {tarea.operario.apellido}")
            p.showPage()
            p.save()
            buffer.seek(0)
            # Enviar por email
            email = EmailMessage(
                subject=f'Comprobante de Pedido #{pedido.id}',
                body='Adjunto comprobante de su pedido. Puede retirar el producto.',
                to=[pedido.cliente.correo]
            )
            email.attach(f'comprobante_pedido_{pedido.id}.pdf', buffer.getvalue(), 'application/pdf')
            email.send()
            pedido.estado = 'listo para retirar'
            pedido.save()
            mensaje = 'Comprobante enviado al cliente.'
    return render(request, 'comprobante_pedido.html', {'pedido': pedido, 'tareas': tareas, 'mensaje': mensaje})


## Materiales ##
def materiales_list(request):
    materiales = Material.objects.all()
    
    for m in materiales:
        m.stockRiesgo = int(m.stockMinimo * 1.1)
    
    return render(request, 'materiales/material_list.html', {'materials': materiales})   

def material_detail(request, pk):
    material = get_object_or_404(Material, pk=pk)
    return render(request, 'materiales/material_detail.html', {'material': material})

def material_create(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('material_list')
    else:
        form = MaterialForm()
    return render(request, 'materiales/material_form.html', {'form': form})

def material_update(request, pk):
    material = get_object_or_404(Material, pk=pk)
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            form.save()
            return redirect('material_list')
    else:
        form = MaterialForm(instance=material)
    return render(request, 'materiales/material_form.html', {'form': form})

def material_delete(request, pk):
    material = get_object_or_404(Material, pk=pk)
    if request.method == 'POST':
        material.delete()
        return redirect('material_list')
    return render(request, 'materiales/material_confirm_delete.html', {'material': material})

def stock_update(request, pk):
    material = get_object_or_404(Material, pk=pk)

    if request.method == 'POST':
        form = StockUpdateForm(request.POST, material=material)
        if form.is_valid():
            stock_ingresado = form.cleaned_data['stock_ingresado']
            proveedor = form.cleaned_data['proveedor']
            fecha = form.cleaned_data['fecha']
            observacion = form.cleaned_data['observacion']

            MovimientoStock.objects.create(
                material=material,
                fecha=fecha,
                cantidad=stock_ingresado,
                proveedor=proveedor,
                observacion=observacion
            )

            material.stockActual += stock_ingresado
            material.save()

            return redirect('material_list')
    else:
        form = StockUpdateForm(material=material)

    return render(request, 'materiales/stock_update.html', {'form': form, 'material': material})

def movimientos_list(request, pk):
    material = get_object_or_404(Material, pk=pk)
    movimientos = MovimientoStock.objects.filter(material=material).order_by('-fecha')

    return render(request, 'movimientos_list.html', {
        'material': material,
        'movimientos': movimientos
    })

def buscar_pedido_por_dni(request):
    pedido = None
    cliente = None
    error = None

    if request.method == 'POST':
        form = BuscarPedidoForm(request.POST)
        if form.is_valid():
            dni = form.cleaned_data['dni']
            try:
                cliente = Cliente.objects.get(dni=dni)
                pedido = Pedido.objects.filter(cliente=cliente, estado='Listo para retirar').first()
                if not pedido:
                    error = "No hay pedidos listos para retirar para este cliente."
            except Cliente.DoesNotExist:
                error = "No se encontró un cliente con ese DNI."
    else:
        form = BuscarPedidoForm()

    return render(request, 'buscar_pedido.html', {
        'form': form,
        'pedido': pedido,
        'cliente': cliente,
        'error': error
    })


def cerrar_pedido(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, estado='Listo para retirar')

    if request.method == 'POST':
        form = CerrarPedidoForm(request.POST)
        if form.is_valid():
            pedido.estado = 'Retirado'
            pedido.fechaSalidaReal = timezone.now().date()
            pedido.save()
            return render(request, 'cerrar_exito.html', {'pedido': pedido})
    else:
        form = CerrarPedidoForm()

    return render(request, 'materiales/cerrar_pedido.html', {'form': form, 'pedido': pedido})



def material_reporte(request):
    tipo = request.GET.get("tipo", "faltante").lower()
    export = request.GET.get("export", "") == "excel"

    context = {"tipo": tipo, "titulo": "", "columns": [], "rows": []}

    def nz(v): 
        return v if v is not None else 0

    # === 1) FALTANTE ===
    if tipo == "faltante":
        qs = Material.objects.filter(stockActual__lt=F("stockMinimo")).values(
            "id", "nombre", "tipo", "unidad", "stockActual", "stockMinimo", "stockreservado"
        )
        rows = []
        for m in qs:
            reservado = nz(m["stockreservado"])
            disponible = max(nz(m["stockActual"]) - reservado, 0)
            faltante = max(nz(m["stockMinimo"]) - nz(m["stockActual"]), 0)
            rows.append({
                "ID": m["id"],
                "Material": m["nombre"],
                "Tipo": m["tipo"],
                "Unidad": m["unidad"],
                "Stock actual": nz(m["stockActual"]),
                "Stock mínimo": nz(m["stockMinimo"]),
                "Reservado": reservado,
                "Disponible": disponible,
                "Faltante": faltante,
            })
        context["titulo"] = "Reporte de stock faltante (general)"
        context["columns"] = list(rows[0].keys()) if rows else []

    # === 2) URGENTE ===
    elif tipo == "urgente":
        notifs = Notificacion.objects.all().values("materiales")
        agregados = defaultdict(lambda: {"Material": None, "Requerido total": 0, "Faltante total": 0, "Notificaciones": 0})
        for n in notifs:
            raw = n.get("materiales") or "[]"
            try:
                data = json.loads(raw)
            except Exception:
                data = []
            for item in data:
                mat_nombre = item.get("name") or item.get("material") or "Desconocido"
                required = nz(item.get("required") or item.get("requerido"))
                available = nz(item.get("available") or item.get("disponible"))
                faltan = max(required - available, 0)
                agg = agregados[mat_nombre]
                agg["Material"] = mat_nombre
                agg["Requerido total"] += required
                agg["Faltante total"] += faltan
                agg["Notificaciones"] += 1
        rows = sorted(agregados.values(), key=lambda r: r["Faltante total"], reverse=True)
        context["titulo"] = "Reporte de stock urgente (vinculado a notificaciones)"
        context["columns"] = ["Material", "Requerido total", "Faltante total", "Notificaciones"]

    # === 3) TODOS ===
    else:
        qs = Material.objects.all().values(
            "id", "nombre", "tipo", "unidad", "stockActual", "stockMinimo", "stockreservado"
        )
        rows = []
        for m in qs:
            reservado = nz(m["stockreservado"])
            disponible = max(nz(m["stockActual"]) - reservado, 0)
            rows.append({
                "ID": m["id"],
                "Material": m["nombre"],
                "Tipo": m["tipo"],
                "Unidad": m["unidad"],
                "Stock actual": nz(m["stockActual"]),
                "Stock mínimo": nz(m["stockMinimo"]),
                "Reservado": reservado,
                "Disponible": disponible,
            })
        context["titulo"] = "Reporte de todo el stock"
        context["columns"] = list(rows[0].keys()) if rows else []

    context["rows"] = rows

    # === Exportar a Excel ===
    if export:
        wb = Workbook()
        ws = wb.active
        ws.title = "Reporte"
        if context["columns"]:
            ws.append(context["columns"])
            for r in rows:
                ws.append([r.get(c, "") for c in context["columns"]])
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"reporte_stock_{tipo}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    return render(request, "materiales/material_reporte.html", context)


