from django.contrib import auth
from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    # ex: /venter/
    path('', TemplateView.as_view(template_name='Venter/home.html'), name='home'),
    # ex: /venter/home/
    path('home/', TemplateView.as_view(template_name='Venter/home.html'), name='home'),
    # ex: /venter/logout/
    path('logout/', auth.views.LogoutView.as_view(template_name="Venter/login.html"), name='logout'),
    # ex: /venter/update_profile/5/
    path('update_profile/<int:pk>', views.UpdateProfileView.as_view(), name='update_profile'),
    # ex: /venter/register_employee/
    path('register_employee/', views.RegisterEmployeeView.as_view(), name='register_employee'),
    # ex: /venter/login/
    path('login/', auth.views.LoginView.as_view(template_name="Venter/login.html"), name='login'),
    # ex: /venter/upload_file/
    path('upload_file/', views.upload_file, name='upload_file'),
    # ex: /venter/delete_file/5/
    path('delete_file/<int:pk>', views.FileDeleteView.as_view(), name='delete_file'),
    # ex: /venter/category_list/civis/
    path('category_list/', views.CategoryListView.as_view(), name='category_list'),
    # ex: /venter/dashboard/
    path('dashboard/', views.FileListView.as_view(), name='dashboard'),
    # ex: /venter/contact_us/
    path('contact_us/', views.contact_us, name='contact_us'),
    # ex: /venter/predict_result/5/
    path('predict_result/<int:pk>', views.predict_result, name='predict_result'),
    # ex: /venter/domain_contents/
    path('domain_contents/', views.domain_contents, name='domain_contents'),
    # ex: /venter/predict_csv/5/
    path('predict_csv/<int:pk>', views.predict_csv, name='predict_csv'),
    # ex: /venter/download_table/5/
    path('download_table/<int:pk>', views.download_table, name='download_table'),
    # ex: password_reset/
    path('password_reset/',
         auth.views.PasswordResetView.as_view(template_name='Venter/password_reset_form.html'),
         name='password_reset'),
    # ex: password_reset_done/
    path('password_reset_done/',
         auth.views.PasswordResetDoneView.as_view(template_name='Venter/password_reset_done.html'),
         name='password_reset_done'),
    # ex: reset/<uidb64>/<token>/
    path('reset/<uidb64>/<token>/',
         auth.views.PasswordResetConfirmView.as_view(template_name='Venter/password_reset_confirm.html'),
         name='password_reset_confirm'),
    # ex: password_reset_complete/
    path('password_reset_complete/',
         auth.views.PasswordResetCompleteView.as_view(template_name='Venter/password_reset_complete.html'),
         name='password_reset_complete'),
]
