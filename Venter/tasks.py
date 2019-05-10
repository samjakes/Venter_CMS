import os
import time

import numpy as np
from gensim.models import KeyedVectors
from networkx.algorithms.components.connected import connected_components
from nltk.corpus import wordnet as wn
from sklearn.feature_extraction.text import TfidfVectorizer

from Backend.celery import app
from Backend.settings import BASE_DIR

from .ML_model.Civis.sentencemodel import toGraph, similarityIndex


@app.task
def categorizer():
    '''
    driver function,
    returns model output mapped on the input corpora as a dict object
    '''
    stats = open('stats.txt', 'w', encoding='utf-8')

    st = time.time()
    wordmodelfile = os.path.join(BASE_DIR, 'Venter/ML_model/Civis/MAX.bin')
    wordmodel = KeyedVectors.load_word2vec_format(wordmodelfile, binary=True, limit=200000)
    et = time.time()
    s = 'Word embedding loaded in %f secs.' % (et-st)
    print(s)
    stats.write(s + '\n')

    #filepaths
    responsePath = os.path.join(BASE_DIR, 'Venter/ML_model/Civis/data/comments/')
    categoryPath = os.path.join(BASE_DIR, 'Venter/ML_model/Civis/data/sentences/')
    responseDomains = os.listdir(responsePath)
    categoryDomains = os.listdir(categoryPath)
    
    #dictionary for populating the json output
    results = {}
    for responseDomain, categoryDomain in zip(responseDomains, categoryDomains):
        #instantiating the key for the domain
        domain = responseDomain[:-4]
        results[domain] = {}

        print('Categorizing %s domain...' % domain)

        temp = open(os.path.join(responsePath, responseDomain), 'r', encoding='utf-8-sig')
        responses = temp.readlines()
        rows = len(responses)

        temp = open(os.path.join(categoryPath, categoryDomain), 'r', encoding='utf-8-sig')
        categories = temp.readlines()
        columns = len(categories)
        categories.append('Novel')

        #saving the scores in a similarity matrix
        #initializing the matrix with -1 to catch dump/false entries
        st = time.time()
        similarity_matrix = [[-1 for c in range(columns)] for r in range(rows)]
        et = time.time()
        s = 'Similarity matrix initialized in %f secs.' % (et-st)
        print(s)
        stats.write(s + '\n')

        row = 0
        st = time.time()
        for response in responses:
            column = 0
            for category in categories[:-1]:
                similarity_matrix[row][column] = similarityIndex(response.split('-')[1].lstrip(), category, wordmodel)
                column += 1
            row += 1
        et = time.time()
        s = 'Similarity matrix populated in %f secs. ' % (et-st)
        print(s)
        stats.write(s + '\n')

        print('Initializing json output...')
        for catName in categories:
            results[domain][catName] = []

        print('Populating category files...')
        for score_row, response in zip(similarity_matrix, responses):
            max_sim_index = len(categories)-1
            if np.array(score_row).sum() > 0:
                max_sim_index = np.array(score_row).argmax()
                temp = {}
                temp['response'] = response
                temp['score'] = int((np.array(score_row).max())*100)
            else:
                temp = response
            results[domain][categories[max_sim_index]].append(temp)
        print('Completed.\n')

        #sorting domain wise categorised responses based on scores
        for domain in results:
            for category in results[domain]:                                                                                                                                      
                temp = results[domain][category]
                if len(temp)==0 or category=='Novel':
                    continue
                #print(temp)
                results[domain][category] = sorted(temp, key=lambda k: k['score'], reverse=True)
        #newlist = sorted(list_to_be_sorted, key=lambda k: k['name']) --> to sort list of dictionaries

        #initializing the matrix with -1 to catch dump/false entries for subcategorization of the novel responses
        no_of_novel_responses = len(results[domain]['Novel'])
        st = time.time()
        similarity_matrix = [[-1 for c in range(no_of_novel_responses)] for r in range(no_of_novel_responses)]
        et = time.time()
        s = 'Similarity matrix for subcategorization of novel responses for %s domain initialized in %f secs.' % (domain, (et-st))
        print(s)
        stats.write(s + '\n')
        

        #populating the matrix
        row = 0
        for response1 in results[domain]['Novel']:
            column = 0
            for response2 in results[domain]['Novel']:
                if response1 == response2:
                    column += 1
                    continue
                similarity_matrix[row][column] = similarityIndex(response1.split('-')[1].lstrip(), response2.split('-')[1].lstrip(), wordmodel)
                column += 1
            row += 1
        
        setlist = []
        index = 0
        for score_row, response in zip(similarity_matrix, results[domain]['Novel']):
            max_sim_index = index
            if np.array(score_row).sum() > 0:
                max_sim_index = np.array(score_row).argmax()
            if set([response, results[domain]['Novel'][max_sim_index]]) not in setlist:
                setlist.append([response, results[domain]['Novel'][max_sim_index]])
            index += 1
    
        G = toGraph(setlist)
        setlist = list(connected_components(G))
    
        novel_sub_categories = {}
        index = 0
        for category in setlist:
            novel_sub_categories[index] = list(category)
            index += 1

        results[domain]['Novel'] = novel_sub_categories

        print('***********************************************************')
    return results
