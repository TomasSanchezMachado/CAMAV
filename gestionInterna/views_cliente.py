from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import Cliente, Pedido

# Listar clientes
def cliente_list(request):
    clientes = Cliente.objects.all()
    return render(request, 'cliente_crud.html', {'clientes': clientes})

# Crear cliente
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
    return render(request, 'cliente_form.html')

# Editar cliente
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

# Eliminar cliente
def cliente_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.delete()
        return redirect('cliente_list')
    return render(request, 'cliente_confirm_delete.html', {'cliente': cliente})

# Ver cliente y sus pedidos
def cliente_view(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    pedidos = Pedido.objects.filter(cliente=cliente)
    return render(request, 'cliente_crud.html', {'cliente': cliente, 'cliente_pedidos': pedidos})