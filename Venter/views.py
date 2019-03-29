import datetime
import json
import os
import jsonpickle
import pandas as pd
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Permission, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import mail_admins
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

# import Venter.upload_to_google_drive
from Backend.settings import MEDIA_ROOT
from Venter.forms import ContactForm, CSVForm, ExcelForm, ProfileForm, UserForm
from Venter.models import Category, File, Profile

from .ML_model.Civis.modeldriver import SimilarityMapping
from .ML_model.ICMC.model.ClassificationService import ClassificationService

@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def upload_file(request):
    """
    View logic for uploading CSV file by a logged in user.

    For POST request-------
        1) The POST data, uploaded csv file and a request parameter are being sent to CSVForm as arguments
        2) If form.is_valid() returns true, the user is assigned to the uploaded_by field
        3) file_form is saved and Form instance is initialized again (file_form = CSVForm(request=request)),
           for user to upload another file after successfully uploading the previous file
    For GET request-------
        The file_form is rendered in the template
    """

    if str(request.user.profile.organisation_name) == 'CIVIS':
        excel_form = ExcelForm(request=request)
        if request.method == 'POST':
            excel_form = ExcelForm(
                request.POST, request.FILES, request=request)
            if excel_form.is_valid():
                file_uploaded = excel_form.save(commit=False)
                file_uploaded.uploaded_by = request.user.profile
                file_uploaded.save()
                excel_form = ExcelForm(request=request)
                return render(request, './Venter/upload_file.html', {
                    'file_form': excel_form, 'successful_submit': True})
        return render(request, './Venter/upload_file.html', {
            'file_form': excel_form})
    else:
        file_form = CSVForm(request=request)
        if request.method == 'POST':
            file_form = CSVForm(request.POST, request.FILES, request=request)
            if file_form.is_valid():
                file_uploaded = file_form.save(commit=False)
                file_uploaded.uploaded_by = request.user.profile
                file_uploaded.save()
                file_form = CSVForm(request=request)
                return render(request, './Venter/upload_file.html', {
                    'file_form': file_form, 'successful_submit': True})

        return render(request, './Venter/upload_file.html', {
            'file_form': file_form})

class CategoryListView(LoginRequiredMixin, ListView):
    """
    Arguments------
        1) LoginRequiredMixin: Request to update profile details by non-authenticated users,
        will throw an HTTP 404 error
        2) ListView: View to display the category list for the organisation to which the logged-in user belongs

    Functions------
        1) get_queryset(): Returns a new QuerySet filtering categories
        based on the organisation name passed in the parameter.
    """
    model = Category
    paginate_by = 13

    def get_queryset(self):

        result = Category.objects.filter(organisation_name=self.request.user.profile.organisation_name)

        query = self.request.GET.get('q', '')

        if query:
            result = Category.objects.filter(category__icontains=query)
        return result


class UpdateProfileView(LoginRequiredMixin, UpdateView):
    """
    Arguments------
        1) UpdateView: View to update the user profile details for the logged-in user
        2) LoginRequiredMixin: Request to update profile details by non-authenticated users,
        will throw an HTTP 404 error
    """
    model = Profile
    success_url = reverse_lazy('home')

    def post(self, request, *args, **kwargs):
        profile_form = ProfileForm(
            request.POST, request.FILES, instance=request.user.profile)
        if profile_form.is_valid():
            profile_form.save()
            profile_form = ProfileForm(instance=request.user.profile)
            return render(request, './Venter/update_profile.html',
                          {'profile_form': profile_form, 'successful_submit': True})
        else:
            return render(request, './Venter/update_profile.html',
                          {'profile_form': profile_form})

    def get(self, request, *args, **kwargs):
        profile_form = ProfileForm(instance=request.user.profile)
        return render(request, './Venter/update_profile.html', {'profile_form': profile_form})


class RegisterEmployeeView(LoginRequiredMixin, CreateView):
    """
    Arguments------
        1) CreateView: View to register a new user(employee) of an organisation.
    Note------
        1) The organisation name for a newly registered employee is taken from
           the profile information of the staff member registering the employee.
        2) The profile.save() returns an instance of Profile that has been saved to the database.
            This occurs only after the profile is created for a new user with the 'profile.user = user'
        3) The validate_password() is an in-built password validator in Django
            # module-django.contrib.auth.password_validation
        Ref: https://docs.djangoproject.com/en/2.1/topics/auth/passwords/
        4) The user_form instance is initialized again (user_form = UserForm()), for staff member
            to register another employee after successful submission of previous form
    """
    model = User

    def post(self, request, *args, **kwargs):
        user_form = UserForm(request.POST)
        if user_form.is_valid():
            user_obj = user_form.save(commit=False)
            password = user_form.cleaned_data.get('password')
            try:
                validate_password(password, user_obj)
                user_obj.set_password(password)
                user_obj.save()
                org_name = request.user.profile.organisation_name
                permission = Permission.objects.get(
                    name='Can view files uploaded by self')
                user_obj.user_permissions.add(permission)
                profile = Profile.objects.create(
                    user=user_obj, organisation_name=org_name)
                profile.save()
                user_form = UserForm()
                return render(request, './Venter/registration.html',
                              {'user_form': user_form, 'successful_submit': True})
            except ValidationError as e:
                user_form.add_error('password', e)
                return render(request, './Venter/registration.html', {'user_form': user_form})
        else:
            return render(request, './Venter/registration.html', {'user_form': user_form})

    def get(self, request, *args, **kwargs):
        user_form = UserForm()
        return render(request, './Venter/registration.html', {'user_form': user_form})


def contact_us(request):
    """
    View logic to email the administrator the contact details submitted by an organisation.
    The contact details are submitted through the 'contact_us' template form.

    For POST request-------
        The contact details of an organisation are collected in the ContactForm.
        If the form is valid, an email is sent to the website administrator.
    For GET request-------
        The contact_us template is rendered
    """
    contact_form = ContactForm()

    if request.method == 'POST':
        contact_form = ContactForm(request.POST)
        if contact_form.is_valid():
            company_name = contact_form.cleaned_data.get('company_name')
            contact_no = contact_form.cleaned_data.get('contact_no')
            email_address = contact_form.cleaned_data.get('email_address')
            requirement_details = contact_form.cleaned_data.get(
                'requirement_details')

            # get current date and time
            now = datetime.datetime.now()
            date_time = now.strftime("%Y-%m-%d %H:%M")

            # prepare email body
            email_body = "Dear Admin,\n\n Following are the inquiry details:\n\n " + \
                "Inquiry Date and Time: "+date_time+"\n Company Name: " + \
                company_name+"\n Contact Number: "+contact_no+"\n Email address: " + \
                email_address+"\n Requirement Details: "+requirement_details+"\n\n"
            mail_admins('Venter Inquiry', email_body)
            # contact_form.save()
            contact_form = ContactForm()
            return render(request, './Venter/contact_us.html', {
                'contact_form': contact_form, 'successful_submit': True})
    return render(request, './Venter/contact_us.html', {
        'contact_form': contact_form,
    })


class FileDeleteView(LoginRequiredMixin, DeleteView):
    """
    Arguments------
        1) LoginRequiredMixin: View to redirect non-authenticated users to show HTTP 403 error
        2) PermissionRequiredMixin: View to check whether the user is a staff
        having permission to delete organisation files
        3) DeletView: View to delete the files uploaded by user(s)/staff member(s) of the organisation

    Functions------
        1) get_queryset(): Returns a new QuerySet filtering files uploaded by the logged-in user
    """
    model = File
    success_url = reverse_lazy('dashboard')

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


class FileListView(LoginRequiredMixin, ListView):
    model = File
    template_name = './Venter/dashboard.html'
    context_object_name = 'file_list'
    paginate_by = 8

    def get_queryset(self):
        if self.request.user.is_staff:
            result = File.objects.filter(
                uploaded_by__organisation_name=self.request.user.profile.organisation_name)
        elif not self.request.user.is_staff and self.request.user.is_active:
            result = File.objects.filter(uploaded_by=self.request.user.profile)

        query = self.request.GET.get('q', '')
        if query:
            result = [file_obj for file_obj in result if query in file_obj.filename.lower()]
        return result

dict_data = {}
domain_list = []

@require_http_methods(["GET"])
def predict_result(request, pk):
    global dict_data, domain_list

    filemeta = File.objects.get(pk=pk)
    if not filemeta.has_prediction:
        output_directory_path = os.path.join(MEDIA_ROOT, f'{filemeta.uploaded_by.organisation_name}/{filemeta.uploaded_by.user.username}/{filemeta.uploaded_date.date()}/output')

        if not os.path.exists(output_directory_path):
            os.makedirs(output_directory_path)

        print(output_directory_path)
        output_file_path_json = os.path.join(output_directory_path, 'results.json')
        output_file_path_xlsx = os.path.join(output_directory_path, 'results.xlsx')

        sm = SimilarityMapping(filemeta.input_file.path)
        dict_data = sm.driver()

        if dict_data:
            filemeta.has_prediction = True

        with open(output_file_path_json, 'w') as temp:
            json.dump(dict_data, temp)

        print('JSON output saved.')
        print('Done.')

        filemeta.output_file_json = output_file_path_json

        download_output = pd.ExcelWriter(output_file_path_xlsx, engine='xlsxwriter')

        for domain in dict_data:
            print('Writing Excel for domain %s' % domain)
            df = pd.DataFrame({key:pd.Series(value) for key, value in dict_data[domain].items()})
            df.to_excel(download_output, sheet_name=domain)
        download_output.save()

        filemeta.output_file_xlsx = output_file_path_xlsx
        filemeta.save()
    else:
        dict_data = json.load(filemeta.output_file_json)
    dict_keys = dict_data.keys()
    domain_list = list(dict_keys)

    return render(request, './Venter/prediction_result.html', {
        'domain_list': domain_list, 'dict_data': dict_data
    })


@require_http_methods(["GET"])
def domain_contents(request):
    global dict_data, domain_list

    domain_name = request.GET.get('domain')
    domain_data = dict_data[domain_name]
    temp = ['Category']
    index = 0
    for subCat in domain_data['Novel']:
        temp.append('Sub category ' + str(index+1))
        index += 1
    temp.append({'role': 'style'})
    domain_stats = []
    domain_stats.append(temp)

    for category, responselist in domain_data.items():
        column = [category, len(responselist), '']
        if category == 'Novel':
            column = ['Novel']
            for subCat in domain_data[category]:
                column.append(len(domain_data[category][subCat]))
            column.append('')
        else:
            for i in range(len(domain_stats[0]) - len(column)):
                column.insert(2, 0)
        domain_stats.append(column)

    return render(request, './Venter/prediction_result.html', {
        'domain_data': domain_data, 'domain_list': domain_list,
        'domain_stats': jsonpickle.encode(domain_stats), 'chart_domain': domain_name
    })

@require_http_methods(["POST", "GET"])
def predict_csv(request, pk):
    """This function is used to handle the selected categories by the user"""

    file_object = File.objects.get(pk=pk)
    file_name = file_object.filename

    input_file_path = os.path.join(MEDIA_ROOT, f'{file_object.uploaded_by.organisation_name}/{file_object.uploaded_by.user.username}/{file_object.uploaded_date.date()}/input/{file_name}')

    csvfile = pd.read_csv(input_file_path, sep=',', header=0, encoding='latin')
    complaint_description = list(csvfile['complaint_description'])

    print("----type of complaint_description---")
    print(type(complaint_description))
    print(csvfile['complaint_description'].shape)
    # print(complaint_description)

    dict_list = []

    if str(request.user.profile.organisation_name) == 'ICMC':
        model = ClassificationService()
        category_queryset = Category.objects.filter(organisation_name='ICMC').values_list('category', flat=True)
        category_list = list(category_queryset)

    elif str(request.user.profile.organisation_name) == "SpeakUp":
        pass
        #do stuff
        # model = SpeakupClassificationService()
        # category_list = Category.objects.filter(organisation_name='SpeakUp').values_list('category', flat=True)

    cats = model.get_top_3_cats_with_prob(complaint_description)

    for row, complaint, scores in zip(csvfile.iterrows(), complaint_description, cats):
        row_dict = {}
        index, data = row
        row_dict['index'] = index

        if str(request.user.profile.organisation_name) == "ICMC":
            row_dict['problem_description'] = complaint
            row_dict['category'] = scores
            row_dict['highest_confidence'] = list(row_dict['category'].values())[0]
        else:
            continue
            data = data.dropna(subset=["text"])
            complaint_description = data['text']
            cats = model.get_top_3_cats_with_prob(complaint_description)
        dict_list.append(row_dict)
    dict_list = sorted(dict_list, key=lambda k: k['highest_confidence'], reverse=True)

    return render(request, './Venter/prediction_table.html', {'dict_list': dict_list, 'category_list': category_list})
