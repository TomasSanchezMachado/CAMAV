from django import forms
from .models import Material, Pedido, MovimientoStock

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['nombre', 'tipo', 'unidad', 'stockActual', 'stockMinimo', 'stockreservado']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control my-2',  # estilo Bootstrap
                'placeholder': field.label     # usa el label como placeholder
            })

class StockUpdateForm(forms.ModelForm):
    stock_ingresado = forms.IntegerField(label="Stock ingresado", min_value=1)
    stock_actual = forms.IntegerField(label="Stock actual", required=False, disabled=True)

    class Meta:
        model = MovimientoStock
        fields = ['fecha', 'proveedor', 'stock_ingresado', 'observacion']

    def __init__(self, *args, **kwargs):
        material = kwargs.pop('material', None)
        super().__init__(*args, **kwargs)
        if material:
            self.fields['stock_actual'].initial = material.stockActual

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control my-2',  # estilo Bootstrap
                'placeholder': field.label     # usa el label como placeholder
            })


class StockUpdateForm_not_in_use(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['stockActual']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control my-2',  # estilo Bootstrap
                'placeholder': field.label     # usa el label como placeholder
            })

class BuscarPedidoForm(forms.Form):
    dni = forms.CharField(label="DNI del cliente", max_length=10)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control my-2',  # estilo Bootstrap
                'placeholder': field.label     # usa el label como placeholder
            })

class CerrarPedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = []
    confirmar = forms.BooleanField(label="Confirmar retiro del pedido", required=True)

"""     def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control my-2',  # estilo Bootstrap
                'placeholder': field.label     # usa el label como placeholder
            }) """
