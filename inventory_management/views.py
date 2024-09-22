from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden
from django.contrib import messages
from .models import Category, Supplier, RawMaterial

def view_raw_materials(request):
    raw_materials = RawMaterial.objects.all().select_related('supplier', 'category')
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()
    is_superuser = request.user.is_superuser
    return render(request, 'inventory_management/view_raw_materials.html', {
        'raw_materials': raw_materials,
        'categories': categories,
        'suppliers': suppliers,
        'is_superuser': is_superuser
    })

@user_passes_test(lambda u: u.is_superuser)
def add_category(request):
    if request.method == 'POST':
        category_name = request.POST.get('category_name')
        description = request.POST.get('description')
        if Category.objects.filter(category_name__iexact=category_name).exists():
            messages.error(request, f"Category '{category_name}' already exists.")
        else:
            Category.objects.create(category_name=category_name, description=description)
            messages.success(request, f"Category '{category_name}' has been added successfully.")
        return redirect('inventory_management:view_raw_materials')
    return HttpResponseForbidden("You don't have permission to add categories.")

@user_passes_test(lambda u: u.is_superuser)
def add_supplier(request):
    if request.method == 'POST':
        supplier_name = request.POST.get('supplier_name')
        description = request.POST.get('description')
        if Supplier.objects.filter(supplier_name__iexact=supplier_name).exists():
            messages.error(request, f"Supplier '{supplier_name}' already exists.")
        else:
            Supplier.objects.create(supplier_name=supplier_name, description=description)
            messages.success(request, f"Supplier '{supplier_name}' has been added successfully.")
        return redirect('inventory_management:view_raw_materials')
    return HttpResponseForbidden("You don't have permission to add suppliers.")

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
        messages.success(request, f"Raw material '{material_name}' has been added successfully.")
        return redirect('inventory_management:view_raw_materials')