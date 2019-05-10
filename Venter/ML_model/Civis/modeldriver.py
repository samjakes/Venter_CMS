# from . import csvparser, sentencemodel
from . import csvparser
from Venter.tasks import categorizer

class SimilarityMapping:
    '''
    This class consumes the model and sequences the flow of execution for the given input
    '''
    def __init__(self, path):
        self.filepath = path

    def driver(self):
        #parsing the input file for having sampled input to the model
        csvparser.parse(self.filepath)
        results = categorizer().delay()
        return results
