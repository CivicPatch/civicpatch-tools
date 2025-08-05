from markdownify import markdownify as md 
from steps.step_02_preprocessing.filter_content import filter_content

def preprocess(input_html):
    output_html =  filter_content(input_html)

    output_md = md(output_html)
    return output_md