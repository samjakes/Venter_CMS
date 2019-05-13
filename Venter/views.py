import datetime
import json
import os
import re
from ast import literal_eval
from collections import defaultdict

import jsonpickle
import pandas as pd
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import mail_admins
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

from Backend.settings import ADMINS, BASE_DIR, MEDIA_ROOT
from Venter.forms import ContactForm, CSVForm, ExcelForm, ProfileForm, UserForm
from Venter.models import Category, File, Profile

from .ML_model.Civis.modeldriver import SimilarityMapping
from .ML_model.ICMC.model.ClassificationService import ClassificationService


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def upload_file(request):
    """
    View logic for uploading CSV/Excel file by a logged in user.

    For POST request-------
        1) The POST data, uploaded csv/xlsx file and a request parameter are being sent to CSVForm/ExcelForm as arguments
        2) If form.is_valid() returns true, the user is assigned to the uploaded_by field
        3) file_form is saved and Form instance is initialized again,
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
        2) LoginRequiredMixin: Request to register employees by non-authenticated users,
        will throw an HTTP 404 error
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
                # permission = Permission.objects.get(
                #     name='Can view files uploaded by self')
                # user_obj.user_permissions.add(permission)
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

            admin_list = User.objects.filter(is_superuser=True)
            for admin in admin_list:
                s = (admin.username, admin.email)
                ADMINS.append(s)

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
        3) DeletView: View to delete file(s) uploaded

    Functions------
        1) get: Returns a new Queryset of files uploaded by user(s)/staff member(s) of the organisation
    """
    model = File
    success_url = reverse_lazy('dashboard')

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


class FileListView(LoginRequiredMixin, ListView):
    """
    Arguments------
        1) LoginRequiredMixin: View to redirect non-authenticated users to show HTTP 403 error
        3) ListView: View to display file(s) uploaded

    Functions------
        1) get_queryset():
        For a user, returns the files uploaded by the logged-in employee
        For a staff member, returns the files uploaded by user(s)/staff member(s) of the organisation
    """
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


@login_required
@require_http_methods(["GET"])
def predict_result(request, pk):
    """
    View logic for running CIVIS Prediction Model on files uploaded by CIVIS users.
    If the input file is being predicted for the first time:
        1) Two output files (.json and .xlsx files are created in file storage)
        2) Input file path is feed into the SimilarityMapping method of ML model
        3) dict_data stores the result json response returned from the ML model
        4) prediction_results.html template is rendered
    If the input file has already been predicted once:
        1) dict_data stores the result json data from the results.json file already created from the ML model
        2) prediction_results.html template is rendered
    """

    json_file_path = os.path.join(BASE_DIR, 'test_dict_data2.json')
    dict_data = {}
    domain_list = []

    with open(json_file_path) as json_file:
        dict_data = json.load(json_file)

    filemeta = File.objects.get(pk=pk)
    output_directory_path = os.path.join(MEDIA_ROOT, f'{filemeta.uploaded_by.organisation_name}/{filemeta.uploaded_by.user.username}/{filemeta.uploaded_date.date()}/output')

    if not os.path.exists(output_directory_path):
        os.makedirs(output_directory_path)

    temp1 = filemeta.filename
    temp2 = os.path.splitext(temp1)
    custom_input_file_name = temp2[0]
    
    output_json_file_name = 'results__'+custom_input_file_name+'.json'
    output_xlsx_file_name = 'results__'+custom_input_file_name+'.xlsx'

    output_file_path_json = os.path.join(output_directory_path, output_json_file_name)
    output_file_path_xlsx = os.path.join(output_directory_path, output_xlsx_file_name)

    filemeta.output_file_json = output_file_path_json
    filemeta.output_file_xlsx = output_file_path_xlsx
    filemeta.save()

    # filemeta = File.objects.get(pk=pk)
    # if not filemeta.has_prediction:
    #     output_directory_path = os.path.join(MEDIA_ROOT, f'{filemeta.uploaded_by.organisation_name}/{filemeta.uploaded_by.user.username}/{filemeta.uploaded_date.date()}/output')

    #     if not os.path.exists(output_directory_path):
    #         os.makedirs(output_directory_path)

    #     temp1 = filemeta.filename
    #     temp2 = os.path.splitext(temp1)
    #     custom_input_file_name = temp2[0]
        
    #     output_json_file_name = 'results__'+custom_input_file_name+'.json'
    #     output_xlsx_file_name = 'results__'+custom_input_file_name+'.xlsx'
 
    #     output_file_path_json = os.path.join(output_directory_path, output_json_file_name)
    #     output_file_path_xlsx = os.path.join(output_directory_path, output_xlsx_file_name)

    #     dict_data = {}
    #     domain_list = []

    #     sm = SimilarityMapping(filemeta.input_file.path)
    #     dict_data = sm.driver()

    #     if dict_data:
    #         filemeta.has_prediction = True

    #     with open(output_file_path_json, 'w') as temp:
    #         json.dump(dict_data, temp)

    #     print('JSON output saved.')
    #     print('Done.')

    #     filemeta.output_file_json = output_file_path_json

    #     download_output = pd.ExcelWriter(output_file_path_xlsx, engine='xlsxwriter')

    #     for domain in dict_data:
    #         print('Writing Excel for domain %s' % domain)
    #         df = pd.DataFrame({key:pd.Series(value) for key, value in dict_data[domain].items()})
    #         df.to_excel(download_output, sheet_name=domain)
    #     download_output.save()

    #     filemeta.output_file_xlsx = output_file_path_xlsx
    #     filemeta.save()
    # else:
    #     dict_data = json.load(filemeta.output_file_json)

    dict_keys = dict_data.keys()
    domain_list = list(dict_keys)
    domain_data = {}

    for domain_name in domain_list:
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
        dict_data[domain_name]['Statistics'] = jsonpickle.encode(domain_stats)

    # with open('test_dict_data1.json', 'w') as temp:
    #     json.dump(dict_data, temp)

    return render(request, './Venter/prediction_result.html', {
        'domain_list': domain_list, 'dict_data': json.dumps(dict_data)
    })


@login_required
@require_http_methods(["GET", "POST"])
def predict_csv(request, pk):
    """
    View logic for running ICMC Prediction Model on files uploaded by ICMC users.
    If the input file is being predicted for the first time:
        1) Two output files (.json and .csv files are created in file storage)
        2) Input file path is feed into the get_top_3_cats_with_prob method of ML model
        3) dict_data stores the result json response returned from the ML model
        4) prediction_table.html template is rendered
    If the input file has already been predicted once:
        1) dict_data stores the result json data from the results.json file already created from the ML model
        2) prediction_table.html template is rendered
    """
    filemeta = File.objects.get(pk=pk)
    
    if not filemeta.has_prediction:
        output_directory_path = os.path.join(MEDIA_ROOT, f'{filemeta.uploaded_by.organisation_name}/{filemeta.uploaded_by.user.username}/{filemeta.uploaded_date.date()}/output')
        if not os.path.exists(output_directory_path):
            os.makedirs(output_directory_path)

        temp1 = filemeta.filename
        temp2 = os.path.splitext(temp1)
        custom_input_file_name = temp2[0]
        
        output_json_file_name = 'results__'+custom_input_file_name+'.json'
        output_csv_file_name = 'results__'+custom_input_file_name+'.csv'

        output_file_path_json = os.path.join(output_directory_path, output_json_file_name)
        output_file_path_csv = os.path.join(output_directory_path, output_csv_file_name)
        
        input_file_path = filemeta.input_file.path
        csvfile = pd.read_csv(input_file_path, sep=',', header=0, encoding='latin1')
        csvfile.columns = [col.strip() for col in csvfile.columns]

        complaint_description = list(csvfile['complaint_description'])
        ward_name = list(csvfile['ward_name'])
        ward_list = list(set(ward_name))
        date_created = []

        for x in list(csvfile['complaint_created']):
            y = x.split(' ')[0]
            date_created.append(y)
        date_list = list(set(date_created))

        dict_list = []
        unsorted_dict_list = []

        if str(request.user.profile.organisation_name) == 'ICMC':
            model = ClassificationService()
        elif str(request.user.profile.organisation_name) == "SpeakUp":
            pass

        cats = model.get_top_3_cats_with_prob(complaint_description)

        for row, complaint, scores, ward, date in zip(csvfile.iterrows(), complaint_description, cats, ward_name, date_created):
            row_dict = {}
            index, data = row
            row_dict['index'] = index

            if str(request.user.profile.organisation_name) == "ICMC":
                row_dict['problem_description'] = complaint
                row_dict['category'] = scores
                row_dict['highest_confidence'] = list(row_dict['category'].values())[0]
                row_dict['ward_name'] = ward
                row_dict['date_created'] = date
            else:
                continue
                # data = data.dropna(subset=["text"])
                # complaint_description = data['text']
                # cats = model.get_top_3_cats_with_prob(complaint_description)
            dict_list.append(row_dict)
        unsorted_dict_list = dict_list
        dict_list = sorted(dict_list, key=lambda k: k['highest_confidence'], reverse=True)

        if dict_list:
            filemeta.has_prediction = True

        with open(output_file_path_json, 'w') as temp:
            json.dump(unsorted_dict_list, temp)
        print('JSON output saved.')
        print('Done.')

        with open(input_file_path, 'r', encoding="latin1") as f1:
            with open(output_file_path_csv, 'w', encoding="latin1") as f2:
                for line in f1:
                    f2.write(line)

        output_csv_file = pd.read_csv(output_file_path_csv, sep=',', header=0)
        original_category_list = []
        temp_cat_list = []
        for item in unsorted_dict_list:
            temp_cat_list = list(item['category'].keys())
            del temp_cat_list[1:]
            original_category_list.append(temp_cat_list)

        output_csv_file.insert(0, "Predicted_Category", original_category_list)
        output_csv_file.to_csv(output_file_path_csv, index=False)

        filemeta.output_file_json = output_file_path_json
        filemeta.output_file_xlsx = output_file_path_csv
        filemeta.save()
    else:
        dict_list = json.load(filemeta.output_file_json)

        if filemeta.file_saved_status:
            temp_list = []
            custom_category_list = []
            output_file_path_xlsx = filemeta.output_file_xlsx.path
            output_xlsx_csv_file = pd.read_csv(output_file_path_xlsx, sep=',', header=0)
            temp_list = output_xlsx_csv_file['Predicted_Category']

            for item in temp_list:
                item = literal_eval(item)
                custom_category_list.append(item)

            for item, cat in zip(dict_list, custom_category_list):
                item['category'] = cat
                
        dict_list = sorted(dict_list, key=lambda k: k['highest_confidence'], reverse=True)

    # preparing ward list and date list for multi-filter widget
    input_file_path = filemeta.input_file.path
    input_csv_file = pd.read_csv(input_file_path, sep=',', header=0, encoding='latin1')
    input_csv_file.columns = [col.strip() for col in input_csv_file.columns]

    date_created = []
    for x in list(input_csv_file['complaint_created']):
        y = x.split(' ')[0]
        date_created.append(y)

    date_list = list(set(date_created))
    ward_name = list(input_csv_file['ward_name'])
    ward_list = list(set(ward_name))

    # preparing category list based on organisation name
    if str(request.user.profile.organisation_name) == 'ICMC':
        category_queryset = Category.objects.filter(organisation_name='ICMC').values_list('category', flat=True)
        category_list = list(category_queryset)
    elif str(request.user.profile.organisation_name) == 'SpeakUp':
        category_queryset = Category.objects.filter(organisation_name='SpeakUp').values_list('category', flat=True)
        category_list = list(category_queryset)
    return render(request, './Venter/prediction_table.html', {'dict_list': dict_list, 'category_list': category_list, 'filemeta': filemeta, 'ward_list': ward_list, 'date_list': date_list})

@login_required
@require_http_methods(["POST"])
def download_table(request, pk):
    """
    View logic to prepare a .csv output file for files uploaded by ICMC users
        1) category_rec stores a two-dimensional list for all the custom categories selected by the user
        2) If 'Predicted_Category' column exists in results.csv file, it is dropped
        3) New category list is populated in the results.csv file and results.csv file is saved in the database
        4) Predicted_table template is rendered and user downloads the results.csv file(from dashboard.html)
    """
    filemeta = File.objects.get(pk=pk)
    sorted_category_list = json.loads(request.POST['sorted_category'])

    status = request.POST['file_saved_status']
    new_sorted_category_list = []

    for temp1 in sorted_category_list:
        # temp1 = [re.split(r"([\(])", x)[0] for x in sublist]
        temp2 = [x.lstrip() for x in temp1]
        temp3 = [x.rstrip() for x in temp2]
        new_sorted_category_list.append(temp3)

    output_csv_file_path = filemeta.output_file_xlsx.path
    csv_file = pd.read_csv(output_csv_file_path, sep=',', header=0)

    if status == "True":
        filemeta.file_saved_status = True
        if 'Predicted_Category' in csv_file.columns:
            csv_file = csv_file.drop("Predicted_Category", axis=1)
        csv_file.insert(0, "Predicted_Category", new_sorted_category_list)

    csv_file.to_csv(output_csv_file_path, index=False)

    filemeta.output_file_xlsx = output_csv_file_path
    filemeta.save()
    return HttpResponseRedirect(reverse('predict_csv', kwargs={"pk": filemeta.pk}))


@login_required
@require_http_methods(["GET", "POST"])
def wordcloud(request, pk):
    filemeta = File.objects.get(pk=pk)

    if str(request.user.profile.organisation_name) == 'ICMC':
        category_queryset = Category.objects.filter(organisation_name='ICMC').values_list('category', flat=True)
        category_list = list(category_queryset)
    elif str(request.user.profile.organisation_name) == 'SpeakUp':
        category_queryset = Category.objects.filter(organisation_name='SpeakUp').values_list('category', flat=True)
        category_list = list(category_queryset)

    if request.method == 'POST':
        output_file_path = filemeta.output_file_xlsx.path
        output_file = pd.read_csv(output_file_path, sep=',', header=0)
        
        temp_dict = defaultdict(list)
        
        for predicted_category_str, complaint_description in zip(output_file['Predicted_Category'], output_file['complaint_description']):
            predicted_category_list = literal_eval(predicted_category_str)
            if predicted_category_list:
                final_cat = predicted_category_list[0]
                final_cat = re.split(r"\(", final_cat)[0]
                final_cat = final_cat.strip(' ')

                if final_cat not in temp_dict:
                    response_list = []
                    response_list.append(complaint_description)
                    temp_dict[final_cat] = response_list
                else:
                    response_list = []
                    response_list.append(complaint_description)
                    temp_dict[final_cat].append(complaint_description)
            else:
                pass
        wordcloud_input_dict = dict(temp_dict)
        print("writing to json file")
        with open('wordcloud_input_data.json', 'w') as fp:
            json.dump(wordcloud_input_dict, fp)

        keys = ["garbage", "recreation park", "dumpster on road", "traffic near K.G road", "plant trees on pavement", "road conditions", "water pond"]
        values = [10, 90, 30, 20, 54, 45, 100]
        words = {}
        words = dict(zip(keys, values))
            
        return render(request, './Venter/wordcloud.html', {'category_list': category_list, 'filemeta': filemeta, 'words':words})
    else:
        return render(request, './Venter/wordcloud.html', {'category_list': category_list, 'filemeta': filemeta})

@login_required
@require_http_methods(["GET", "POST"])
def visualization_dashboard(request, pk):
    filemeta = File.objects.get(pk=pk)

    if str(request.user.profile.organisation_name) == 'ICMC':
        # none
        pass
    elif str(request.user.profile.organisation_name) == 'CIVIS':
        output_file_path = filemeta.output_file_xlsx.path

    if request.method == 'GET':
        return render(request, './Venter/visualization_dashboard.html', {'filemeta': filemeta})
