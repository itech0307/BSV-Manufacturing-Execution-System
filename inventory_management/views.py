from django.shortcuts import render, redirect
from .models import Category, Supplier, RawMaterial

def view_raw_materials(request):
    raw_materials = RawMaterial.objects.all().select_related('supplier', 'category')
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()
    return render(request, 'inventory_management/view_raw_materials.html', {
        'raw_materials': raw_materials,
        'categories': categories,
        'suppliers': suppliers
    })

def add_category(request):
    if request.method == 'POST':
        category_name = request.POST.get('category_name')
        description = request.POST.get('description')
        Category.objects.create(category_name=category_name, description=description)
        return redirect('inventory_management:view_raw_materials')

def add_supplier(request):
    if request.method == 'POST':
        supplier_name = request.POST.get('supplier_name')
        description = request.POST.get('description')
        Supplier.objects.create(supplier_name=supplier_name, description=description)
        return redirect('inventory_management:view_raw_materials')

def add_rawmaterial(request):
    if request.method == 'POST':
        material_name = request.POST.get('material_name')
        description = request.POST.get('description')
        supplier_id = request.POST.get('supplier')
        category_id = request.POST.get('category')
        
        supplier = Supplier.objects.get(id=supplier_id)
        category = Category.objects.get(id=category_id)
        
        RawMaterial.objects.create(
            material_name=material_name,
            description=description,
            supplier=supplier,
            category=category
        )
        return redirect('inventory_management:view_raw_materials')