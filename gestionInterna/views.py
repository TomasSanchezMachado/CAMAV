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
from django.contrib.auth.decorators import login_required
from .decorators import role_required
from django.contrib.auth.models import User
from django.template.loader import render_to_string

def material_create_ajax(request):
    """AJAX endpoint: GET -> return form fragment HTML; POST -> create material and return JSON with id/name."""
    if request.method == 'GET':
        form = MaterialForm(initial={'nombre': request.GET.get('name', '')})
        html = render_to_string('materiales/material_form_fragment.html', {'form': form}, request=request)
        return JsonResponse({'ok': True, 'html': html})

    # POST
    form = MaterialForm(request.POST)
    if form.is_valid():
        material = form.save()
        return JsonResponse({'ok': True, 'id': material.id, 'nombre': material.nombre})
    else:
        # return fragment with errors to re-render in modal
        html = render_to_string('materiales/material_form_fragment.html', {'form': form}, request=request)
        return JsonResponse({'ok': False, 'html': html, 'errors': form.errors}, status=400)

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

@role_required(['encargado'])
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
    operarios = Operario.objects.filter(role='operario')
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


@login_required
@role_required(['operario'])
def paneltareas(request):
    operarios = Operario.objects.filter(role='operario')
    context = { 'operarios': operarios }
    user_operario = getattr(request.user, 'operario', None)
    if user_operario:
        context['operario'] = user_operario
    if request.method == 'POST':
        accion = request.POST.get('accion')
        estadoselect = request.POST.get('estado')
        context['estadoselect'] = estadoselect
        priority = request.POST.get('prioridad')
        context['priority'] = priority
        if accion == 'elegiroperario':
            operario_id = request.POST.get('operario')

            if operario_id:
                operario = get_object_or_404(Operario, id=operario_id)
            else:
                operario = user_operario
            if not operario:
                context['error'] = 'No hay un operario asignado al usuario. Selecciona uno o contacta al administrador.'
                return render(request, 'paneltareas.html', context)
            tareas = Tarea.objects.filter(operario=operario)
            if estadoselect:
                tareas = tareas.filter(estado=estadoselect)
            if priority:
                tareas = tareas.filter(prioridad=priority)
            context['tareas'] = tareas
            context['operario'] = operario

            if estadoselect:
                context['titulo_tareas'] = f"Tareas con estado '{estadoselect}'"
            else:
                context['titulo_tareas'] = "Tareas Pendientes"

    if request.method == 'GET' and user_operario:
        tareas = Tarea.objects.filter(operario=user_operario, estado='por reparar')
        context['tareas'] = tareas
        context['titulo_tareas'] = "Tareas con estado 'por reparar'"
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
    # Check availability for materials assigned to this task
    missing_materials = []
    for mt in materialxtarea:
        mat = mt.material
        # available stock = stockActual - stockreservado (treat None as 0)
        available = int(mat.stockActual or 0) - int(mat.stockreservado or 0)
        required = int(mt.stockrecomendado or 0)
        if available < required:
            missing_materials.append({
                'id': mat.id,
                'nombre': mat.nombre,
                'required': required,
                'available': available,
            })
    can_reserve = len(missing_materials) == 0
    context['can_reserve'] = can_reserve
    context['missing_materials'] = missing_materials
    # If there are missing materials, create a Notificacion record (if not already unresolved)
    if missing_materials:
        exists = Notificacion.objects.filter(tarea=tarea, resolved=False).exists()
        if not exists:
            try:
                Notificacion.objects.create(
                    tarea=tarea,
                    materiales=json.dumps(missing_materials, ensure_ascii=False),
                )
            except Exception:
                # avoid crashing the view if notification creation fails; log later if needed
                pass
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
            # Re-evaluate availability before reserving to avoid race conditions
            still_missing = []
            for mt in materialxtarea:
                mat = mt.material
                available = int(mat.stockActual or 0) - int(mat.stockreservado or 0)
                required = int(mt.stockrecomendado or 0)
                if available < required:
                    still_missing.append({
                        'id': mat.id,
                        'nombre': mat.nombre,
                        'required': required,
                        'available': available,
                    })
            if still_missing:
                # create or update notification and do not perform reservation
                exists = Notificacion.objects.filter(tarea=tarea, resolved=False).exists()
                if not exists:
                    try:
                        Notificacion.objects.create(
                            tarea=tarea,
                            materiales=json.dumps(still_missing, ensure_ascii=False),
                        )
                    except Exception:
                        pass
                # show message and redirect back to task detail
                messages.error(request, 'No se puede reservar: falta stock de algunos materiales. Se ha creado una notificación para el encargado.')
                return redirect('detalle_tarea', tarea_id=tarea.id)
            # perform reservation
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

            return redirect('detalle_tarea', tarea_id=tarea.id)

    return render(request, 'create_observacion.html', context)

@role_required(['encargado'])
def listapedidosrevisados(request):
    pedidos = Pedido.objects.filter(estado='revisado')
    return render(request, 'listapedidosrevisados.html', {'pedidos': pedidos})

def historial_amortiguador(request, tarea_id=None, amortiguador_id=None):
    tarea_pk = tarea_id or amortiguador_id
    tarea = get_object_or_404(Tarea, id=tarea_pk)
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

        pedido = tarea.pedido
        tareas_pedido = Tarea.objects.filter(pedido=pedido)
        if all(t.estado == 'terminada' for t in tareas_pedido):
            pedido.estado = 'terminado'
            pedido.save()

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

def crear_operario(request, pk=None):
    """Create or edit an Operario. If pk is provided (via URL), show edit form.
    The form posts back to the same URL and includes a hidden 'op_id' when editing.
    """
    # Support create and edit using the same form
    if request.method == "POST":
        op_id = request.POST.get('op_id')
        legajo = request.POST.get("legajo")
        nombre = request.POST.get("nombre")
        apellido = request.POST.get("apellido")
        password = request.POST.get("password")
        estado = request.POST.get("estado", "Libre")  # por defecto Libre

        if op_id:
            # editar operario existente
            operario = get_object_or_404(Operario, pk=op_id)
            operario.legajo = legajo
            operario.nombre = nombre
            operario.apellido = apellido
            operario.estado = estado
            # Si se envía password, actualizar también el User
            if password:
                # actualizar campo password del usuario de Django
                if operario.user:
                    operario.user.set_password(password)
                    operario.user.save()
                operario.password = password
            operario.save()
        else:
            # crear nuevo operario y usuario asociado
            user = User.objects.create_user(
                username=legajo,
                first_name=nombre,
                last_name=apellido,
                password=password
            )
            Operario.objects.create(
                legajo=legajo,
                nombre=nombre,
                apellido=apellido,
                password=password,
                estado=estado,
                user=user
            )

        return redirect("estado_operarios")

    # Si es GET, mostrar el formulario. If pk is provided from the URL use it;
    # otherwise, accept ?id= or ?op_id= for backwards compatibility.
    op_id = pk or request.GET.get('id') or request.GET.get('op_id')
    context = {}
    if op_id:
        operario = get_object_or_404(Operario, pk=op_id)
        context['operario'] = operario
    return render(request, "crear_operario.html", context)

def lista_operarios(request):
    query = request.GET.get("q", "")

    operarios_qs = Operario.objects.filter(role='operario')
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
    # support creating with a 'next' parameter to return to a caller (e.g., ficha form)
    next_url = request.GET.get('next') or request.POST.get('next')
    prefill_name = request.GET.get('name')
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save()
            if next_url:
                # append added_material_id to the next URL
                sep = '&' if '?' in next_url else '?'
                return redirect(f"{next_url}{sep}added_material_id={material.id}")
            return redirect('material_list')
    else:
        if prefill_name:
            form = MaterialForm(initial={'nombre': prefill_name})
        else:
            form = MaterialForm()
    return render(request, 'materiales/material_form.html', {'form': form, 'next': next_url})

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

    return render(request, 'cerrar_pedido.html', {'form': form, 'pedido': pedido})



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
        # Use the new Notificacion format: one Notificacion per task with JSON 'materiales'.
        # Include fecha_solicitud in the report.
        notifs = Notificacion.objects.filter(resolved=False).values('id', 'tarea_id', 'materiales', 'fecha_solicitud')
        rows = []
        for n in notifs:
            tarea_ref = n.get('tarea_id')
            raw = n.get('materiales') or ''
            fecha = n.get('fecha_solicitud')
            fecha_text = fecha.strftime('%Y-%m-%d %H:%M:%S') if fecha else ''
            materiales_text = ''
            try:
                data = json.loads(raw)
                parts = []
                for item in data:
                    name = item.get('nombre') or item.get('name') or item.get('material') or 'Desconocido'
                    required = nz(item.get('required') or item.get('requerido') or 0)
                    available = nz(item.get('available') or item.get('disponible') or 0)
                    parts.append(f"nombre del material :{name} (requerido: {required}, disponible: {available})")
                materiales_text = '; '.join(parts)
            except Exception:
                # If not JSON, keep raw text
                materiales_text = raw
            rows.append({
                'Tarea': tarea_ref if tarea_ref is not None else '-',
                'Fecha': fecha_text,
                'Materiales': materiales_text,
            })
        context["titulo"] = "Notificaciones pendientes por tarea"
        context["columns"] = ["Tarea", "Fecha", "Materiales"]

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


### CRUD para Fichaamortiguador (integrado)
def fichaamortiguador_list(request):
    q = request.GET.get('q', '').strip()
    fichas_qs = Fichaamortiguador.objects.all()
    if q:
        fichas_qs = fichas_qs.filter(
            Q(nombregenerico__icontains=q) | Q(nroseriegenerico__icontains=q)
        )
    return render(request, 'fichaamortiguador_crud.html', {'fichas': fichas_qs, 'query': q})


def fichaamortiguador_create(request):
    if request.method == 'POST':
        nombregenerico = request.POST.get('nombregenerico')
        nroseriegenerico = request.POST.get('nroseriegenerico')
        valor_minimo = request.POST.get('valor_minimo') or 0
        valor_maximo = request.POST.get('valor_maximo') or 0
        ficha = Fichaamortiguador.objects.create(
            nombregenerico=nombregenerico,
            nroseriegenerico=nroseriegenerico,
            valor_minimo=valor_minimo,
            valor_maximo=valor_maximo
        )

        # Procesar materiales enviados como listas: material_name[] y material_cantidad[]
        # Accept either material_id (select) or material_name (free text) lists
        material_ids = request.POST.getlist('material_id')
        material_names = request.POST.getlist('material_name')
        cantidades = request.POST.getlist('material_cantidad')
        # If material_id provided, prefer it
        if material_ids and any(mid for mid in material_ids):
            for mid, cantidad in zip(material_ids, cantidades):
                if not mid:
                    # fallback to name in same position
                    continue
                try:
                    material = Material.objects.get(pk=int(mid))
                except Exception:
                    material = None
                try:
                    cantidad_val = int(cantidad) if cantidad not in (None, '') else 0
                except Exception:
                    cantidad_val = 0
                if not material:
                    continue
                MaterialFichaAmortiguador.objects.create(
                    material=material,
                    fichaamortiguador=ficha,
                    cantidadrecomendada=cantidad_val,
                )
        else:
            for name, cantidad in zip(material_names, cantidades):
                name = (name or '').strip()
                if not name:
                    continue
                try:
                    cantidad_val = int(cantidad) if cantidad not in (None, '') else 0
                except Exception:
                    cantidad_val = 0

                material = Material.objects.filter(nombre__iexact=name).first()
                if not material:
                    material = Material.objects.create(nombre=name, tipo='', unidad='unidad')

                MaterialFichaAmortiguador.objects.create(
                    material=material,
                    fichaamortiguador=ficha,
                    cantidadrecomendada=cantidad_val,
                )

        return redirect('fichaamortiguador_list')
    # pasar lista de materiales disponibles para el select (como dicts serializables)
    materials_all = list(Material.objects.values('id', 'nombre'))
    # Si venimos del formulario de creación de material, podemos recibir added_material_id
    added_id = request.GET.get('added_material_id')
    materials_prefill = []
    if added_id:
        try:
            m = Material.objects.get(pk=added_id)
            materials_prefill.append({'nombre': m.nombre, 'cantidad': ''})
        except Material.DoesNotExist:
            pass
    return render(request, 'fichaamortiguador_form.html', {'ficha': None, 'materials': materials_prefill, 'materials_all': materials_all})


def fichaamortiguador_edit(request, pk):
    ficha = get_object_or_404(Fichaamortiguador, pk=pk)
    if request.method == 'POST':
        ficha.nombregenerico = request.POST.get('nombregenerico')
        ficha.nroseriegenerico = request.POST.get('nroseriegenerico')
        ficha.valor_minimo = request.POST.get('valor_minimo') or 0
        ficha.valor_maximo = request.POST.get('valor_maximo') or 0
        ficha.save()

        # Actualizar relaciones de materiales: borramos las anteriores y creamos nuevas
        MaterialFichaAmortiguador.objects.filter(fichaamortiguador=ficha).delete()
        # Accept either material_id (select) or material_name (free text) lists
        material_ids = request.POST.getlist('material_id')
        material_names = request.POST.getlist('material_name')
        cantidades = request.POST.getlist('material_cantidad')
        # If material_id provided, prefer it
        if material_ids and any(mid for mid in material_ids):
            for mid, cantidad in zip(material_ids, cantidades):
                if not mid:
                    # fallback to name in same position
                    continue
                try:
                    material = Material.objects.get(pk=int(mid))
                except Exception:
                    material = None
                try:
                    cantidad_val = int(cantidad) if cantidad not in (None, '') else 0
                except Exception:
                    cantidad_val = 0
                if not material:
                    continue
                MaterialFichaAmortiguador.objects.create(
                    material=material,
                    fichaamortiguador=ficha,
                    cantidadrecomendada=cantidad_val,
                )
        else:
            for name, cantidad in zip(material_names, cantidades):
                name = (name or '').strip()
                if not name:
                    continue
                try:
                    cantidad_val = int(cantidad) if cantidad not in (None, '') else 0
                except Exception:
                    cantidad_val = 0

                material = Material.objects.filter(nombre__iexact=name).first()
                if not material:
                    material = Material.objects.create(nombre=name, tipo='', unidad='unidad')

                MaterialFichaAmortiguador.objects.create(
                    material=material,
                    fichaamortiguador=ficha,
                    cantidadrecomendada=cantidad_val,
                )

        return redirect('fichaamortiguador_list')

    # preparar materiales existentes para prellenar el formulario
    materials_qs = MaterialFichaAmortiguador.objects.filter(fichaamortiguador=ficha).select_related('material')
    materials = [{'id': m.material.id, 'nombre': m.material.nombre, 'cantidad': m.cantidadrecomendada} for m in materials_qs]
    # agregar material creado recientemente si viene en query params
    added_id = request.GET.get('added_material_id')
    if added_id:
        try:
            m = Material.objects.get(pk=added_id)
            materials.append({'id': m.id, 'nombre': m.nombre, 'cantidad': ''})
        except Material.DoesNotExist:
            pass
    materials_all = list(Material.objects.values('id', 'nombre'))
    return render(request, 'fichaamortiguador_form.html', {'ficha': ficha, 'materials': materials, 'materials_all': materials_all})


def fichaamortiguador_delete(request, pk):
    ficha = get_object_or_404(Fichaamortiguador, pk=pk)
    if request.method == 'POST':
        ficha.delete()
        return redirect('fichaamortiguador_list')
    return render(request, 'fichaamortiguador_confirm_delete.html', {'ficha': ficha})


### CRUD para Cliente (integrado)
def cliente_list(request):
    q = request.GET.get('q', '').strip()
    clientes_qs = Cliente.objects.all()
    if q:
        clientes_qs = clientes_qs.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(dni__icontains=q)
        )
    return render(request, 'cliente_crud.html', {'clientes': clientes_qs, 'query': q})


def cliente_create(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        dni = request.POST.get('dni')
        telefono = request.POST.get('telefono')
        correo = request.POST.get('correo')
        Cliente.objects.create(
            nombre=nombre,
            apellido=apellido,
            dni=dni,
            telefono=telefono,
            correo=correo
        )
        return redirect('cliente_list')
    return render(request, 'cliente_form.html', {'cliente': None})


def cliente_edit(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.nombre = request.POST.get('nombre')
        cliente.apellido = request.POST.get('apellido')
        cliente.dni = request.POST.get('dni')
        cliente.telefono = request.POST.get('telefono')
        cliente.correo = request.POST.get('correo')
        cliente.save()
        return redirect('cliente_list')
    return render(request, 'cliente_form.html', {'cliente': cliente})


def cliente_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.delete()
        return redirect('cliente_list')
    return render(request, 'cliente_confirm_delete.html', {'cliente': cliente})


def cliente_view(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    pedidos = Pedido.objects.filter(cliente=cliente)
    # Renderizamos la misma plantilla de listado pero pasamos los pedidos del cliente
    clientes = Cliente.objects.all()
    return render(request, 'cliente_crud.html', {'clientes': clientes, 'cliente_pedidos': pedidos, 'cliente': cliente})


