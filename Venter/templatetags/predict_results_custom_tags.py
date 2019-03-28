import jsonpickle
from django import template

register = template.Library()

@register.filter
def get_domain_data(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_domain_stats(dictionary, key):
    domain_data = dictionary.get(key)
    temp = ['Category']
    index = 0
    for subCat in domain_data['Novel']:
        temp.append('Sub category ' + str(index+1))
        index += 1
    temp.append({'role':'style'})
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
                column.insert(2,0)
        domain_stats.append(column)
    return jsonpickle.encode(domain_stats)