from Backend.celery import app
from .ML_model.Civis.modeldriver import SimilarityMapping

@app.task
def predict_runner(filepath):
    sm = SimilarityMapping(filepath)
    results = sm.driver()
    return results
