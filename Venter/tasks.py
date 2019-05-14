from celery.utils.log import get_task_logger

from Backend.celery import app
from .ML_model.Civis.modeldriver import SimilarityMapping

logger = get_task_logger(__name__)

@app.task
def predict_runner(filepath):
    sm = SimilarityMapping(filepath)
    results = sm.driver()
    return results

