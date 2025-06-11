from django.urls import path
from . import views

app_name = 'data_monitoring'

urlpatterns = [
    path('input_drymix/', views.input_drymix, name='input_drymix'),
    path('input_dryline/', views.input_dryline, name='input_dryline'),
    path('input_rp/', views.input_rp, name='input_rp'),
    path('input_inspection/', views.input_inspection, name='input_inspection'),
    path('input_printing/', views.input_printing, name='input_printing'),

    path('aging_room/', views.aging_room, name='aging_room'),
    path('create_lot_no/', views.create_lot_no, name='create_lot_no'),
    
    path('order_search/', views.order_search, name='order_search'),
    path('dryplan/', views.dryplan, name='dryplan'),
    path('drymix/', views.drymix, name='drymix'),
    path('dryline/', views.dryline, name='dryline'),
    path('delamination/', views.delamination, name='delamination'),
    path('inspection/', views.inspection, name='inspection'),
    path('inspection_waitlist/', views.inspection_waitlist, name='inspection_waitlist'),
    path('printing_waitlist/', views.printing_waitlist, name='printing_waitlist'),
    path('debug/export-counts/', views.debug_export_counts, name='debug_export_counts'),
]