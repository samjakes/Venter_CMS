# -*- coding: utf-8 -*-
"""
Created on Mon Feb 25 17:15:22 2019

@author: Chintan Maniyar
"""

import pandas as pd
import re
import os

from Backend.settings import BASE_DIR

def parse(filepath):
    '''
    This function parses the fed csv file and saves them separately, 
    segregating the categories
    Args(1) - csv filepath
    '''
    xls = pd.ExcelFile(filepath)
    df = pd.read_excel(xls, 'Form responses 1', header=[0,1])

    headers = df.keys()[2:]
    headers = headers[:len(headers)-3]
    for h in headers[1::2]:
        filename = str(h).split(',')[0].split('\'')[1] + '.txt'

        file = open(os.path.join(BASE_DIR, 'Venter/ML_model/Civis/data/comments/') + filename, 'w', encoding='utf-8')
        index = 1
        print("Parsing " + filename + '...')
        for sentence in df[h]:
            if type(sentence) == str:
                file.write(str(index) + '- ' + sentence.lstrip().replace('\n', ' ') + '\n')
                index += 1
        file.close()
