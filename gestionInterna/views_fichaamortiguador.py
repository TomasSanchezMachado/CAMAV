from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import Fichaamortiguador

# Listar fichas de amortiguador
def fichaamortiguador_list(request):
    fichas = Fichaamortiguador.objects.all()
    return render(request, 'fichaamortiguador_crud.html', {'fichas': fichas})

# Crear ficha de amortiguador
def fichaamortiguador_create(request):
    if request.method == 'POST':
        nombregenerico = request.POST.get('nombregenerico')
        nroseriegenerico = request.POST.get('nroseriegenerico')
        valor_minimo = request.POST.get('valor_minimo')
        valor_maximo = request.POST.get('valor_maximo')
        Fichaamortiguador.objects.create(
            nombregenerico=nombregenerico,
            nroseriegenerico=nroseriegenerico,
            valor_minimo=valor_minimo,
            valor_maximo=valor_maximo
        )
        return redirect('fichaamortiguador_list')
    return render(request, 'fichaamortiguador_form.html')

# Editar ficha de amortiguador
def fichaamortiguador_edit(request, pk):
    ficha = get_object_or_404(Fichaamortiguador, pk=pk)
    if request.method == 'POST':
        ficha.nombregenerico = request.POST.get('nombregenerico')
        ficha.nroseriegenerico = request.POST.get('nroseriegenerico')
        ficha.valor_minimo = request.POST.get('valor_minimo')
        ficha.valor_maximo = request.POST.get('valor_maximo')
        ficha.save()
        return redirect('fichaamortiguador_list')
    return render(request, 'fichaamortiguador_form.html', {'ficha': ficha})

# Eliminar ficha de amortiguador
def fichaamortiguador_delete(request, pk):
    ficha = get_object_or_404(Fichaamortiguador, pk=pk)
    if request.method == 'POST':
        ficha.delete()
        return redirect('fichaamortiguador_list')
    return render(request, 'fichaamortiguador_confirm_delete.html', {'ficha': ficha})