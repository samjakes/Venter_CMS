"""Helper functions for the Venter app code"""
import os
from datetime import date

def get_file_upload_path(instance, filename):
    """
    Returns a custom MEDIA path for files uploaded by a user
    Eg: /MEDIA/CSV Files/xyz/user1/2019-02-06/file1.csv
    """
    return os.path.join(
        f'CSV Files/{instance.uploaded_by.profile.organisation_name}/{instance.uploaded_by.profile.user.username}/{instance.uploaded_date.date()}/{filename}')

def get_organisation_logo_path(instance, filename):
    """
    Returns a custom MEDIA path for organisation logo uploaded by staff member
    Eg: /MEDIA/Organisation Logo/xyz/2019-02-06/image1.png
    """
    return os.path.join(
        f'Organisation Logo/{instance.organisation_name}/{date.today()}/{filename}')


def get_user_profile_picture_path(instance, filename):
    """
    Returns a custom MEDIA path for profile picture uploaded by user
    Eg: /MEDIA/User Profile Picture/xyz/user1/2019-02-06/image2.png
    """
    return os.path.join(
        f'User Profile Picture/{instance.organisation_name}/{instance.user.username}/{date.today()}/{filename}')