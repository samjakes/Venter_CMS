import os

import numpy as np
import pandas as pd
from django.conf import settings

from .ImportGraph import ImportGraph


class ClassificationService:
    def __init__(self):

        complaints = pd.read_csv(
            os.path.join(settings.BASE_DIR, "Venter", "ML_model", "ICMC", "dataset", "dataset_mcgm_clean",
                         "complaint_categories.csv"))
        self.index_complaint_title_map = {}

        for i in range(len(complaints)):
            line = complaints['Subcategory-English'][i]

            if isinstance(line, float):
                line = complaints['Subcategory-Marathi'][i]

            line = line.strip('\'').replace("/", " ").replace("(", " ").replace(")", " ")
            self.index_complaint_title_map[i] = line

        self.g0 = ImportGraph.get_instance()

    def get_probs_graph(self, model_id, data, flag):
        if model_id == 0:
            model = self.g0

        data = model.process_query(data, flag)
        d = model.run(data)
        print(d)
        return d

    def get_top_3_cats_with_prob(self, data):

        
        prob1 = self.get_probs_graph(0, data, flag=1)
        
        final_prob = prob1[0]

        final_sorted = np.argsort(prob1)[::-1]
        
        
        temp = final_sorted[-1]
        print(temp)
        t2 = []
        for i in range(3):
            t2.append(float(final_prob[temp[-3:][2-i]]))
        
        print('****SWA LA LA********')
        print(t2)

        #     t2.append(float(temp[-3:][2-i]))
        
	    # Returns list of size [batch_size] where each list member is dict with 3 key-value pair
        return [{self.index_complaint_title_map[x]: float(prob1[i, x]) for x in final_sorted[i, :3]} for i in
                range(len(final_sorted))]