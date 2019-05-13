import ast
from django import template


register = template.Library()

@register.filter
def get_domain_data(dictionary, key):
    p = ast.literal_eval(dictionary)
    return p[key]

@register.filter
def get_domain(value, domain):
    print("-------------------inside get_domain FUNCTION-------------------------------")
    print(type(value))
    print("value passed: ", value)
    print(type(domain))
    print("domain passed: ", domain)
    print("-------------------outside FUNCTION-------------------------------")
    return value.replace(value, domain)
    